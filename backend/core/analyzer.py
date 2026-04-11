"""
Analyzer Module — The Orchestrator

Uses SQLAlchemy SessionLocal directly for DB operations
since this runs in a background task (outside request lifecycle).

Called from: routes/analyze.py via BackgroundTasks
"""

import time
import logging
from datetime import datetime

from core.frame_selector import sample, get_sampling_stats
from modules.yolo_detector import detect
from modules.color_detector import detect_color, detect_color_full_frame
from modules.ocr_extractor import extract_text
from modules.motion_detector import detect_motion
from modules.counter import count
from utils.video_utils import download_from_cloudinary, save_frame, cleanup_temp
from utils.helpers import format_timestamp
from database.db import SessionLocal
from database.schemas import Job, Detection

logger = logging.getLogger(__name__)


# ============================================================
# DB HELPERS — background task can't use Depends(get_db)
# so we manage sessions manually
# ============================================================

def _update_progress(job_id: str, **kwargs):
    """Update job progress in DB."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            for key, val in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, val)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update progress for {job_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _complete_job(job_id: str, found: bool, confidence: float, detections: list, stats: dict):
    """Mark job as complete and save detections."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "complete"
        job.result_found = found
        job.confidence = confidence
        job.time_taken = stats.get("time_taken")
        job.total_frames = stats.get("total_frames")
        job.frames_processed = stats.get("frames_processed")
        job.completed_at = datetime.utcnow()

        for d in detections:
            bbox = d.get("bbox")
            det = Detection(
                job_id=job_id,
                frame_number=d["frame_number"],
                timestamp=d["timestamp"],
                timestamp_fmt=d["timestamp_fmt"],
                object_class=d.get("object_class"),
                color=d.get("color"),
                confidence=d["confidence"],
                bbox_x1=bbox[0] if bbox else None,
                bbox_y1=bbox[1] if bbox else None,
                bbox_x2=bbox[2] if bbox else None,
                bbox_y2=bbox[3] if bbox else None,
                frame_url=d.get("frame_image"),
                text_content=d.get("text_content"),
            )
            db.add(det)

        db.commit()
        logger.info(f"Job {job_id} completed: {len(detections)} detections")

    except Exception as e:
        logger.error(f"Failed to complete job {job_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _fail_job(job_id: str, error: str):
    """Mark job as failed."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = error
            job.completed_at = datetime.utcnow()
            db.commit()
        logger.error(f"Job {job_id} failed: {error}")
    except Exception as e:
        logger.error(f"Failed to mark job {job_id} as failed: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================
# MAIN ANALYSIS PIPELINE
# ============================================================

def run_analysis(job_id: str, video_url: str, query_data: dict, strategy_config: dict):
    """
    Main analysis pipeline. Runs as a background task.

    Args:
        job_id: UUID string
        video_url: Cloudinary video URL
        query_data: from prompt_interpreter.parse()
        strategy_config: from strategy_selector.select()
    """
    local_path = None
    start_time = time.time()

    try:
        # ─── Step 1: Download video ───
        logger.info(f"Job {job_id}: downloading video")
        local_path = download_from_cloudinary(video_url)
        _update_progress(job_id, progress=10)

        # ─── Step 2: Prepare config ───
        strategy_config["timestamp"] = query_data.get("timestamp")

        # ─── Step 3: Prepare detect_fn for binary search ───
        detect_fn = None
        if strategy_config["strategy"] == "binary_search":
            target = query_data.get("target")
            detect_fn = lambda frame: len(detect(frame, target)) > 0

        # ─── Step 4: Sample frames ───
        logger.info(f"Job {job_id}: sampling frames with strategy={strategy_config['strategy']}")
        selected_frames = sample(
            video_path=local_path,
            strategy_config=strategy_config,
            detect_fn=detect_fn,
        )

        stats = get_sampling_stats(local_path, selected_frames)
        total_selected = len(selected_frames)
        logger.info(f"Job {job_id}: selected {total_selected} of {stats['total_frames']} frames")

        _update_progress(
            job_id,
            progress=30,
            total_frames=stats["total_frames"],
        )

        # ─── Step 5: Analyze selected frames ───
        detections = []
        prev_frame = None
        frames_analyzed = 0

        for i, frame_info in enumerate(selected_frames):
            frame = frame_info["frame"]
            frame_num = frame_info["frame_number"]
            timestamp = frame_info["timestamp"]

            result = _analyze_single_frame(
                frame=frame,
                prev_frame=prev_frame,
                frame_num=frame_num,
                timestamp=timestamp,
                query_data=query_data,
                modules=strategy_config["modules"],
            )

            frames_analyzed += 1

            if result:
                result["frame_image"] = save_frame(frame, frame_num)
                detections.append(result)

                # ─── Step 6: Early termination ───
                if strategy_config["early_stop"]:
                    if result["confidence"] >= strategy_config["confidence_threshold"]:
                        logger.info(
                            f"Job {job_id}: early stop at frame {frame_num} "
                            f"(conf={result['confidence']})"
                        )
                        break

            prev_frame = frame

            # Update progress (30% → 90%)
            if i % 5 == 0:  # update every 5 frames to reduce DB writes
                progress = 30 + int((i / max(total_selected, 1)) * 60)
                _update_progress(
                    job_id,
                    progress=progress,
                    frames_processed=frames_analyzed,
                )

        # ─── Step 7: Build stats ───
        total_time = round(time.time() - start_time, 2)

        best_confidence = 0.0
        if detections:
            best_confidence = max(d["confidence"] for d in detections)

        final_stats = {
            "total_frames": stats["total_frames"],
            "frames_selected": stats["frames_selected"],
            "frames_processed": frames_analyzed,
            "reduction_percent": stats["reduction_percent"],
            "time_taken": total_time,
            "fps": stats["fps"],
            "duration": stats["duration"],
        }

        # ─── Step 8: Save results ───
        _complete_job(
            job_id=job_id,
            found=len(detections) > 0,
            confidence=best_confidence,
            detections=detections,
            stats=final_stats,
        )

    except Exception as e:
        _fail_job(job_id, error=str(e))

    finally:
        if local_path:
            cleanup_temp(local_path)


# ============================================================
# SINGLE FRAME ANALYSIS
# ============================================================

def _analyze_single_frame(frame, prev_frame, frame_num, timestamp, query_data, modules) -> dict | None:
    """Run only the required CV modules on one frame."""

    target = query_data.get("target")
    attribute = query_data.get("attribute")

    # ── Motion check (gates everything for event detection) ──
    if "motion" in modules:
        if prev_frame is None:
            return None
        motion = detect_motion(frame, prev_frame)
        if not motion["detected"]:
            return None

    # ── YOLO object detection ──
    if "yolo" in modules:
        results = detect(frame, target)
        if not results:
            return None

        best = max(results, key=lambda d: d["confidence"])

        # Color check on detected object
        if "hsv" in modules and attribute:
            color = detect_color(frame, best["bbox"])
            if color != attribute:
                return None
            best["color"] = color

        # Count objects
        if "counter" in modules:
            best["count"] = count(results, target)

        return {
            "frame_number": frame_num,
            "timestamp": timestamp,
            "timestamp_fmt": format_timestamp(timestamp),
            "object_class": best["object_class"],
            "color": best.get("color"),
            "confidence": best["confidence"],
            "bbox": best["bbox"],
            "text_content": None,
            "count": best.get("count"),
        }

    # ── Color only (no YOLO) ──
    if "hsv" in modules and "yolo" not in modules:
        color_result = detect_color_full_frame(frame, attribute)
        if color_result and color_result["detected"]:
            return {
                "frame_number": frame_num,
                "timestamp": timestamp,
                "timestamp_fmt": format_timestamp(timestamp),
                "object_class": "color_region",
                "color": attribute,
                "confidence": color_result["confidence"],
                "bbox": color_result.get("bbox"),
                "text_content": None,
                "count": None,
            }
        return None

    # ── OCR only ──
    if "ocr" in modules:
        text = extract_text(frame)
        if text:
            return {
                "frame_number": frame_num,
                "timestamp": timestamp,
                "timestamp_fmt": format_timestamp(timestamp),
                "object_class": "text",
                "color": None,
                "confidence": 0.85,
                "bbox": None,
                "text_content": text,
                "count": None,
            }
        return None

    return None