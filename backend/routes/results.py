"""
Results Route — GET /api/results/{job_id}

Frontend polls this every 2 seconds until status is 'complete' or 'failed'.
Protected by auth — users can only see their own jobs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database.db import get_db
from database.schemas import Job, Detection
import logging
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/api/results/{job_id}")
async def get_results(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analysis results or progress for a job."""

    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user["id"],
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # ─── Processing ───
    if job.status == "processing":
        return {
            "job_id": str(job.id),
            "status": "processing",
            "progress": job.progress or 0,
            "frames_processed": job.frames_processed or 0,
            "total_frames": job.total_frames or 0,
            "strategy": job.strategy,
            "modules": job.modules.split(",") if job.modules else [],
            "intent": job.intent,
            "target": job.target,
        }

    # ─── Failed ───
    if job.status == "failed":
        return {
            "job_id": str(job.id),
            "status": "failed",
            "error": job.error or "Unknown error",
        }

    # ─── Complete ───
    detections = (
        db.query(Detection)
        .filter(Detection.job_id == job.id)
        .order_by(Detection.confidence.desc())
        .all()
    )

    formatted_detections = []
    for d in detections:
        bbox = None
        if d.bbox_x1 is not None:
            bbox = [d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2]

        formatted_detections.append({
            "frame_number": d.frame_number,
            "timestamp": d.timestamp,
            "timestamp_fmt": d.timestamp_fmt,
            "object_class": d.object_class,
            "color": d.color,
            "confidence": d.confidence,
            "bbox": bbox,
            "frame_url": d.frame_url,
            "text_content": d.text_content,
        })
    
    result = {
        "job_id": str(job.id),
        "status": "complete",
        "found": job.result_found or False,
        "confidence": job.confidence or 0.0,
        "detection_count": len(formatted_detections),
        "detections": formatted_detections,
        "stats": {
            "total_frames": job.total_frames,
            "frames_processed": job.frames_processed,
            "time_taken": job.time_taken,
            "strategy": job.strategy,
            "modules": job.modules.split(",") if job.modules else [],
            "intent": job.intent,
            "target": job.target,
            "attribute": job.attribute,
            "temporal_scope": job.temporal_scope,
        },
    }

    logger.info(
        "Job %s complete — found: %s, confidence: %.2f, detections: %d, "
        "frames: %s/%s, time: %ss, strategy: %s, modules: %s, "
        "intent: %s, target: %s, attribute: %s, scope: %s",
        result["job_id"],
        result["found"],
        result["confidence"],
        result["detection_count"],
        result["stats"]["frames_processed"],
        result["stats"]["total_frames"],
        result["stats"]["time_taken"],
        result["stats"]["strategy"],
        result["stats"]["modules"],
        result["stats"]["intent"],
        result["stats"]["target"],
        result["stats"]["attribute"],
        result["stats"]["temporal_scope"],
    )

    return result