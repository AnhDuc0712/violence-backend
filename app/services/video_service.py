from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.video import Video

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".m4v",
}


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in ALLOWED_VIDEO_EXTENSIONS else ".bin"


def _estimate_duration_seconds(file_path: Path) -> Optional[int]:
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if fps > 0 and frame_count > 0:
            return int(frame_count / fps)
        return None
    finally:
        cap.release()


async def save_upload_video(db: Session, file: UploadFile, owner_user_id) -> Video:
    settings.UPLOAD_DIR_PATH.mkdir(parents=True, exist_ok=True)
    owner_dir = settings.UPLOAD_DIR_PATH / str(owner_user_id)
    owner_dir.mkdir(parents=True, exist_ok=True)

    suffix = _safe_suffix(file.filename or "uploaded_video")
    temp_path = owner_dir / f"tmp_{uuid.uuid4().hex}{suffix}"

    sha256 = hashlib.sha256()
    file_size = 0

    with temp_path.open("wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)
            sha256.update(chunk)
            file_size += len(chunk)

    content_hash = sha256.hexdigest()

    existing = (
        db.query(Video)
        .filter(
            Video.owner_user_id == owner_user_id,
            Video.content_hash == content_hash,
            Video.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        temp_path.unlink(missing_ok=True)
        return existing

    final_filename = f"{content_hash[:16]}_{uuid.uuid4().hex[:8]}{suffix}"
    final_path = owner_dir / final_filename
    shutil.move(str(temp_path), str(final_path))

    relative_path = final_path.relative_to(settings.UPLOAD_DIR_PATH).as_posix()
    duration_sec = _estimate_duration_seconds(final_path)

    video = Video(
        owner_user_id=owner_user_id,
        content_hash=content_hash,
        original_filename=file.filename,
        mime_type=file.content_type,
        size_bytes=file_size,
        duration_sec=duration_sec,
        raw_path=relative_path,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video
