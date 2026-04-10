from sqlalchemy import Column, String, BigInteger, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_hash = Column(String, nullable=False)
    original_filename = Column(String)
    mime_type = Column(String)
    size_bytes = Column(BigInteger)
    duration_sec = Column(Integer)
    raw_path = Column(Text, nullable=False)
    s3_key = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True))