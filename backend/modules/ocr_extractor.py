"""
OCR Text Extraction Module

Extracts readable text from video frames using Tesseract OCR.
Stateless — no internal state between calls.

Interface:
    extract_text(frame) → str or None
"""

import cv2
import numpy as np
import re

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def preprocess(frame: np.ndarray) -> np.ndarray:
    """
    Preprocess frame for better OCR accuracy.
    Grayscale → threshold → denoise → upscale if small.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold handles varying lighting better
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # Denoise
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)

    # Upscale small images (OCR works better on larger text)
    h, w = denoised.shape
    if w < 300 or h < 300:
        scale = max(2, 300 // min(w, h))
        denoised = cv2.resize(denoised, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)

    return denoised


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


def extract_text(frame: np.ndarray) -> str | None:
    """
    Extract readable text from a video frame.

    Args:
        frame: BGR image (numpy array)

    Returns:
        Extracted text string, or None if no text found
    """
    if not TESSERACT_AVAILABLE:
        return None

    try:
        processed = preprocess(frame)

        # Run Tesseract
        raw_text = pytesseract.image_to_string(processed, config="--psm 6")

        # Clean up
        text = raw_text.strip()
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        if not text or is_gibberish(text):
            return None

        return text

    except Exception:
        return None


def extract_text_with_confidence(frame: np.ndarray) -> dict | None:
    """
    Extract text with per-word confidence scores.
    Used when analyzer needs confidence data.

    Args:
        frame: BGR image (numpy array)

    Returns:
        dict with text, confidence, word_count or None
    """
    if not TESSERACT_AVAILABLE:
        return None

    try:
        processed = preprocess(frame)

        data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)

        words = []
        confidences = []

        for i in range(len(data["text"])):
            word = data["text"][i].strip()
            conf = int(data["conf"][i])

            if word and conf > 30 and not is_gibberish(word):
                words.append(word)
                confidences.append(conf / 100.0)

        if not words:
            return None

        text = " ".join(words)
        avg_conf = round(sum(confidences) / len(confidences), 3)

        return {
            "text": text,
            "confidence": avg_conf,
            "word_count": len(words),
        }

    except Exception:
        return None


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    if not TESSERACT_AVAILABLE:
        print("pytesseract not installed. Run: pip install pytesseract")
        print("Also install Tesseract binary: sudo apt install tesseract-ocr")
        exit(1)

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