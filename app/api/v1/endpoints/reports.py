from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.report import Report, ReportMessage # Giả định đã tạo model
from app.schemas.report import ReportCreate, ReportRead, ReportDetail, ReportMessageCreate, ReportMessageRead

router = APIRouter()

@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ F1. Submit Report: Gửi yêu cầu hỗ trợ/khiếu nại. """
    new_report = Report(
        reporter_user_id=current_user.id,
        message_type=payload.message_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        evidence_paths=payload.evidence_paths,
        status="open"
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@router.get("", response_model=List[ReportRead])
def get_my_reports(
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ F2. View My Reports: Lịch sử khiếu nại. """
    return db.query(Report).filter(
        Report.reporter_user_id == current_user.id
    ).order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{report_id}", response_model=ReportDetail)
def get_report_detail(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ F3. View Report Detail: Xem chi tiết kèm tin nhắn trao đổi. """
    report = db.query(Report).filter(Report.id == report_id, Report.reporter_user_id == current_user.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy Report.")
        
    messages = db.query(ReportMessage).filter(ReportMessage.report_id == report.id).order_by(ReportMessage.created_at.asc()).all()
    
    report_response = ReportDetail.model_validate(report)
    report_response.messages = [ReportMessageRead.model_validate(m) for m in messages]
    return report_response

@router.post("/{report_id}/messages", response_model=ReportMessageRead)
def reply_to_report(
    report_id: UUID,
    payload: ReportMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ F4. Reply to Report: Nhắn tin bổ sung cho Admin. """
    report = db.query(Report).filter(Report.id == report_id, Report.reporter_user_id == current_user.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy Report.")
        
    new_message = ReportMessage(
        report_id=report.id,
        sender_user_id=current_user.id,
        message=payload.message,
        attachments=payload.attachments
    )
    db.add(new_message)
    
    # Cập nhật thời gian update của Report
    from datetime import datetime
    report.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(new_message)
    return new_message

@router.delete("/{report_id}", status_code=204)
def cancel_report(report_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = db.query(Report).filter(Report.id == report_id, Report.reporter_user_id == current_user.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
    if report.status != "open":
        raise HTTPException(status_code=400, detail="Chỉ có thể hủy báo cáo khi đang ở trạng thái 'Chờ xử lý'")
    
    db.delete(report)
    db.commit()
    return None