"""
YOLO Object Detection Module

Detects objects in video frames using YOLOv8-nano.
Model loads once, reused across all frames.

Interface:
    detect(frame, target) → list of {object_class, confidence, bbox}
    detect(frame)          → list of ALL detections (for scene description)
"""

import numpy as np

# Load model once at module level
_model = None


def _get_model():
    """Load YOLOv8-nano model. Lazy loaded on first call."""
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO
            _model = YOLO("yolov8n.pt")
            _model.to("cpu")
        except ImportError:
            raise RuntimeError("Install ultralytics: pip install ultralytics")
    return _model


def detect(frame: np.ndarray, target: str = None, confidence: float = 0.5) -> list:
    """
    Detect objects in a frame.

    Args:
        frame: BGR image (numpy array)
        target: specific object class to filter for ("car", "person", etc.)
                if None, returns all detections
        confidence: minimum confidence threshold

    Returns:
        list of dicts, each with:
            object_class: str ("car", "person", etc.)
            confidence: float (0-1)
            bbox: list [x1, y1, x2, y2]
        Returns empty list if nothing found.
    """
    model = _get_model()

    try:
        results = model(frame, conf=confidence, verbose=False)

        if not results or len(results) == 0:
            return []

        detections = []
        boxes = results[0].boxes

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            cls_name = results[0].names[cls_id]

            # Filter by target if specified
            if target and cls_name != target:
                continue

            detections.append({
                "object_class": cls_name,
                "confidence": round(conf, 3),
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
            })

        # Sort by confidence descending
        detections.sort(key=lambda d: d["confidence"], reverse=True)

        return detections

    except Exception:
        return []


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import cv2
    import sys

    if len(sys.argv) < 2:
        print("Usage: python yolo_detector.py <image_path>")
        print("\nRunning with blank frame (will detect nothing)...\n")

        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        results = detect(frame)
        print(f"Detections on blank frame: {len(results)}")
        sys.exit(0)

    image_path = sys.argv[1]
    frame = cv2.imread(image_path)

    if frame is None:
        print(f"Cannot read image: {image_path}")
        sys.exit(1)

    # Detect all objects
    print("--- All detections ---")
    all_results = detect(frame)
    for d in all_results:
        print(f"  {d['object_class']}: {d['confidence']} at {d['bbox']}")

    # Detect specific target
    print("\n--- Filter: person ---")
    person_results = detect(frame, target="person")
    print(f"  Found {len(person_results)} person(s)")

    # How analyzer.py uses it
    print("\n--- Analyzer simulation ---")
    target = "person"
    results = detect(frame, target)
    if results:
        best = max(results, key=lambda d: d["confidence"])
        print(f"  Best: {best['object_class']} at {best['confidence']} bbox={best['bbox']}")
    else:
        print(f"  No {target} found")