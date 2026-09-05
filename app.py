"""
app.py
The Flask web server. This is the file you run.

Routes:
  GET  /                       -> dashboard page
  GET  /api/cameras            -> list of cameras (for the upload dropdown + map)
  POST /api/upload             -> upload + process a video for one camera
  GET  /api/detections         -> every plate ever detected (for the list/map)
  GET  /api/vehicle/<plate>    -> full trajectory for one plate
  GET  /api/alerts             -> all alerts (blacklist / speeding / anomaly)
  GET  /api/heatmap            -> detection counts per camera
  POST /api/blacklist          -> add a plate to the blacklist
"""

import os
import json
import time
from datetime import datetime

from flask import Flask, request, jsonify, render_template

from anpr import db, analytics
from anpr.detector import process_video

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)

with open(os.path.join(BASE_DIR, "cameras.json")) as f:
    CONFIG = json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cameras")
def api_cameras():
    return jsonify(CONFIG["cameras"])


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Expects multipart/form-data:
      video        - the video file
      camera_id    - e.g. 'CAM_A'
      start_time   - ISO datetime string: when the video RECORDING started
                      (this is what lets us convert "frame at 12.4s" into a
                       real global timestamp that can be compared across cameras)
    """
    video = request.files.get("video")
    camera_id = request.form.get("camera_id")
    start_time_str = request.form.get("start_time")

    if not video or not camera_id or not start_time_str:
        return jsonify({"error": "video, camera_id and start_time are all required"}), 400

    if camera_id not in CONFIG["cameras"]:
        return jsonify({"error": f"unknown camera_id {camera_id}"}), 400

    camera = CONFIG["cameras"][camera_id]

    # save uploaded video to disk
    filename = f"{camera_id}_{int(time.time())}_{video.filename}"
    save_path = os.path.join(UPLOAD_DIR, filename)
    video.save(save_path)

    # parse the recording start time -> unix epoch seconds
    start_epoch = datetime.fromisoformat(start_time_str).timestamp()

    # ---- run the CV pipeline ----
    raw_detections = process_video(save_path, sample_fps=1)

    inserted_plates = set()
    for d in raw_detections:
        global_ts = start_epoch + d["frame_time_sec"]
        db.insert_detection(
            plate=d["plate"],
            camera_id=camera_id,
            camera_name=camera["name"],
            lat=camera["lat"],
            lon=camera["lon"],
            timestamp=global_ts,
            confidence=d["confidence"],
            video_source=filename,
        )
        inserted_plates.add(d["plate"])

    # run per-plate checks (blacklist + speeding) for everything just inserted
    for plate in inserted_plates:
        analytics.run_all_checks_for_plate(plate)

    # route-anomaly check looks across ALL cameras/plates, run it globally
    analytics.run_global_checks()

    return jsonify({
        "message": f"Processed {video.filename} for {camera['name']}",
        "plates_found": len(inserted_plates),
        "plates": sorted(inserted_plates),
    })


@app.route("/api/detections")
def api_detections():
    return jsonify(db.get_all_detections())


@app.route("/api/vehicle/<plate>")
def api_vehicle(plate):
    return jsonify(analytics.get_trajectory(plate.upper()))


@app.route("/api/alerts")
def api_alerts():
    return jsonify(db.get_alerts())


@app.route("/api/heatmap")
def api_heatmap():
    return jsonify(db.get_camera_counts())


@app.route("/api/blacklist", methods=["POST"])
def api_blacklist():
    data = request.get_json(force=True)
    plate = data.get("plate", "").upper().strip()
    reason = data.get("reason", "manually flagged")
    if not plate:
        return jsonify({"error": "plate is required"}), 400
    db.add_to_blacklist(plate, reason)
    return jsonify({"message": f"{plate} added to blacklist"})


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
