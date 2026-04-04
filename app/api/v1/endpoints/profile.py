from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserCredential
from app.schemas.user import UserResponse, UserUpdate, UserChangePassword
from app.core.security import verify_password, get_password_hash

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_user_profile(current_user: User = Depends(get_current_user)):
    """
    B1. Xem Profile: Trả về thông tin của User đang đăng nhập.
    """
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_profile(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    B2. Cập nhật Profile: Chỉ cho phép đổi username và phone.
    """
    if profile_data.username is not None:
        current_user.username = profile_data.username
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
        
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.put("/me/password", status_code=status.HTTP_200_OK)
def change_password(
    password_data: UserChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    B3. Đổi mật khẩu: Yêu cầu mật khẩu cũ chính xác mới được đổi mật khẩu mới.
    """
    # Lấy thông tin credential từ bảng user_credentials
    credential = db.query(UserCredential).filter(UserCredential.user_id == current_user.id).first()
    
    if not credential:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin bảo mật của tài khoản.")
        
    # Xác thực mật khẩu cũ
    if not verify_password(password_data.old_password, credential.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác.")
        
    # Cập nhật mật khẩu mới
    credential.password_hash = get_password_hash(password_data.new_password)
    credential.password_updated_at = datetime.utcnow()
    
    db.add(credential)
    db.commit()
    
    return {"message": "Đổi mật khẩu thành công."}