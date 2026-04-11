import base64
import hashlib
import secrets
import uuid

from sqlalchemy.orm import Session

from database.schemas import SessionToken, User, Video


def _hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(salt.encode("utf-8")),
        100_000,
    )
    return base64.b64encode(derived).decode("utf-8")


def hash_password(password: str) -> str:
    salt = base64.b64encode(secrets.token_bytes(16)).decode("utf-8")
    return f"{salt}${_hash_password(password, salt)}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        salt, expected_hash = stored_password.split("$", 1)
    except ValueError:
        return False

    actual_hash = _hash_password(password, salt)
    return secrets.compare_digest(actual_hash, expected_hash)


def serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_video(video: Video) -> dict:
    duration = float(video.duration or 0)
    total_frames = video.total_frames or max(1, round(duration * 30))
    return {
        "video_id": str(video.id),
        "filename": video.filename or "Untitled video",
        "url": video.cloudinary_url,
        "public_id": video.public_id,
        "duration": duration,
        "width": video.width or 0,
        "height": video.height or 0,
        "format": None,
        "bytes": video.file_size or 0,
        "uploaded_at": video.uploaded_at.isoformat() if video.uploaded_at else None,
        "total_frames": total_frames,
    }


def create_user(db: Session, email: str, password: str) -> dict:
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise ValueError("An account with that email already exists.")

    user = User(email=email, password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


def authenticate_user(db: Session, email: str, password: str) -> dict | None:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        return None
    return serialize_user(user)


def create_token(db: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    session_token = SessionToken(user_id=uuid.UUID(user_id), token=token)
    db.add(session_token)
    db.commit()
    return token


def revoke_token(db: Session, token: str) -> None:
    session_token = db.query(SessionToken).filter(SessionToken.token == token).first()
    if session_token:
        db.delete(session_token)
        db.commit()


def get_user_by_token(db: Session, token: str) -> dict | None:
    session_token = db.query(SessionToken).filter(SessionToken.token == token).first()
    if not session_token or not session_token.user:
        return None
    return serialize_user(session_token.user)


def add_video(db: Session, user_id: str, video: dict) -> dict:
    video_record = Video(
        user_id=uuid.UUID(user_id),
        filename=video["filename"],
        cloudinary_url=video["url"],
        public_id=video["public_id"],
        duration=video.get("duration"),
        width=video.get("width"),
        height=video.get("height"),
        file_size=video.get("bytes"),
        total_frames=max(1, round(float(video.get("duration") or 0) * 30)),
    )
    db.add(video_record)
    db.commit()
    db.refresh(video_record)
    return serialize_video(video_record)


def list_videos_for_user(db: Session, user_id: str) -> list[dict]:
    videos = (
        db.query(Video)
        .filter(Video.user_id == uuid.UUID(user_id))
        .order_by(Video.uploaded_at.desc())
        .all()
    )
    return [serialize_video(video) for video in videos]


def get_video_for_user(db: Session, user_id: str, video_id: str) -> dict | None:
    video = (
        db.query(Video)
        .filter(Video.id == uuid.UUID(video_id), Video.user_id == uuid.UUID(user_id))
        .first()
    )
    return serialize_video(video) if video else None
