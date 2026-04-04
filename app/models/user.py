from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, CITEXT
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, nullable=False)
    email = Column(CITEXT, nullable=False, unique=True)
    phone = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    phone_verified = Column(Boolean, default=False, nullable=False)
    role = Column(String, server_default="user", nullable=False)
    status = Column(String, server_default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    deleted_at = Column(DateTime(timezone=True))

# Thêm bảng chứa mật khẩu vào đây:
class UserCredential(Base):
    __tablename__ = "user_credentials"

    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    password_hash = Column(String, nullable=False)
    password_algo = Column(String, nullable=False)
    password_updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)