from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
import uuid
from app.core.database import Base

# ==========================================
# 1. DATABASE MODELS (SQLAlchemy)
# ==========================================

class Report(Base):
    __tablename__ = "reports"
    __table_args__ = {'extend_existing': True} # Chống lỗi "already defined"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_type = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    evidence_paths = Column(JSONB, nullable=True)
    status = Column(String, server_default="open", nullable=False)
    priority = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

class ReportMessage(Base):
    __tablename__ = "report_messages"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    sender_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    message = Column(Text, nullable=False)
    attachments = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ReportAction(Base):
    __tablename__ = "report_actions"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    action = Column(String, nullable=False)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

# ==========================================
# 2. SCHEMAS (Pydantic)
# ==========================================
class ReportAssignUpdate(BaseModel):
    assigned_admin_id: uuid.UUID

class ReportStatusUpdate(BaseModel):
    status: str
    action_note: Optional[str] = None

class ReportMessageCreate(BaseModel):
    message: str
    attachments: Optional[List[str]] = None