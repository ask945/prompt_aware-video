"""
Analyze Route — POST /api/analyze

Uses existing auth layer and PostgreSQL/SQLAlchemy stack.
Parses query, selects strategy, creates job, launches background analysis.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from core import prompt_interpreter
from core import strategy_selector
from core.analyzer import run_analysis
from database.db import get_db
from database.schemas import Job
from database.service import get_video_for_user

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    video_url: str | None = None
    video_id: str | None = None
    query: str


@router.post("/api/analyze")
async def analyze_video(
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ─── Resolve video URL ───
    selected_video = None

    if payload.video_id:
        selected_video = get_video_for_user(db, current_user["id"], payload.video_id)
        if not selected_video:
            raise HTTPException(status_code=404, detail="Video not found for this user.")

    video_url = payload.video_url or (selected_video["url"] if selected_video else None)
    if not video_url:
        raise HTTPException(status_code=400, detail="video_url is required.")

    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="query is required.")

    # ─── Step 1: Parse query (sync — instant) ───
    parsed_query = prompt_interpreter.parse(payload.query)
    logger.info("Parsed query: %s", parsed_query)

    # ─── Step 2: Select strategy (sync — instant) ───
    strategy_config = strategy_selector.select(
        intent=parsed_query["intent"],
        temporal_scope=parsed_query["temporal_scope"],
    )
    logger.info("Selected strategy config: %s", strategy_config)

    # ─── Step 3: Create job in DB ───
    job = Job(
        user_id=current_user["id"],
        video_id=payload.video_id,
        query=payload.query,
        intent=parsed_query["intent"],
        target=parsed_query.get("target"),
        attribute=parsed_query.get("attribute"),
        temporal_scope=parsed_query.get("temporal_scope"),
        strategy=strategy_config["strategy"],
        modules=",".join(strategy_config["modules"]),
        status="processing",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = str(job.id)
    logger.info("Created job: %s", job_id)

    # ─── Step 4: Launch background task ───
    background_tasks.add_task(
        run_analysis,
        job_id=job_id,
        video_url=video_url,
        query_data=parsed_query,
        strategy_config=strategy_config,
    )
    
    # ─── Step 5: Return immediately ───
    return {
        "job_id": job_id,
        "status": "processing",
        "video_id": payload.video_id,
        "video_url": video_url,
        "query": payload.query,
        "parsed_query": parsed_query,
        "strategy": {
            "name": strategy_config["strategy"],
            "modules": strategy_config["modules"],
            "sample_rate": strategy_config["sample_rate"],
            "early_stop": strategy_config["early_stop"],
        },
    }