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
from core.prompt_interpreter import YOLO_CLASSES, TARGET_ALIASES
from modules.yolo_detector import detect, track
from modules.color_detector import detect_color, detect_color_top_n, detect_color_full_frame, is_color_match
from modules.clip_scorer import score_frame, make_clip_prompt
from modules.ocr_extractor import extract_text, extract_text_regions
from modules.motion_detector import detect_motion
from modules.counter import count, count_unique
from utils.video_utils import download_from_cloudinary, cleanup_temp
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
        job.result_found = bool(found)
        job.confidence = float(confidence)
        job.time_taken = float(stats.get("time_taken") or 0)
        job.total_frames = int(stats.get("total_frames") or 0)
        job.frames_processed = int(stats.get("frames_processed") or 0)
        unique_count_val = stats.get("unique_count")
        if unique_count_val is not None:
            job.unique_count = int(unique_count_val)
        job.completed_at = datetime.utcnow()

        for d in detections:
            bbox = d.get("bbox")
            count_val = d.get("count")
            track_id_val = d.get("track_id")
            det = Detection(
                job_id=job_id,
                frame_number=int(d["frame_number"]),
                timestamp=float(d["timestamp"]),
                timestamp_fmt=d["timestamp_fmt"],
                object_class=d.get("object_class"),
                color=d.get("color"),
                confidence=float(d["confidence"]),
                bbox_x1=int(bbox[0]) if bbox else None,
                bbox_y1=int(bbox[1]) if bbox else None,
                bbox_x2=int(bbox[2]) if bbox else None,
                bbox_y2=int(bbox[3]) if bbox else None,
                count=int(count_val) if count_val is not None else None,
                track_id=int(track_id_val) if track_id_val is not None else None,
                frame_url=None,
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

        # ─── Step 2b: Check if CLIP should be used instead of YOLO ───
        target = query_data.get("target")
        intent = query_data.get("intent")
        raw_query = query_data.get("raw_query", "")
        resolved_target = TARGET_ALIASES.get(target, target) if target else None

        # Typo tolerance: only for intents that actually use YOLO.
        # Skip for OCR/scene/event (they don't rely on YOLO class lookup).
        # This prevents nonsense matches like "board" → "keyboard".
        YOLO_BASED_INTENTS = {"object", "object_color", "counting", "color"}
        if target and resolved_target not in YOLO_CLASSES and intent in YOLO_BASED_INTENTS:
            import difflib
            candidates = list(YOLO_CLASSES) + list(TARGET_ALIASES.keys())
            close = difflib.get_close_matches(target, candidates, n=1, cutoff=0.75)
            if close:
                corrected = close[0]
                resolved_target = TARGET_ALIASES.get(corrected, corrected)
                logger.info(
                    f"Job {job_id}: fuzzy-matched target '{target}' → '{resolved_target}'"
                )
                query_data["target"] = resolved_target
                target = resolved_target

        # Counting intent MUST use YOLO — CLIP can't count objects.
        # If no YOLO target, default to "person" (most common counting case).
        if intent == "counting":
            if not target or resolved_target not in YOLO_CLASSES:
                logger.info(
                    f"Job {job_id}: counting intent with unknown target '{target}', "
                    f"defaulting to 'person'"
                )
                query_data["target"] = "person"
                target = "person"
                resolved_target = "person"
            use_clip = False
        elif intent == "ocr":
            # OCR has its own dedicated pipeline (EasyOCR); don't hijack to CLIP
            use_clip = False
        else:
            use_clip = (
                # Target not in YOLO vocabulary (chain, machete, weapon, etc.)
                (target and resolved_target not in YOLO_CLASSES)
                # Event/scene intents — YOLO can't understand actions or scene descriptions
                or intent in ("event", "scene")
            )

        if use_clip:
            strategy_config["modules"] = ["clip"]
            logger.info(
                f"Job {job_id}: intent='{intent}', target='{target}' → using CLIP"
            )
        else:
            logger.info(
                f"Job {job_id}: intent='{intent}', target='{target}' → using YOLO pipeline"
            )

        # ─── Step 3: Prepare detect_fn for coarse-to-fine / binary search ───
        clip_prompt = make_clip_prompt(raw_query) if use_clip else None

        detect_fn = None
        if strategy_config["strategy"] in ("coarse_to_fine", "binary_search"):
            if "clip" in strategy_config["modules"]:
                # CLIP-based coarse pass: score frame against visual prompt
                CLIP_COARSE_THRESHOLD = 0.20
                detect_fn = lambda frame: score_frame(frame, clip_prompt) >= CLIP_COARSE_THRESHOLD
            else:
                attribute = query_data.get("attribute")
                low_conf = 0.3

                if attribute and "hsv" in strategy_config["modules"]:
                    def detect_fn(frame):
                        results = detect(frame, target, confidence=low_conf)
                        if not results:
                            return False
                        for r in results:
                            color = detect_color(frame, r["bbox"])
                            if is_color_match(color, attribute):
                                return True
                        return False
                else:
                    detect_fn = lambda frame: len(detect(frame, target, confidence=low_conf)) > 0

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

        # ─── Step 4b: Fallback to uniform if search found nothing ───
        if total_selected == 0 and strategy_config["strategy"] in ("coarse_to_fine", "binary_search"):
            logger.info(
                f"Job {job_id}: {strategy_config['strategy']} found no candidate regions, "
                f"falling back to uniform sampling"
            )
            fallback_config = {**strategy_config, "strategy": "uniform", "sample_rate": 1}
            selected_frames = sample(
                video_path=local_path,
                strategy_config=fallback_config,
                detect_fn=None,
            )
            stats = get_sampling_stats(local_path, selected_frames)
            total_selected = len(selected_frames)
            logger.info(f"Job {job_id}: uniform fallback selected {total_selected} of {stats['total_frames']} frames")

        _update_progress(
            job_id,
            progress=30,
            total_frames=stats["total_frames"],
        )

        # ─── Step 4c: Reset tracker + ensure sequential order for counting ───
        is_counting = intent == "counting" and "counter" in strategy_config["modules"]
        if is_counting:
            # Sort frames ascending by frame_number so tracker sees them in time order
            selected_frames = sorted(selected_frames, key=lambda f: f["frame_number"])
            # Prime tracker state reset with a dummy call on the first frame
            if selected_frames:
                try:
                    track(selected_frames[0]["frame"], target, confidence=0.25, reset=True)
                    logger.info(f"Job {job_id}: tracker reset for counting")
                except Exception as e:
                    logger.warning(f"Job {job_id}: tracker reset failed — {e}")

        # ─── Step 5: Analyze selected frames ───
        detections = []
        prev_frame = None
        frames_analyzed = 0
        tracked_ids_seen = set()  # aggregates unique track IDs for counting

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
                # OCR returns a list of regions; everything else returns a dict
                if isinstance(result, list):
                    detections.extend(result)
                    best_conf = max(r["confidence"] for r in result)
                else:
                    detections.append(result)
                    best_conf = result["confidence"]
                    # Aggregate ALL tracked IDs seen in this frame (not just best)
                    frame_ids = result.get("tracked_ids_in_frame") or []
                    tracked_ids_seen.update(frame_ids)

                # ─── Step 6: Early termination ───
                if strategy_config["early_stop"]:
                    if best_conf >= strategy_config["confidence_threshold"]:
                        logger.info(
                            f"Job {job_id}: early stop at frame {frame_num} "
                            f"(conf={best_conf})"
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

        # ─── Step 7: Filter and rank detections ───
        is_clip = "clip" in strategy_config.get("modules", [])

        if is_clip and detections:
            # CLIP scores are on a different scale (0.18-0.35 typical).
            # Use relative scoring: keep top frames that are significantly
            # above the mean score (the "spike" frames where the event happens).
            scores = [d["confidence"] for d in detections]
            mean_score = sum(scores) / len(scores)
            std_score = (sum((s - mean_score) ** 2 for s in scores) / len(scores)) ** 0.5
            # Keep frames scoring > mean + 0.5*std (the peaks)
            clip_threshold = mean_score + 0.5 * max(std_score, 0.005)
            detections = [d for d in detections if d["confidence"] >= clip_threshold]
            # Cap at top 10 most relevant frames
            detections.sort(key=lambda d: d["confidence"], reverse=True)
            detections = detections[:10]
            logger.info(
                f"Job {job_id}: CLIP relative filter — mean={mean_score:.4f}, "
                f"std={std_score:.4f}, threshold={clip_threshold:.4f}, "
                f"kept {len(detections)} detections"
            )
        else:
            # YOLO/HSV detections — absolute threshold
            MIN_RESULT_CONFIDENCE = 0.25
            detections = [d for d in detections if d["confidence"] >= MIN_RESULT_CONFIDENCE]

            # For object_color queries: if any frame had a real color match
            # (exact or top-2), drop the "no-match" detections that were
            # heavily penalized. They're just wrong-colored objects from
            # frames where no matching object existed.
            tiers = {d.get("_match_tier") for d in detections}
            if "exact" in tiers or "top-2" in tiers:
                before = len(detections)
                detections = [d for d in detections if d.get("_match_tier") != "no-match"]
                logger.info(
                    f"Job {job_id}: found real color matches — dropped "
                    f"{before - len(detections)} no-match detections"
                )

            # Strip internal-only field before DB save
            for d in detections:
                d.pop("_match_tier", None)

        # ─── Step 7b: Dedupe OCR detections by normalized text ───
        # Same sign text appears in every frame. Keep one instance per
        # unique text (the earliest occurrence, highest confidence).
        if intent == "ocr" and detections:
            import re as _re
            before = len(detections)
            seen = {}
            for d in detections:
                text = (d.get("text_content") or "").strip()
                if not text:
                    continue
                # Normalize: lowercase, strip non-alphanumerics for grouping
                # ("Edappone" == "(Edappone" == "lEdappone" → same group)
                key = _re.sub(r"[^a-z0-9]", "", text.lower())
                if len(key) < 2:
                    continue  # too short to dedupe meaningfully
                existing = seen.get(key)
                if existing is None:
                    seen[key] = d
                else:
                    # Keep highest confidence; if tied, keep earliest timestamp
                    if (d["confidence"], -d["timestamp"]) > (existing["confidence"], -existing["timestamp"]):
                        seen[key] = d
            detections = sorted(seen.values(), key=lambda d: d["timestamp"])
            logger.info(
                f"Job {job_id}: OCR deduped {before} → {len(detections)} "
                f"unique text regions"
            )

        # ─── Step 8: Build stats ───
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
            "unique_count": len(tracked_ids_seen) if tracked_ids_seen else None,
        }

        if is_counting:
            logger.info(
                f"Job {job_id}: counted {len(tracked_ids_seen)} unique "
                f"{target}(s) across {frames_analyzed} frames"
            )

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
    raw_query = query_data.get("raw_query", "")

    # ── CLIP zero-shot matching (handles actions, interactions, unknown objects) ──
    if "clip" in modules:
        CLIP_FINE_THRESHOLD = 0.18
        # Use pre-built clip_prompt from query_data if available, else build it
        clip_prompt = query_data.get("_clip_prompt") or make_clip_prompt(raw_query)
        query_data["_clip_prompt"] = clip_prompt  # cache for next frame
        similarity = score_frame(frame, clip_prompt)
        if similarity >= CLIP_FINE_THRESHOLD:
            return {
                "frame_number": frame_num,
                "timestamp": timestamp,
                "timestamp_fmt": format_timestamp(timestamp),
                "object_class": "clip_match",
                "color": None,
                "confidence": round(float(similarity), 3),
                "bbox": None,
                "text_content": None,
                "count": None,
            }
        return None

    # ── Motion check (gates everything for event detection) ──
    if "motion" in modules:
        if prev_frame is None:
            return None
        motion = detect_motion(frame, prev_frame)
        if not motion["detected"]:
            return None

    # ── YOLO object detection (with tracking for counting intent) ──
    if "yolo" in modules:
        use_tracking = "counter" in modules
        if use_tracking:
            results = track(frame, target, confidence=0.25)
        else:
            results = detect(frame, target)

        if not results:
            logger.info(f"Frame {frame_num}: YOLO found 0 '{target}'")
            return None

        # Color-aware candidate selection:
        # When a color is requested, iterate through ALL detected objects
        # and prefer ones where HSV color matches. Don't just pick the
        # highest-confidence detection (which might be a different-colored
        # object — e.g. a white van at 0.88 conf vs maroon car at 0.55).
        if "hsv" in modules and attribute:
            exact_matches = []     # color exactly matches (or via similarity)
            top2_matches = []      # color in top-2 dominant
            no_matches = []        # color not found

            for r in results:
                dom = detect_color(frame, r["bbox"])
                top = detect_color_top_n(frame, r["bbox"], n=2)
                r["_dominant_color"] = dom
                r["_top_colors"] = top
                if is_color_match(dom, attribute):
                    exact_matches.append(r)
                elif any(is_color_match(c, attribute) for c in top):
                    top2_matches.append(r)
                else:
                    no_matches.append(r)

            # Prefer exact match → top-2 match → best by confidence
            if exact_matches:
                best = max(exact_matches, key=lambda d: d["confidence"])
                # Label with the REQUESTED color (what user asked for),
                # not the base HSV bucket. Keep HSV observation for debugging.
                best["color"] = attribute
                best["hsv_dominant"] = best["_dominant_color"]
                match_tier = "exact"
            elif top2_matches:
                best = max(top2_matches, key=lambda d: d["confidence"])
                best["color"] = attribute
                best["hsv_dominant"] = best["_dominant_color"]
                best["confidence"] *= 0.8
                match_tier = "top-2"
            else:
                best = max(no_matches, key=lambda d: d["confidence"])
                # Here the detected color genuinely doesn't match —
                # keep the HSV observation so user sees the mismatch
                best["color"] = best["_dominant_color"]
                best["confidence"] *= 0.3
                match_tier = "no-match"

            # Tag so step-7 can drop no-match detections when real matches exist
            best["_match_tier"] = match_tier

            logger.info(
                f"Frame {frame_num}: YOLO found {len(results)} '{target}'(s), "
                f"picked {match_tier} match — class={best['object_class']}, "
                f"dom='{best['_dominant_color']}', top={best['_top_colors']}, "
                f"wanted='{attribute}', conf={best['confidence']:.3f}"
            )
        else:
            best = max(results, key=lambda d: d["confidence"])
            logger.info(
                f"Frame {frame_num}: YOLO found {len(results)} '{target}'(s), "
                f"best={best['object_class']} (conf={best['confidence']})"
            )

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
            "track_id": best.get("track_id"),
            "_match_tier": best.get("_match_tier"),
            # tracked_ids_in_frame: all unique track IDs seen this frame
            # (used by analyzer loop to aggregate unique_count)
            "tracked_ids_in_frame": [
                r["track_id"] for r in results if r.get("track_id") is not None
            ] if use_tracking else [],
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

    # ── OCR — return each text region as a separate detection ──
    if "ocr" in modules:
        regions = extract_text_regions(frame)
        if regions:
            return [
                {
                    "frame_number": frame_num,
                    "timestamp": timestamp,
                    "timestamp_fmt": format_timestamp(timestamp),
                    "object_class": "text",
                    "color": None,
                    "confidence": r["confidence"],
                    "bbox": r["bbox"],
                    "text_content": r["text"],
                    "count": None,
                }
                for r in regions
            ]
        return None

    return None