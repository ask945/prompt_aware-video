import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import cloudinary.uploader
from sqlalchemy.orm import Session

from auth import get_current_user
from database.db import get_db
from database.service import add_video

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".webm"}
MAX_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/api/upload")
async def upload_video(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported video format. Use MP4, AVI, MOV, or WebM.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp_path = tmp.name
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise HTTPException(400, "File too large. Maximum size is 100MB.")
                tmp.write(chunk)

        result = cloudinary.uploader.upload(
            tmp_path,
            resource_type="video",
            folder="prompt-aware-video",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Cloudinary upload failed: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return add_video(db, current_user["id"], {
        "filename": file.filename,
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "duration": result.get("duration"),
        "width": result.get("width"),
        "height": result.get("height"),
        "format": result.get("format"),
        "bytes": result.get("bytes"),
    })
