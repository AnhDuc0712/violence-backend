from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List

# --- Schema cho Sự kiện (Events) ---
class AnalysisEventRead(BaseModel):
    id: UUID
    session_id: UUID
    event_type: str
    score: float
    t_start: Optional[float]
    t_end: Optional[float]
    ml_review_status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Schema cho Phiên phân tích (Sessions) ---
class AnalysisSessionCreate(BaseModel):
    video_id: UUID
    pipeline_spec: Dict[str, Any] = {"model_version": "v1.0", "threshold": 0.7}

class AnalysisSessionRead(BaseModel):
    id: UUID
    video_id: UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    failure_reason: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)
    
class AnalysisSessionDetail(AnalysisSessionRead):
    # Dùng cho D3 + D4: Trả về Session kèm luôn danh sách Events
    events: List[AnalysisEventRead] = []