from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError
import uuid
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.analysis import AnalysisSession
# Giả định bạn đã tạo model VideoFeedback map với bảng video_feedback
from app.models.analysis import VideoFeedback 
from app.schemas.feedback import VideoFeedbackCreate, VideoFeedbackRead

router = APIRouter()

@router.post("", response_model=VideoFeedbackRead, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: VideoFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    E1. Submit Feedback: Gửi đánh giá cho một phiên phân tích cụ thể.
    """
    # Kiểm tra session có tồn tại và thuộc về user không
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == payload.session_id,
        AnalysisSession.owner_user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên phân tích hợp lệ.")

    try:
        new_feedback = VideoFeedback(
            owner_user_id=current_user.id,
            session_id=payload.session_id,
            feedback_type=payload.feedback_type,
            rating=payload.rating,
            comment=payload.comment
        )
        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)
        return new_feedback
    except IntegrityError:
        db.rollback()
        # Xử lý lỗi UNIQUE constraint (owner_user_id, session_id)
        raise HTTPException(status_code=400, detail="Bạn đã gửi đánh giá cho phiên phân tích này rồi.")

@router.get("", response_model=List[VideoFeedbackRead])
def get_my_feedbacks(
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    E2. View Feedback History: Lịch sử đánh giá của tôi.
    """
    feedbacks = db.query(VideoFeedback).filter(
        VideoFeedback.owner_user_id == current_user.id
    ).order_by(VideoFeedback.created_at.desc()).offset(skip).limit(limit).all()
    return feedbacks

@router.delete("/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    fb = db.query(VideoFeedback).filter(VideoFeedback.id == feedback_id, VideoFeedback.owner_user_id == current_user.id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Không tìm thấy phản hồi")
    
    db.delete(fb)
    db.commit()
    return None