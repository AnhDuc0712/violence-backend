from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, JSON,Integer,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    pipeline_spec = Column(JSONB, nullable=False)
    analysis_hash = Column(String, nullable=False)
    status = Column(String, server_default="pending", nullable=False)
    processed_video_path = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    failure_reason = Column(Text)
    deleted_at = Column(DateTime(timezone=True))

class AnalysisEvent(Base):
    __tablename__ = "analysis_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    t_start = Column(Float)
    t_end = Column(Float)
    payload = Column(JSONB, nullable=False)
    ml_review_status = Column(String, server_default="pending", nullable=False)
    ml_label_override = Column(String)
    ml_reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    ml_reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_hash = Column(String, nullable=False)

class VideoFeedback(Base):
    __tablename__ = "video_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    feedback_type = Column(String, nullable=False) # VD: "false_positive", "false_negative", "excellent"
    rating = Column(Integer, nullable=True) # 1 đến 5 sao
    comment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Đảm bảo mỗi user chỉ được đánh giá 1 lần cho mỗi phiên phân tích
    __table_args__ = (
        UniqueConstraint('owner_user_id', 'session_id', name='uix_user_session_feedback'),
    )