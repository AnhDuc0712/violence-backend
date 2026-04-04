from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.analysis import AnalysisEvent

router = APIRouter()

# Schema dùng nội bộ cho API này
class MLReviewAction(BaseModel):
    decision: str # "approved", "rejected", "overridden"
    label_override: Optional[str] = None
    note: Optional[str] = None

@router.get("/events/pending")
def get_pending_reviews(
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ E1. View Pending Reviews: Lấy danh sách các sự kiện bạo lực cần con người xác nhận. """
    events = db.query(AnalysisEvent).filter(
        AnalysisEvent.ml_review_status == "pending"
    ).order_by(AnalysisEvent.created_at.desc()).offset(skip).limit(limit).all()
    return events

@router.post("/events/{event_id}/review")
def review_ml_event(
    event_id: UUID,
    payload: MLReviewAction,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ E2 & E3. Approve/Reject/Override: Xác nhận hoặc sửa lại nhãn của AI. """
    event = db.query(AnalysisEvent).filter(AnalysisEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện.")
        
    if payload.decision not in ["approved", "rejected", "overridden"]:
        raise HTTPException(status_code=400, detail="Quyết định không hợp lệ.")
        
    # Cập nhật sự kiện
    event.ml_review_status = payload.decision
    if payload.decision == "overridden" and payload.label_override:
        event.ml_label_override = payload.label_override
        
    event.ml_reviewed_by = current_admin.id
    event.ml_reviewed_at = datetime.utcnow()
    
    # Ghi log vào bảng ml_reviews (Nếu bạn đã map Model MLReview)
    # new_review = MLReview(reviewer_user_id=current_admin.id, target_id=event.id, ...)
    # db.add(new_review)
    
    db.commit()
    return {"message": "Đã ghi nhận kết quả kiểm duyệt."}

@router.post("/dataset/snapshot")
def create_dataset_snapshot(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ E5. Create Dataset Snapshot: Đóng gói các dữ liệu đã được kiểm duyệt để train lại Model. """
    # Lấy các event đã được review xong
    reviewed_events = db.query(AnalysisEvent).filter(
        AnalysisEvent.ml_review_status.in_(["approved", "overridden"])
    ).count()
    
    # Logic thực tế sẽ dump các JSON/Image paths ra một file/bảng riêng
    # Giả lập insert vào bảng ml_dataset_snapshots
    return {
        "message": "Đã tạo snapshot thành công",
        "num_samples": reviewed_events,
        "snapshot_id": str(UUID(int=0)) # Trả về ID thật khi implement DB insert
    }