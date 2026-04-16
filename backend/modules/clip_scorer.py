"""
CLIP Visual Scoring Module

Zero-shot frame-to-text similarity using OpenCLIP.
Matches ANY natural language description against video frames.

Used as fallback when YOLO can't handle the query:
  - Actions: "person snatching chain", "lady falling"
  - Interactions: "thief contacting lady", "fight occurring"
  - Abstract concepts: "chaotic scene", "dangerous situation"
  - Objects not in COCO: "machete", "chain", "weapon"

Model: ViT-B-32 (~350MB, downloads on first run, cached after that)
Speed: ~1-2 sec/frame on CPU

Interface:
    score_frame(frame, query_text) → float (0.0 - 1.0)
    score_frames_batch(frames, query_text) → list[float]
    make_clip_prompt(raw_query) → str (visual description for CLIP)
"""

import logging
import re
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================
# QUERY → CLIP PROMPT TRANSFORMER
# Converts user questions into visual descriptions CLIP understands.
# "when does fight start" → "a photo of people fighting"
# "when does the man start running" → "a photo of a man running"
# ============================================================

# Words to strip — they add no visual meaning for CLIP
_STRIP_WORDS = {
    "when", "does", "did", "do", "the", "a", "an", "is", "are", "was",
    "were", "has", "have", "had", "will", "would", "could", "should",
    "first", "last", "start", "begin", "stop", "end",
    "appear", "appears", "appeared", "happen", "happens", "happened",
    "occur", "occurs", "occurred", "get", "gets", "got",
    "can", "you", "see", "find", "show", "me", "please",
    "what", "where", "how", "why", "which",
}


def make_clip_prompt(raw_query: str) -> str:
    """
    Transform a user query into a visual description for CLIP.

    CLIP was trained on image captions like "a photo of a dog running",
    not questions like "when does the dog start running?". This function
    strips question/temporal words and prepends "a photo of".

    Examples:
        "when does fight start"           → "a photo of fight"
        "when does the man start running" → "a photo of man running"
        "when does the chain get snatched"→ "a photo of chain snatched"
        "when does the woman fall"        → "a photo of woman fall"
        "describe the video"              → "a photo of video"
    """
    words = raw_query.lower().strip().rstrip("?!.").split()
    visual_words = [w for w in words if w not in _STRIP_WORDS]

    if not visual_words:
        # Fallback: use original query
        return f"a photo of {raw_query.lower().strip()}"

    phrase = " ".join(visual_words)
    prompt = f"a photo of {phrase}"
    logger.info(f"CLIP prompt: '{raw_query}' → '{prompt}'")
    return prompt


# ============================================================
# LAZY-LOADED CLIP MODEL
# ============================================================

_model = None
_preprocess = None
_tokenizer = None


def _get_model():
    """Load OpenCLIP model. Lazy loaded on first call."""
    global _model, _preprocess, _tokenizer

    if _model is None:
        try:
            import open_clip
            import torch

            model_name = "ViT-B-32"
            pretrained = "laion2b_s34b_b79k"

            logger.info(f"Loading CLIP model: {model_name} ({pretrained})...")
            _model, _, _preprocess = open_clip.create_model_and_transforms(
                model_name, pretrained=pretrained
            )
            _tokenizer = open_clip.get_tokenizer(model_name)
            _model.eval()

            logger.info("CLIP model loaded successfully")

        except ImportError:
            raise RuntimeError("Install open-clip-torch: pip install open-clip-torch")

    return _model, _preprocess, _tokenizer


# ============================================================
# FRAME SCORING
# ============================================================

def score_frame(frame: np.ndarray, query_text: str) -> float:
    """
    Score a single frame against a text query using CLIP.

    Args:
        frame: BGR image (numpy array from OpenCV)
        query_text: natural language description to match

    Returns:
        Similarity score 0.0 - 1.0 (higher = better match)
        Typical range: 0.15-0.35 for real matches.
    """
    try:
        import torch
        from PIL import Image

        model, preprocess, tokenizer = _get_model()

        # Convert BGR (OpenCV) → RGB (PIL)
        rgb = frame[:, :, ::-1]
        pil_image = Image.fromarray(rgb)

        # Preprocess image and tokenize text
        image_input = preprocess(pil_image).unsqueeze(0)
        text_input = tokenizer([query_text])

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features = model.encode_text(text_input)

            # Normalize
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Cosine similarity
            similarity = (image_features @ text_features.T).item()

        return max(0.0, min(1.0, similarity))

    except Exception as e:
        logger.error(f"CLIP scoring failed: {e}")
        return 0.0


def score_frames_batch(frames: list[np.ndarray], query_text: str) -> list[float]:
    """
    Score multiple frames against a text query in one batch.
    More efficient than calling score_frame() repeatedly.

    Args:
        frames: list of BGR images (numpy arrays)
        query_text: natural language description

    Returns:
        list of similarity scores (same length as frames)
    """
    if not frames:
        return []

    try:
        import torch
        from PIL import Image

        model, preprocess, tokenizer = _get_model()

        # Preprocess all frames
        image_inputs = []
        for frame in frames:
            rgb = frame[:, :, ::-1]
            pil_image = Image.fromarray(rgb)
            image_inputs.append(preprocess(pil_image))

        image_batch = torch.stack(image_inputs)
        text_input = tokenizer([query_text])

        with torch.no_grad():
            image_features = model.encode_image(image_batch)
            text_features = model.encode_text(text_input)

            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            similarities = (image_features @ text_features.T).squeeze(-1)

        return [max(0.0, min(1.0, s.item())) for s in similarities]

    except Exception as e:
        logger.error(f"CLIP batch scoring failed: {e}")
        return [0.0] * len(frames)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import cv2
    import sys

    print("Loading CLIP model (first run downloads ~350MB)...")
    model, preprocess, tokenizer = _get_model()
    print("Model loaded.\n")

    # Test with synthetic frame
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.putText(frame, "Hello", (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)

    queries = [
        "a gray image with text",
        "a person walking on the street",
        "a red car driving fast",
    ]

    print("--- Scoring synthetic frame ---")
    for q in queries:
        score = score_frame(frame, q)
        print(f"  '{q}' → {score:.4f}")

    # Test batch
    print("\n--- Batch scoring ---")
    scores = score_frames_batch([frame, frame], "gray image")
    print(f"  Batch scores: {[f'{s:.4f}' for s in scores]}")

    # Test with real image if provided
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        if img is not None:
            print(f"\n--- Testing on {sys.argv[1]} ---")
            test_queries = [
                "a person standing on a road",
                "a vehicle on the street",
                "someone fighting",
                "a peaceful empty scene",
            ]
            for q in test_queries:
                score = score_frame(img, q)
                print(f"  '{q}' → {score:.4f}")
