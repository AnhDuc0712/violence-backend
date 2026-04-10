# TRONG FILE: app/api/routes/videos.py (CỦA BACKEND 8000)

import os
import uuid
import logging
from datetime import datetime
from typing import List
from uuid import UUID

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from fastapi.responses import StreamingResponse, JSONResponse  
from fastapi.encoders import jsonable_encoder              
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoRead
from app.services.s3_service import generate_presigned_url
from app.services.video_service import save_upload_video

router = APIRouter()
logger = logging.getLogger(__name__)

# ==========================================================
# 🚀 C1. Upload Video (CHỈ LƯU FILE - KHÔNG GỌI AI)
# ==========================================================
@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=VideoRead)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="File không đúng định dạng video."
        )

    try:
        video = await save_upload_video(db, file, current_user.id)
        logger.info(f"✅ Video uploaded: {video.id} by User: {current_user.id}")
        return video

    except Exception as e:
        logger.error(f"❌ Upload Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Lỗi trong quá trình lưu video."
        )

# ==========================================================
# 📺 C2. Stream Video (NETFLIX LEVEL STREAMING)
# ==========================================================
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION_NAME,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4')
    )

@router.get("/stream")
def stream_video(s3_key: str, request: Request):
    try:
        s3 = get_s3_client()
        obj = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        
        file_size = obj['ContentLength']
        range_header = request.headers.get('range')

        # Hàm Generator chia nhỏ data thành từng cục 1MB (đúng chuẩn sếp bắt bệnh)
        def iterfile(stream):
            for chunk in stream.iter_chunks(chunk_size=1024 * 1024): # 1MB chunks
                yield chunk

        if range_header:
            bytes_range = range_header.replace("bytes=", "").split("-")
            start = int(bytes_range[0])
            end = int(bytes_range[1]) if bytes_range[1] else file_size - 1

            chunk_size = end - start + 1

            # Lấy đúng mảng byte mà trình duyệt yêu cầu
            obj_range = s3.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Range=f"bytes={start}-{end}"
            )

            return StreamingResponse(
                iterfile(obj_range['Body']), # ✅ Đã bọc generator
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                    "Content-Type": "video/mp4",
                },
            )

        # Nếu trình duyệt không đòi Range (thường lúc mới load lần đầu)
        return StreamingResponse(
            iterfile(obj['Body']), # ✅ Đã bọc generator
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Type": "video/mp4",
            },
        )

    except Exception as e:
        logger.error(f"❌ Stream Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Không thể stream video từ S3.")

# ==========================================================
# 📋 C3. View My Videos (DÙNG STREAM API)
# ==========================================================
@router.get("") 
def get_videos(
    skip: int = 0, limit: int = 20, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    videos = db.query(Video).filter(
        Video.owner_user_id == current_user.id,
        Video.deleted_at.is_(None)
    ).order_by(Video.created_at.desc()).offset(skip).limit(limit).all()
    
    data = jsonable_encoder(videos)
    
    BACKEND_URL = getattr(settings, 'API_BASE_URL', "http://localhost:8000")
    for v in data:
        if v.get("s3_key"):
            v["video_url"] = f"{BACKEND_URL}/api/v1/videos/stream?s3_key={v['s3_key']}"
        else:
            v["video_url"] = ""

    return JSONResponse(content=data)

# ==========================================================
# 🔍 C4. View Video Detail (DÙNG STREAM API)
# ==========================================================
@router.get("/{video_id}") 
def get_video_detail(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.owner_user_id == current_user.id,
        Video.deleted_at.is_(None)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy video.")

    data = jsonable_encoder(video)
    
    BACKEND_URL = getattr(settings, 'API_BASE_URL', "http://localhost:8000")
    if data.get("s3_key"):
        data["video_url"] = f"{BACKEND_URL}/api/v1/videos/stream?s3_key={data['s3_key']}"
    else:
        data["video_url"] = ""

    return JSONResponse(content=data)

# ==========================================================
# 🗑️ C5. Soft Delete
# ==========================================================
@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.owner_user_id == current_user.id,
        Video.deleted_at.is_(None)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy video.")

    video.deleted_at = datetime.utcnow()
    db.commit()
    return None

# ==========================================================
# 🗝️ C6. Get Presigned URL (Backup)
# ==========================================================
@router.get("/{video_id}/presigned-url")
def get_video_presigned_url(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.owner_user_id == current_user.id,
        Video.deleted_at.is_(None)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy video.")

    if not video.s3_key:
        raise HTTPException(status_code=400, detail="Video chưa có s3_key.")

    try:
        presigned_url = generate_presigned_url(video.s3_key)
        return {"presigned_url": presigned_url}
    except Exception as e:
        logger.error(f"❌ Presigned URL Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Không thể tạo presigned URL.")