"""
Object Counter Module

Counts objects from YOLO detection results.
Does NOT run YOLO itself — receives YOLO output from analyzer.py.

Interface:
    count(detections, target) → int
"""


def count(detections: list, target: str = None) -> int:
    """
    Count objects in YOLO detection results.

    Args:
        detections: list from yolo_detector.detect()
            each item: {object_class, confidence, bbox}
        target: specific class to count (None = count all)

    Returns:
        int count
    """
    if not detections:
        return 0

    if target:
        return sum(1 for d in detections if d["object_class"] == target)

    return len(detections)


def count_with_details(detections: list, target: str = None) -> dict:
    """
    Count with breakdown by class.

    Args:
        detections: list from yolo_detector.detect()
        target: specific class to count (None = all classes)

    Returns:
        dict with total, target_count, breakdown
    """
    if not detections:
        return {
            "total": 0,
            "target_count": 0,
            "breakdown": {},
        }

    # Count per class
    breakdown = {}
    for d in detections:
        cls = d["object_class"]
        breakdown[cls] = breakdown.get(cls, 0) + 1

    target_count = breakdown.get(target, 0) if target else len(detections)

    return {
        "total": len(detections),
        "target_count": target_count,
        "breakdown": breakdown,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    # Simulated YOLO output
    fake_detections = [
        {"object_class": "person", "confidence": 0.92, "bbox": [10, 20, 100, 200]},
        {"object_class": "person", "confidence": 0.88, "bbox": [150, 30, 250, 210]},
        {"object_class": "car", "confidence": 0.85, "bbox": [300, 100, 500, 300]},
        {"object_class": "person", "confidence": 0.76, "bbox": [400, 50, 480, 220]},
        {"object_class": "dog", "confidence": 0.71, "bbox": [50, 300, 150, 400]},
    ]

    print("--- count() ---")
    print(f"All objects: {count(fake_detections)}")
    print(f"Persons:     {count(fake_detections, 'person')}")
    print(f"Cars:        {count(fake_detections, 'car')}")
    print(f"Dogs:        {count(fake_detections, 'dog')}")
    print(f"Cats:        {count(fake_detections, 'cat')}")

    print("\n--- count_with_details() ---")
    details = count_with_details(fake_detections, "person")
    print(f"Total: {details['total']}")
    print(f"Persons: {details['target_count']}")
    print(f"Breakdown: {details['breakdown']}")

    print("\n--- Empty input ---")
    print(f"Empty list: {count([])}")
    print(f"None target: {count(fake_detections, None)}")