from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from botocore.config import Config
import boto3
from botocore.exceptions import ClientError
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


def _estimate_duration_seconds(file_path: str) -> Optional[int]:
    """Lấy thời lượng video (OpenCV cần truyền string đường dẫn)"""
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(file_path)
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


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION_NAME,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        config=Config(
            signature_version='s3v4',
        )
    )


def _s3_object_url(object_key: str) -> str:
    return f"{settings.S3_BASE_URL.rstrip('/')}/{object_key.lstrip('/')}"


async def save_upload_video(db: Session, file: UploadFile, owner_user_id) -> Video:
    suffix = _safe_suffix(file.filename or "uploaded_video")
    sha256 = hashlib.sha256()
    file_size = 0

    # 1. GHI RA FILE TẠM (Vào thẳng thư mục rác của Hệ điều hành, không dính dáng dự án)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
            sha256.update(chunk)
            file_size += len(chunk)
        temp_path = tmp.name # Lấy đường dẫn vật lý của file tạm

    try:
        content_hash = sha256.hexdigest()

        # 2. KIỂM TRA TRÙNG LẶP DƯỚI DATABASE
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
            return existing

        # 3. LẤY THỜI LƯỢNG VIDEO BẰNG OPENCV
        duration_sec = _estimate_duration_seconds(temp_path)

        # 4. UPLOAD LÊN S3
        final_filename = f"{content_hash[:16]}_{uuid.uuid4().hex[:8]}{suffix}"
        object_key = f"{settings.S3_UPLOAD_PREFIX.rstrip('/')}/{owner_user_id}/{final_filename}"
        s3_client = _get_s3_client()

        with open(temp_path, "rb") as fobj:
            s3_client.upload_fileobj(
                fobj,
                settings.S3_BUCKET_NAME,
                object_key,
                ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
            )

        # 5. LƯU THÔNG TIN VÀO DATABASE
        video = Video(
            owner_user_id=owner_user_id,
            content_hash=content_hash,
            original_filename=file.filename,
            mime_type=file.content_type,
            size_bytes=file_size,
            duration_sec=duration_sec,
            raw_path=_s3_object_url(object_key),
            s3_key=object_key,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video

    except ClientError as exc:
        raise RuntimeError(f"S3 upload failed: {exc}")
    
    finally:
        # 6. DỌN DẸP CHIẾN TRƯỜNG (BẮT BUỘC)
        # Bất kể code thành công hay crash ngang, file tạm luôn bị xóa
        if os.path.exists(temp_path):
            os.remove(temp_path)