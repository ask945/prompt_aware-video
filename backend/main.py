import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Configure logging before anything else
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)

# Load .env.local BEFORE any other imports that read env vars
env_path = Path(__file__).resolve().parent.parent / ".env.local"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import cloudinary
from config import settings
from database.db import Base, engine
import database.schemas  # noqa: F401
from routes.analyze import router as analyze_router
from routes.auth import router as auth_router
from routes.upload import router as upload_router
from routes.results import router as results_router

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

app = FastAPI(
    title="Prompt-Aware Video Analysis API",
    version="1.0.0",
)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(analyze_router)
app.include_router(results_router)
app.include_router(auth_router)