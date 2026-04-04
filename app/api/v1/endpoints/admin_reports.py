from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.report import Report, ReportMessage, ReportAction
from app.schemas.report import ReportRead, ReportDetail, ReportAssignUpdate, ReportStatusUpdate, ReportMessageCreate, ReportMessageRead

router = APIRouter()

@router.get("", response_model=List[ReportRead])
def get_all_reports(
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ F1. View Report List: Lấy danh sách toàn bộ khiếu nại/hỗ trợ. """
    query = db.query(Report)
    
    if status_filter:
        query = query.filter(Report.status == status_filter)
    if category_filter:
        query = query.filter(Report.category == category_filter)
        
    return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{report_id}", response_model=ReportDetail)
def get_report_detail(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ F2. View Report Detail: Xem chi tiết khiếu nại kèm lịch sử tin nhắn. """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy Report.")
        
    messages = db.query(ReportMessage).filter(ReportMessage.report_id == report.id).order_by(ReportMessage.created_at.asc()).all()
    
    report_response = ReportDetail.model_validate(report)
    report_response.messages = [ReportMessageRead.model_validate(m) for m in messages]
    return report_response

@router.patch("/{report_id}/assign")
def assign_report(
    report_id: UUID,
    payload: ReportAssignUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ F3. Assign Report: Phân công một Admin (hoặc tự nhận) xử lý ticket này. """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy Report.")
        
    # Lấy ID của Admin trong bảng admins tương ứng với user_id được truyền vào
    # (Giả định payload truyền vào là id của bảng admins, nếu là user_id thì cần query check bảng admins trước)
    
    report.assigned_admin_id = payload.assigned_admin_id
    report.updated_at = datetime.utcnow()
    
    # Ghi log hành động
    action_log = ReportAction(
        report_id=report.id,
        actor_user_id=current_admin.id,
        action="assigned",
        new_value={"assigned_admin_id": str(payload.assigned_admin_id)}
    )
    db.add(action_log)
    db.commit()
    
    return {"message": "Đã phân công xử lý thành công."}

@router.patch("/{report_id}/status")
def update_report_status(
    report_id: UUID,
    payload: ReportStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ F4 & F6. Update Status & Log Action: Cập nhật trạng thái xử lý và ghi log. """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy Report.")
        
    old_status = report.status
    report.status = payload.status
    report.updated_at = datetime.utcnow()
    
    if payload.status in ["resolved", "closed"]:
        report.resolved_at = datetime.utcnow()
        
    # Ghi log hành động vào bảng report_actions
    action_log = ReportAction(
        report_id=report.id,
        actor_user_id=current_admin.id,
        action="status_changed",
        old_value={"status": old_status},
        new_value={"status": payload.status, "note": payload.action_note}
    )
    db.add(action_log)
    db.commit()
    
    return {"message": f"Đã cập nhật trạng thái thành {payload.status}."}

@router.post("/{report_id}/messages", response_model=ReportMessageRead)
def reply_to_report_as_admin(
    report_id: UUID,
    payload: ReportMessageCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ F5. Reply to Report: Admin nhắn tin phản hồi cho User. """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy Report.")
        
    new_message = ReportMessage(
        report_id=report.id,
        sender_user_id=current_admin.id,
        message=payload.message,
        attachments=payload.attachments
    )
    db.add(new_message)
    
    report.updated_at = datetime.utcnow()
    # Tự động chuyển trạng thái sang in_progress nếu admin bắt đầu reply
    if report.status == "open":
        report.status = "in_progress"
        
    db.commit()
    db.refresh(new_message)
    return new_message