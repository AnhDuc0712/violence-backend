from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.video import Video
from app.models.analysis import AnalysisSession, AnalysisEvent
from app.schemas.video import VideoRead
from app.schemas.analysis import AnalysisSessionRead, AnalysisSessionDetail

router = APIRouter()

@router.get("/videos", response_model=List[VideoRead])
def get_all_videos(
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ D1. View All Videos: Xem toàn bộ video trên hệ thống. """
    return db.query(Video).order_by(Video.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/sessions", response_model=List[AnalysisSessionRead])
def get_all_sessions(
    status_filter: Optional[str] = None,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ D2. View All Analysis Sessions: Quản lý các tiến trình AI. """
    query = db.query(AnalysisSession)
    if status_filter:
        query = query.filter(AnalysisSession.status == status_filter)
    return query.order_by(AnalysisSession.created_at.desc()).offset(skip).limit(limit).all()

@router.post("/sessions/{session_id}/cancel")
def cancel_analysis_job(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ D5. Cancel Job: Hủy một tiến trình đang phân tích. """
    session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên phân tích.")
        
    if session.status not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail="Chỉ có thể hủy tiến trình đang chờ hoặc đang chạy.")
        
    session.status = "cancelled"
    # TODO: Gửi tín hiệu (Celery revoke) để ngắt worker đang chạy thực tế
    db.commit()
    return {"message": "Đã hủy tiến trình phân tích."}