from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.config import settings  

from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token
)

from app.schemas.user import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserCreate,
    UserResponse,
    UserLogin,
    Token
)

from app.models.user import User, UserCredential

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # kiểm tra email tồn tại
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email đã được đăng ký.")

    # tạo user
    new_user = User(
        email=user_in.email,
        username=user_in.username,
        phone=user_in.phone,
        role="user",
        status="active"
    )
    db.add(new_user)
    db.flush()  # lấy id

    # tạo credential
    new_credential = UserCredential(
        user_id=new_user.id,
        password_hash=get_password_hash(user_in.password),
        password_algo="bcrypt"
    )
    db.add(new_credential)

    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    # tìm user
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Email hoặc mật khẩu không đúng.")

    # kiểm tra trạng thái
    if user.status != "active":
        raise HTTPException(status_code=400, detail="Tài khoản đã bị khóa.")

    # kiểm tra password
    credential = db.query(UserCredential).filter(UserCredential.user_id == user.id).first()
    if not credential or not verify_password(login_data.password, credential.password_hash):
        raise HTTPException(status_code=400, detail="Email hoặc mật khẩu không đúng.")

    # FIX: Đổi 'data=' thành 'subject=' hoặc truyền tham số vị trí tùy theo hàm trong security.py
    # Ở đây tôi dùng user.id làm định danh chính (sub)
    access_token = create_access_token(
        subject=str(user.id), 
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(data: RefreshTokenRequest):
    try:
        # verify refresh token
        payload = verify_refresh_token(data.refresh_token)

        # FIX: Lấy identity từ payload (thường là trường 'sub')
        user_id = payload.get("sub")
        if not user_id:
            raise Exception("Invalid token payload")

        # tạo access token mới
        new_access_token = create_access_token(
            subject=str(user_id),
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ hoặc đã hết hạn"
        )


@router.post("/logout")
def logout():
    # FE tự xóa token trong localStorage
    return {"message": "Đăng xuất thành công"}