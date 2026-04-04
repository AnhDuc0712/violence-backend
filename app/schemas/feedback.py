from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class VideoFeedbackCreate(BaseModel):
    session_id: UUID
    feedback_type: str # VD: "false_positive", "false_negative", "excellent"
    rating: Optional[int] = None # 1 đến 5 sao
    comment: Optional[str] = None

class VideoFeedbackRead(BaseModel):
    id: UUID
    owner_user_id: UUID
    session_id: UUID
    feedback_type: str
    rating: Optional[int]
    comment: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)