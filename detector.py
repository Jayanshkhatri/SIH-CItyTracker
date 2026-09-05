"""
detector.py
This is the "computer vision" part.

Pipeline for every sampled frame of the video:
  1. Use an OpenCV Haar Cascade to find rectangle regions that LOOK like
     number plates (fast, works out of the box, no training needed).
  2. Crop those regions and run EasyOCR on them to read the actual text.
  3. Clean up the text (remove OCR junk) and keep only plausible plate strings.

NOTE FOR BEGINNERS: the Haar Cascade shipped with OpenCV is a general-purpose
"plate-shaped rectangle" detector, not a India-specific plate model, so
accuracy on real traffic footage will be moderate. For a college project /
demo this is completely fine. If you want production-grade accuracy later,
swap this cascade for a YOLOv8 model fine-tuned on license plates - the rest
of this codebase (DB, dashboard, analytics) does not need to change at all.
"""

import re
import cv2

_reader = None  # lazy-loaded so the Flask app starts up fast


def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


_plate_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
)

PLATE_REGEX = re.compile(r"^[A-Z0-9]{5,11}$")


def clean_text(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def detect_plates_in_frame(frame, min_confidence=0.35):
    """Returns a list of {'plate': str, 'confidence': float} found in one frame."""
    results = []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    boxes = _plate_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 20)
    )

    reader = get_reader()
    for (x, y, w, h) in boxes:
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            continue
        ocr_hits = reader.readtext(crop)
        for (_bbox, text, conf) in ocr_hits:
            cleaned = clean_text(text)
            if PLATE_REGEX.match(cleaned) and conf >= min_confidence:
                results.append({"plate": cleaned, "confidence": float(conf)})
    return results


def process_video(video_path, sample_fps=1):
    """
    Reads the video frame by frame but only actually RUNS detection on
    `sample_fps` frames per second of footage (running OCR on every single
    frame would be very slow and mostly redundant).

    Returns a list of {'plate', 'confidence', 'frame_time_sec'}.
    frame_time_sec = how many seconds into the video this was seen -
    the caller converts that into a real (global clock) timestamp.
    """
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_interval = max(int(video_fps / sample_fps), 1)

    frame_idx = 0
    detections = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_interval == 0:
            hits = detect_plates_in_frame(frame)
            for h in hits:
                h["frame_time_sec"] = frame_idx / video_fps
                detections.append(h)
        frame_idx += 1

    cap.release()
    return detections
