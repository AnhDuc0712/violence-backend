from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.core.security import ALGORITHM, SECRET_KEY

# Khai báo cấu hình cho Swagger UI biết API Login nằm ở đâu
# Điều này giúp nút "Authorize" (ổ khóa xanh) trên Swagger hoạt động
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class TokenData(BaseModel):
    user_id: Optional[UUID] = None

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependency: Giải mã JWT token và trả về object User hiện tại.
    Dùng cho các API yêu cầu đăng nhập.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập (Token không hợp lệ hoặc đã hết hạn)",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Giải mã token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
            
        token_data = TokenData(user_id=UUID(user_id_str))
        
    except JWTError:
        raise credentials_exception
        
    # Query user từ DB
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
        
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Tài khoản này đã bị khóa hoặc không hoạt động."
        )
        
    return user

def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency: Dùng cho các API chỉ dành riêng cho Admin (Module C, E, F).
    """
    # Lưu ý: Nếu DB của bạn có bảng Admin riêng liên kết với User,
    # bạn có thể query thêm bảng Admin ở đây để check role_level.
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập tài nguyên này."
        )
    return current_user