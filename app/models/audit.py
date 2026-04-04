from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.core.database import Base # Hoặc nơi bạn cấu hình declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(UUID(as_uuid=True), index=True)
    action = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True)
    ip_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)