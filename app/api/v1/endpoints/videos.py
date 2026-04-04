import os
import uuid
import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import httpx

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoRead
from app.services import video_service

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
    # Kiểm tra định dạng
    if not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="File không đúng định dạng video."
        )

    try:
        # 1. Lưu video vào storage và Database thông qua service
        # Bước này chỉ khởi tạo video trong DB với status "pending" hoặc tương tự
        video = await video_service.save_upload_video(db, file, current_user.id)
        
        logger.info(f"✅ Video uploaded: {video.id} by User: {current_user.id}")
        
        # 2. Trả về thông tin video cho FE. 
        # FE sẽ lấy ID này để gọi tiếp sang /analysis/start
        return video

    except Exception as e:
        logger.error(f"❌ Upload Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Lỗi trong quá trình lưu video."
        )

# ==========================================================
# 📺 C2. Stream Video (Dùng để hiển thị video từ AI)
# ==========================================================
@router.get("/stream")
async def stream_video(video_url: str):
    try:
        # Streaming từ AI server hoặc storage server về Client
        async def generate():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("GET", video_url) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk

        return StreamingResponse(generate(), media_type="video/mp4")

    except Exception as e:
        logger.error(f"❌ Stream Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Không thể stream video.")

# ==========================================================
# 📋 C3. View My Videos
# ==========================================================
@router.get("", response_model=List[VideoRead])
def get_my_videos(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Video).filter(
        Video.owner_user_id == current_user.id,
        Video.deleted_at.is_(None)
    ).order_by(Video.created_at.desc()).offset(skip).limit(limit).all()

# ==========================================================
# 🔍 C4. View Video Detail
# ==========================================================
@router.get("/{video_id}", response_model=VideoRead)
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

    return video

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