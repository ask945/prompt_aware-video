"""
Config — Centralized settings for the entire backend.

All thresholds, paths, and model configs in one place.
Import anywhere: from config import settings
"""

import os
from pathlib import Path


class Settings:

    # ─── Paths ───
    BASE_DIR = Path(__file__).resolve().parent
    TEMP_DIR = BASE_DIR / "temp"
    FRAMES_DIR = BASE_DIR / "frames"

    # ─── Cloudinary ───
    CLOUDINARY_NAME = os.getenv("CLOUDINARY_NAME", "")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

    # ─── YOLO ───
    YOLO_MODEL = "yolov8n.pt"
    YOLO_CONFIDENCE = 0.5
    YOLO_DEVICE = "cpu"

    # ─── Color Detection ───
    COLOR_MIN_AREA_PCT = 0.5

    # ─── Motion Detection ───
    MOTION_THRESHOLD = 2.0

    # ─── OCR ───
    OCR_MIN_CONFIDENCE = 30

    # ─── Frame Sampling ───
    SCENE_CHANGE_THRESHOLD = 30.0
    DIRECT_SEEK_WINDOW = 5
    BINARY_SEARCH_MAX_ITERATIONS = 20

    # ─── Upload Limits ───
    MAX_VIDEO_SIZE_MB = 100
    ALLOWED_FORMATS = {"mp4", "avi", "mov", "mkv", "webm"}

    # ─── Server ───
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    def __init__(self):
        self.TEMP_DIR.mkdir(exist_ok=True)
        self.FRAMES_DIR.mkdir(exist_ok=True)


settings = Settings()