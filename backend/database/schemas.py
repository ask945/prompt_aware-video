"""
Database Models — Updated

Changes from original:
  - Job: added 'error' column (Text) for failed job messages
  - Job: added 'temporal_scope' column (String) for stats
  - Job: added 'completed_at' column (already existed, just confirming)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="user", cascade="all, delete")
    jobs = relationship("Job", back_populates="user", cascade="all, delete")
    sessions = relationship("SessionToken", back_populates="user", cascade="all, delete")


class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    cloudinary_url = Column(String, nullable=False)
    public_id = Column(String)
    filename = Column(String)
    file_size = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    total_frames = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)

    uploaded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="videos")
    jobs = relationship("Job", back_populates="video", cascade="all, delete")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False)

    query = Column(Text)

    # From prompt_interpreter
    intent = Column(String)
    target = Column(String)
    attribute = Column(String)
    temporal_scope = Column(String)       # ← NEW

    # From strategy_selector
    strategy = Column(String)
    modules = Column(String)              # comma-separated: "yolo,hsv"

    # Progress tracking
    status = Column(String, default="processing")  # processing / complete / failed
    progress = Column(Integer, default=0)           # 0-100

    total_frames = Column(Integer)
    frames_processed = Column(Integer)

    # Results
    result_found = Column(Boolean, default=False)
    confidence = Column(Float)

    time_taken = Column(Float)
    error = Column(Text)                  # ← NEW: error message for failed jobs

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="jobs")
    video = relationship("Video", back_populates="jobs")
    detections = relationship("Detection", back_populates="job", cascade="all, delete")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    frame_number = Column(Integer)
    timestamp = Column(Float)
    timestamp_fmt = Column(String)

    object_class = Column(String)
    color = Column(String)
    confidence = Column(Float)

    bbox_x1 = Column(Integer)
    bbox_y1 = Column(Integer)
    bbox_x2 = Column(Integer)
    bbox_y2 = Column(Integer)

    frame_url = Column(String)
    text_content = Column(Text)

    job = relationship("Job", back_populates="detections")


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")