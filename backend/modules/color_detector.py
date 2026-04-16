"""
Color Detection Module (HSV)

Two functions:
  detect_color(frame, bbox) → color name string
      Used by analyzer for object+color queries.
      Crops the bbox region, finds dominant color.

  detect_color_full_frame(frame, target_color) → dict
      Used by analyzer for color-only queries.
      Checks if target color exists anywhere in the frame.

Interface:
    detect_color(frame, bbox)                → "red" | "blue" | None
    detect_color_full_frame(frame, color)     → { detected, confidence, area_pct }
"""

import cv2
import numpy as np


# ============================================================
# HSV COLOR RANGES
# Red wraps around 0/180 in OpenCV HSV, so it has two ranges
# ============================================================

# ============================================================
# SIMILAR COLORS — for fuzzy matching in real-world video
# "white" in CCTV often looks "gray", "silver" looks "white", etc.
# ============================================================

SIMILAR_COLORS = {
    "white":  {"white", "gray", "grey", "silver"},
    "gray":   {"gray", "grey", "white", "silver"},
    "grey":   {"gray", "grey", "white", "silver"},
    "silver": {"silver", "gray", "grey", "white"},
    "black":  {"black"},
    "red":    {"red", "maroon"},
    "maroon": {"maroon", "red"},
    "blue":   {"blue", "navy"},
    "navy":   {"navy", "blue"},
    "green":  {"green", "teal"},
    "teal":   {"teal", "green", "cyan"},
    "orange": {"orange", "yellow"},
    "yellow": {"yellow", "orange", "golden"},
    "golden": {"golden", "yellow", "orange"},
    "pink":   {"pink", "magenta"},
    "magenta":{"magenta", "pink"},
    "purple": {"purple", "violet"},
    "violet": {"violet", "purple"},
}


def is_color_match(detected: str, wanted: str) -> bool:
    """Check if detected color matches wanted color (with fuzzy similarity)."""
    if detected == wanted:
        return True
    similar = SIMILAR_COLORS.get(wanted, {wanted})
    return detected in similar


COLOR_RANGES = {
    "red":    [(np.array([0, 100, 100]),   np.array([10, 255, 255])),
               (np.array([170, 100, 100]), np.array([180, 255, 255]))],
    "blue":   [(np.array([100, 100, 100]), np.array([130, 255, 255]))],
    "green":  [(np.array([40, 100, 100]),  np.array([80, 255, 255]))],
    "yellow": [(np.array([20, 100, 100]),  np.array([35, 255, 255]))],
    "orange": [(np.array([10, 100, 100]),  np.array([20, 255, 255]))],
    "purple": [(np.array([130, 100, 100]), np.array([160, 255, 255]))],
    "pink":   [(np.array([160, 100, 100]), np.array([170, 255, 255]))],
    "cyan":   [(np.array([80, 100, 100]),  np.array([100, 255, 255]))],
    "white":  [(np.array([0, 0, 140]),     np.array([180, 50, 255]))],
    "black":  [(np.array([0, 0, 0]),       np.array([180, 255, 40]))],
    "gray":   [(np.array([0, 0, 60]),      np.array([180, 50, 160]))],
    "grey":   [(np.array([0, 0, 60]),      np.array([180, 50, 160]))],
    "brown":  [(np.array([10, 100, 50]),   np.array([20, 255, 150]))],
    "maroon": [(np.array([0, 100, 50]),    np.array([10, 255, 150]))],
    "navy":   [(np.array([100, 100, 50]),  np.array([130, 255, 150]))],
    "teal":   [(np.array([80, 100, 80]),   np.array([100, 255, 200]))],
    "golden": [(np.array([15, 100, 150]),  np.array([30, 255, 255]))],
    "silver": [(np.array([0, 0, 150]),     np.array([180, 30, 220]))],
    "beige":  [(np.array([15, 30, 180]),   np.array([30, 80, 255]))],
    "violet": [(np.array([130, 100, 100]), np.array([160, 255, 255]))],
    "magenta":[(np.array([150, 100, 100]), np.array([170, 255, 255]))],
}


def _hsv_to_color_name(h: int, s: int, v: int) -> str:
    """
    Convert a single HSV pixel to the closest color name.
    Used to identify dominant color in a region.

    Tuned for real-world video (CCTV, outdoor, compressed footage)
    where "white" objects rarely hit pure V=255.
    """
    # Low saturation → achromatic (black, white, gray)
    if s < 50:
        if v < 40:
            return "black"
        elif v > 140:
            return "white"
        elif v < 90:
            return "black"
        else:
            return "gray"

    # Medium-low saturation + high value → still white-ish
    # Catches slightly tinted whites (common in video compression)
    if s < 80 and v > 170:
        return "white"

    # Chromatic — classify by hue
    if h < 5 or h > 170:
        return "red"
    elif 5 <= h < 15:
        return "orange"
    elif 15 <= h < 35:
        return "yellow"
    elif 35 <= h < 80:
        return "green"
    elif 80 <= h < 100:
        return "cyan"
    elif 100 <= h < 130:
        return "blue"
    elif 130 <= h < 160:
        return "purple"
    else:
        return "pink"


