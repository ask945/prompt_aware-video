"""
Motion Detection Module

Simple, stateless motion detection between two frames.
No internal state — analyzer.py manages prev_frame externally.

Interface:
    detect_motion(frame, prev_frame) → { detected, motion_percentage, confidence }
"""

import cv2
import numpy as np


def detect_motion(frame: np.ndarray, prev_frame: np.ndarray, threshold: float = 2.0) -> dict:
    """
    Detect motion between two consecutive frames.

    Args:
        frame: current frame (BGR)
        prev_frame: previous frame (BGR)
        threshold: motion percentage above which motion is "detected"

    Returns:
        dict with:
            detected: bool
            motion_percentage: float (0-100)
            confidence: float (0-1)
    """
    try:
        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)
        gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)

        diff = cv2.absdiff(gray1, gray2)
        _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        # Clean up noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        motion_pct = (cv2.countNonZero(mask) / mask.size) * 100
        confidence = min(round(motion_pct / 100, 3), 1.0)

        return {
            "detected": motion_pct > threshold,
            "motion_percentage": round(motion_pct, 2),
            "confidence": confidence,
        }

    except Exception as e:
        return {
            "detected": False,
            "motion_percentage": 0.0,
            "confidence": 0.0,
            "error": str(e),
        }


def detect_scene_change(frame: np.ndarray, prev_frame: np.ndarray, threshold: float = 20.0) -> dict:
    """
    Detect scene change (cut) between two frames.
    Higher threshold than regular motion — catches only big visual shifts.

    Args:
        frame: current frame (BGR)
        prev_frame: previous frame (BGR)
        threshold: percentage threshold for scene change

    Returns:
        dict with:
            detected: bool
            change_magnitude: float (0-100)
    """
    result = detect_motion(frame, prev_frame, threshold=threshold)

    return {
        "detected": result["detected"],
        "change_magnitude": result["motion_percentage"],
        "confidence": result["confidence"],
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    # Create test frames
    frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 100

    # No motion
    frame2 = frame1.copy()
    result = detect_motion(frame2, frame1)
    print(f"No motion:     detected={result['detected']}, pct={result['motion_percentage']}%")

    # Small motion
    frame3 = frame1.copy()
    frame3[200:250, 200:250] = 200
    result = detect_motion(frame3, frame1)
    print(f"Small motion:  detected={result['detected']}, pct={result['motion_percentage']}%")

    # Large motion
    frame4 = frame1.copy()
    frame4[100:400, 100:500] = 200
    result = detect_motion(frame4, frame1)
    print(f"Large motion:  detected={result['detected']}, pct={result['motion_percentage']}%")

    # Scene change
    frame5 = np.ones((480, 640, 3), dtype=np.uint8) * 50
    result = detect_scene_change(frame5, frame1)
    print(f"Scene change:  detected={result['detected']}, magnitude={result['change_magnitude']}%")