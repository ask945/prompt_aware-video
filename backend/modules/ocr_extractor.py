"""
OCR Text Extraction Module

Extracts readable text from video frames using EasyOCR.
Pure Python — no system binary needed. Deploys anywhere.

Supports English + many other scripts (Malayalam, Hindi, etc.)
Model downloads on first run (~100MB), cached after that.

Interface:
    extract_text(frame) → str or None
    extract_text_with_confidence(frame) → dict or None
"""

import logging
import numpy as np
import re

logger = logging.getLogger(__name__)

# ============================================================
# LAZY-LOADED EASYOCR READER
# Loaded once on first call, reused across all frames.
# ============================================================

_reader = None


def _get_reader():
    """Load EasyOCR reader. Lazy loaded on first call."""
    global _reader
    if _reader is None:
        try:
            import easyocr
            # English + Malayalam (add more languages as needed)
            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            logger.info("EasyOCR reader loaded (languages: en)")
        except ImportError:
            logger.error("easyocr not installed. Run: pip install easyocr")
            raise RuntimeError("Install easyocr: pip install easyocr")
    return _reader


# ============================================================
# GIBBERISH FILTER
# ============================================================

def is_gibberish(text: str) -> bool:
    """
    Filter out OCR garbage.
    Returns True if text is likely gibberish.
    """
    if len(text) < 2:
        return True

    # Count actual letters/digits vs special chars
    alphanum = sum(1 for c in text if c.isalnum())
    total = len(text.replace(" ", ""))

    if total == 0:
        return True

    # If less than 40% alphanumeric, likely garbage
    if alphanum / total < 0.4:
        return True

    # Reject strings that are just repeated characters
    if len(set(text.replace(" ", ""))) < 3 and len(text) > 3:
        return True

    return False


# ============================================================
# MAIN EXTRACTION FUNCTIONS
# ============================================================

def extract_text(frame: np.ndarray) -> str | None:
    """
    Extract all readable text from a video frame as one combined string.
    Use extract_text_regions() for per-region results.

    Returns:
        Combined text string, or None if no text found
    """
    regions = extract_text_regions(frame)
    if not regions:
        return None
    combined = " ".join(r["text"] for r in regions)
    combined = re.sub(r"\s+", " ", combined).strip()
    return combined


def extract_text_regions(frame: np.ndarray) -> list[dict]:
    """
    Extract text from a video frame, returning each text region separately
    with its bounding box and confidence.

    Returns:
        list of {text, confidence, bbox} dicts. Empty list if nothing found.
        bbox is [x1, y1, x2, y2].
    """
    try:
        reader = _get_reader()

        results = reader.readtext(frame, detail=1, paragraph=False)

        if not results:
            logger.debug("OCR found no text regions")
            return []

        regions = []
        for bbox_pts, text, conf in results:
            text = text.strip()
            if conf >= 0.3 and text and not is_gibberish(text):
                # EasyOCR bbox is 4 corner points [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                # Convert to [x1, y1, x2, y2]
                xs = [int(p[0]) for p in bbox_pts]
                ys = [int(p[1]) for p in bbox_pts]
                bbox = [min(xs), min(ys), max(xs), max(ys)]

                regions.append({
                    "text": text,
                    "confidence": round(conf, 3),
                    "bbox": bbox,
                })

        if regions:
            logger.info(f"OCR found {len(regions)} region(s): {[r['text'][:30] for r in regions]}")

        return regions

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return []


def extract_text_with_confidence(frame: np.ndarray) -> dict | None:
    """
    Extract text with per-word confidence scores.

    Args:
        frame: BGR image (numpy array)

    Returns:
        dict with text, confidence, word_count or None
    """
    try:
        reader = _get_reader()

        results = reader.readtext(frame, detail=1, paragraph=False)

        if not results:
            return None

        words = []
        confidences = []

        for bbox, text, conf in results:
            text = text.strip()
            if conf >= 0.3 and text and not is_gibberish(text):
                words.append(text)
                confidences.append(conf)

        if not words:
            return None

        combined = " ".join(words)
        avg_conf = round(sum(confidences) / len(confidences), 3)

        return {
            "text": combined,
            "confidence": avg_conf,
            "word_count": len(words),
        }

    except Exception as e:
        logger.error(f"OCR with confidence failed: {e}")
        return None


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import cv2

    print("Loading EasyOCR reader (first run downloads model ~100MB)...")
    reader = _get_reader()
    print("Reader loaded.\n")

    # Create test frame with text
    frame = np.ones((200, 400, 3), dtype=np.uint8) * 255
    cv2.putText(frame, "Hello World", (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

    # Test simple extraction
    text = extract_text(frame)
    print(f"Simple: '{text}'")

    # Test with confidence
    result = extract_text_with_confidence(frame)
    print(f"Detailed: {result}")

    # Test empty frame (should return None)
    empty = np.ones((200, 400, 3), dtype=np.uint8) * 255
    text_empty = extract_text(empty)
    print(f"Empty frame: {text_empty}")

    # Test gibberish filter
    print(f"\nGibberish tests:")
    print(f"  '|||~~' → {is_gibberish('|||~~')}")
    print(f"  'Hello' → {is_gibberish('Hello')}")
    print(f"  'aaaa'  → {is_gibberish('aaaa')}")
    print(f"  'EXIT'  → {is_gibberish('EXIT')}")

    # Test with image file if provided
    import sys
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        if img is not None:
            print(f"\n--- Testing on {sys.argv[1]} ---")
            text = extract_text(img)
            print(f"Text: '{text}'")
            result = extract_text_with_confidence(img)
            print(f"Detailed: {result}")
        else:
            print(f"Cannot read image: {sys.argv[1]}")