def _get_color_votes(frame: np.ndarray, bbox: list | tuple) -> dict:
    """
    Internal helper. Crops center 60% of bbox, downsamples, classifies
    every pixel by HSV, returns {color_name: pixel_count} dict.

    Returns empty dict on failure.
    """
    try:
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        # Clamp to frame bounds
        h, w = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return {}

        # Shrink to center 60% to avoid edges (tires, shadows, background)
        bw, bh = x2 - x1, y2 - y1
        margin_x, margin_y = int(bw * 0.2), int(bh * 0.2)
        cx1 = x1 + margin_x
        cy1 = y1 + margin_y
        cx2 = x2 - margin_x
        cy2 = y2 - margin_y

        if cx2 <= cx1 or cy2 <= cy1:
            cx1, cy1, cx2, cy2 = x1, y1, x2, y2

        region = frame[cy1:cy2, cx1:cx2]

        # Downsample to max 50x50 for speed
        rh, rw = region.shape[:2]
        if rh > 50 or rw > 50:
            region = cv2.resize(region, (min(rw, 50), min(rh, 50)))

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        pixels = hsv.reshape(-1, 3)
        votes = {}
        for px in pixels:
            color_name = _hsv_to_color_name(int(px[0]), int(px[1]), int(px[2]))
            votes[color_name] = votes.get(color_name, 0) + 1

        return votes

    except Exception:
        return {}


def detect_color(frame: np.ndarray, bbox: list | tuple) -> str | None:
    """
    Detect the dominant color inside a bounding box region.
    Returns the single most common color name, or None on failure.
    """
    votes = _get_color_votes(frame, bbox)
    if not votes:
        return None
    return max(votes, key=votes.get)


def detect_color_top_n(frame: np.ndarray, bbox: list | tuple, n: int = 2) -> list[str]:
    """
    Return the top-N dominant colors inside a bounding box.
    Sorted by pixel count descending. Empty list on failure.
    """
    votes = _get_color_votes(frame, bbox)
    if not votes:
        return []
    return sorted(votes, key=votes.get, reverse=True)[:n]


def detect_color_full_frame(frame: np.ndarray, target_color: str, min_area_pct: float = 0.5) -> dict | None:
    """
    Check if a specific color exists anywhere in the full frame.

    Used for color-only queries:
        "Find red objects" → scan entire frame for red regions

    Args:
        frame: full BGR image
        target_color: color name to search for ("red", "blue", etc.)
        min_area_pct: minimum percentage of frame area to count as detected

    Returns:
        dict with detected, confidence, area_pct or None on failure
    """
    target = target_color.lower()

    if target not in COLOR_RANGES:
        return None

    try:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Build mask from all ranges for this color
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lower, upper in COLOR_RANGES[target]:
            range_mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.bitwise_or(mask, range_mask)

        # Clean up noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Calculate area percentage
        area_pct = (cv2.countNonZero(mask) / mask.size) * 100
        detected = area_pct > min_area_pct
        confidence = min(round(area_pct / 50, 3), 1.0)  # 50% area = 1.0 confidence

        # Find bounding box of largest color region
        bbox = None
        if detected:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest)
                bbox = [x, y, x + w, y + h]

        return {
            "detected": detected,
            "confidence": round(confidence, 3),
            "area_pct": round(area_pct, 2),
            "color": target,
            "bbox": bbox,
        }

    except Exception:
        return None


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    # Create test frame with colored regions
    frame = np.zeros((400, 600, 3), dtype=np.uint8)
    frame[50:150, 50:150] = [0, 0, 255]     # Red (BGR)
    frame[50:150, 200:300] = [0, 255, 0]     # Green (BGR)
    frame[50:150, 350:450] = [255, 0, 0]     # Blue (BGR)
    frame[200:300, 50:150] = [0, 255, 255]   # Yellow (BGR)
    frame[200:300, 200:300] = [255, 255, 255] # White (BGR)

    # Test detect_color with bbox (what color is in this region?)
    print("--- detect_color (bbox → color name) ---")
    print(f"Red region [50,50,150,150]:    {detect_color(frame, [50, 50, 150, 150])}")
    print(f"Green region [200,50,300,150]: {detect_color(frame, [200, 50, 300, 150])}")
    print(f"Blue region [350,50,450,150]:  {detect_color(frame, [350, 50, 450, 150])}")
    print(f"Yellow region [50,200,150,300]:{detect_color(frame, [50, 200, 150, 300])}")
    print(f"White region [200,200,300,300]:{detect_color(frame, [200, 200, 300, 300])}")
    print(f"Black region [400,300,500,400]:{detect_color(frame, [400, 300, 500, 400])}")

    # Test detect_color_full_frame (is red anywhere in the frame?)
    print("\n--- detect_color_full_frame (is color in frame?) ---")
    print(f"Red in frame:    {detect_color_full_frame(frame, 'red')}")
    print(f"Green in frame:  {detect_color_full_frame(frame, 'green')}")
    print(f"Purple in frame: {detect_color_full_frame(frame, 'purple')}")

    # Test invalid inputs
    print("\n--- Edge cases ---")
    print(f"Invalid bbox:  {detect_color(frame, [0, 0, 0, 0])}")
    print(f"Unknown color: {detect_color_full_frame(frame, 'magentaish')}")