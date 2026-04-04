from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any

class ReportMessageCreate(BaseModel):
    message: str
    attachments: Optional[Any] = None # JSONB

class ReportMessageRead(BaseModel):
    id: UUID
    report_id: UUID
    sender_user_id: UUID
    message: str
    attachments: Optional[Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ReportCreate(BaseModel):
    message_type: str # "bug", "support", "complaint"
    target_type: str # "video", "session", "account", "other"
    target_id: Optional[UUID] = None
    category: str
    title: Optional[str] = None
    description: str
    evidence_paths: Optional[Any] = None

class ReportRead(BaseModel):
    id: UUID
    reporter_user_id: UUID
    message_type: str
    target_type: str
    category: str
    title: Optional[str]
    description: str
    status: str
    priority: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ReportDetail(ReportRead):
    messages: List[ReportMessageRead] = []
class ReportAssignUpdate(BaseModel):
    assigned_admin_id: UUID

class ReportStatusUpdate(BaseModel):
    status: str # "open", "in_progress", "resolved", "closed"
    action_note: Optional[str] = None