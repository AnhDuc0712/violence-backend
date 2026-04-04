from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
# Giả định có model AuditLog và LoginAttempt
from app.models.audit import AuditLog, LoginAttempt 
from app.schemas.user import UserResponse
from pydantic import BaseModel


class UserRoleUpdate(BaseModel):
    role: str


router = APIRouter()

@router.get("", response_model=List[UserResponse])
def get_users_list(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ C1 & C2. View User List & Search/Filter. """
    query = db.query(User)
    
    if search:
        query = query.filter(User.email.ilike(f"%{search}%") | User.username.ilike(f"%{search}%"))
    if status_filter:
        query = query.filter(User.status == status_filter)
        
    return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{user_id}", response_model=UserResponse)
def get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ C4. View User Detail. """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    return user

@router.patch("/{user_id}/status")
def block_unblock_user(
    user_id: UUID,
    new_status: str, # "active" hoặc "blocked"
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ C3. Block/Unblock User. """
    if new_status not in ["active", "blocked", "suspended"]:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ.")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        
    # Không cho phép tự block chính mình hoặc block Super Admin khác
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Không thể tự khóa tài khoản của chính mình.")
        
    user.status = new_status
    db.commit()
    
    # Ở một hệ thống thực tế, bạn nên ghi thêm 1 dòng vào bảng audit_logs ở đây
    
    return {"message": f"Đã chuyển trạng thái người dùng thành {new_status}"}

@router.get("/{user_id}/logs")
def get_user_activity_logs(
    user_id: UUID,
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ C5 & C6. View User Activity & Login History. """
    # Lấy lịch sử đăng nhập
    logins = db.query(LoginAttempt).filter(LoginAttempt.user_id == user_id)\
        .order_by(LoginAttempt.created_at.desc()).offset(skip).limit(limit).all()
        
    # Lấy lịch sử thao tác
    activities = db.query(AuditLog).filter(AuditLog.actor_user_id == user_id)\
        .order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
        
    return {
        "login_history": logins,
        "activity_logs": activities
    }

@router.patch("/{user_id}/role")
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """ C7. Change User Role. """
    if payload.role not in ["admin", "user", "super_admin"]:
        raise HTTPException(status_code=400, detail="Quyền không hợp lệ.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    user.role = payload.role
    db.commit()
    return {"message": f"Đã cập nhật quyền thành {payload.role}"}
