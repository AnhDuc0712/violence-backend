from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class VideoBase(BaseModel):
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_sec: Optional[int] = None

class VideoCreate(VideoBase):
    content_hash: str
    owner_user_id: UUID
    raw_path: str
    s3_key: Optional[str] = None

class VideoRead(VideoBase):
    id: UUID
    content_hash: str
    owner_user_id: UUID
    raw_path: str
    s3_key: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)