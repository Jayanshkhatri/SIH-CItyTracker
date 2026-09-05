# Multi-Camera ANPR Traffic Tracking — Starter Project

A working prototype of the system you described:
- Upload a video tagged to a fixed camera location
- Backend detects plates (OpenCV + EasyOCR), saves to one shared SQLite database
- Dashboard updates live: list + map markers
- Cross-camera matching: distance / travel time / avg speed per leg
- Full multi-camera trajectory once a plate is seen at 2+ cameras
- Alerts: blacklist hits, speeding, route anomalies
- Heatmap data via `/api/heatmap`

## 1. Install Python
Get Python 3.10 or 3.11 from https://python.org (tick "Add to PATH" during install on Windows).

## 2. Open the folder in VS Code
File → Open Folder → select `anpr_project`.

## 3. Create a virtual environment (keeps this project's packages separate)
Open VS Code's terminal (`` Ctrl+` ``) and run:

```bash
python -m venv venv
```

Activate it:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

## 4. Install dependencies
```bash
pip install -r requirements.txt
```
Note: `easyocr` will download a small OCR model the first time it runs — needs internet once.

## 5. Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

## 6. Try it
1. Upload a traffic video, pick a camera (e.g. CAM_A), set the recording start time.
2. Wait for processing (progress shows in the status line — longer videos take longer, this runs frame-by-frame).
3. Upload a second video tagged to a different camera (CAM_B) with a plate that also appears in video 1.
4. Click that plate in the "Detected Vehicles" list → see the route drawn on the map with distance/time/speed.
5. Check the "Alerts" tab for speeding / blacklist / route anomaly flags.

To test blacklist alerts:
```bash
curl -X POST http://127.0.0.1:5000/api/blacklist -H "Content-Type: application/json" -d "{\"plate\": \"DL1CAB1234\", \"reason\": \"stolen\"}"
```

## Project structure
```
anpr_project/
  app.py                 <- Flask server + all API routes
  cameras.json            <- edit this to add/rename cameras, set speed limit & route order
  requirements.txt
  anpr/
    db.py                 <- SQLite: detections, blacklist, alerts
    detector.py            <- OpenCV + EasyOCR plate detection pipeline
    geo.py                 <- distance/speed math (haversine)
    analytics.py            <- trajectories, speeding/blacklist/anomaly checks
  templates/index.html      <- dashboard page
  static/css/style.css      <- dashboard styling
  static/js/dashboard.js    <- map, tables, alerts, trajectory rendering (fetch calls to the API)
  uploads/                  <- uploaded videos are saved here
  db/anpr.db                <- created automatically on first run
```

## Known limitations (this is a v1, not production)
- The OpenCV Haar Cascade plate detector is general-purpose, not trained on
  Indian plates specifically — detection accuracy on real footage will be
  moderate. For better accuracy, replace `anpr/detector.py`'s cascade with a
  YOLOv8 model fine-tuned on license plates (the DB/API/dashboard code does
  not need to change).
- Video processing is synchronous (blocks the upload request) — fine for a
  demo. For production, move `process_video()` into a background task queue
  (e.g. Celery + Redis) so uploads return instantly and processing happens async.
- Camera GPS coordinates are hardcoded in `cameras.json` — edit that file to
  match your real camera locations.
