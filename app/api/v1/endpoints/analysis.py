import uuid
import logging
import os
import requests
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Header, Body, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.analysis import AnalysisSession
from app.models.analysis import AnalysisEvent
from app.models.video import Video
from app.schemas.analysis import (
    AnalysisSessionCreate, 
    AnalysisSessionRead, 
    AnalysisSessionDetail
)
MODEL_URL = os.getenv("AI_SERVER_URL")
router = APIRouter()
logger = logging.getLogger(__name__)

# Key bảo mật giữa AI Service và Web Backend
INTERNAL_SECRET_KEY = "toi_nho_ngoc_nhu_vai_ca_lon"

# 1. Thêm 'score' vào Schema của Event
class AnalysisEventRead(BaseModel):
    id: UUID
    event_type: str
    t_start: Optional[float] = 0.0
    t_end: Optional[float] = 0.0
    score: Optional[float] = 0.0  # 🔥 THÊM DÒNG NÀY ĐỂ PYDANTIC KHÔNG XÓA MẤT

    class Config:
        from_attributes = True

# 2. Thêm 'max_prob' và 'events' vào Schema Detail của Session
class AnalysisSessionDetail(BaseModel): # (Kế thừa AnalysisSessionRead nếu có)
    id: UUID
    status: str
    # ... các trường khác
    max_prob: Optional[float] = 0.0  # 🔥 THÊM DÒNG NÀY
    events: List[AnalysisEventRead] = [] # 🔥 ĐẢM BẢO GỌI ĐÚNG SCHEMA EVENT Ở TRÊN

    class Config:
        from_attributes = True
class AISyncPayload(BaseModel):
    session_id: UUID
    status: Optional[str] = None
    processed_video_path: Optional[str] = None
    max_prob: Optional[float] = 0.0
    events: List[Any] = []
    analysis_hash: Optional[str] = None

# 🚀 1. START ANALYSIS (Khởi tạo phiên)
# 🚀 1. START ANALYSIS (Khởi tạo phiên)
@router.post("/start", response_model=AnalysisSessionRead)
async def start_analysis(
    request: Request,
    payload: AnalysisSessionCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    try:
        body = await request.json()
        logger.info(f"📥 Incoming Start Request: {body}")
    except:
        pass

    video = db.query(Video).filter(
        Video.id == payload.video_id, 
        Video.owner_user_id == current_user.id
    ).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video không tồn tại")

    existing = db.query(AnalysisSession).filter(
        AnalysisSession.video_id == video.id,
        AnalysisSession.status == "pending"
    ).first()
    
    if existing:
        logger.info(f"♻️ Reusing existing pending session: {existing.id}")
        return existing

    new_session = AnalysisSession(
        id=uuid.uuid4(),
        owner_user_id=current_user.id,
        video_id=video.id,
        pipeline_spec=payload.pipeline_spec or {},
        status="pending", 
        analysis_hash=f"tmp_{uuid.uuid4().hex[:8]}", 
        created_at=datetime.utcnow(),
        processed_video_path="", 
        failure_reason=""
    )
    
    try:
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        logger.info(f"✨ Started Session: {new_session.id}")
        
        # 🔥 ĐÃ CHUYỂN REQUEST VÀO ĐÚNG VỊ TRÍ (SAU KHI TẠO SESSION)
        MODEL_URL = os.getenv("AI_SERVER_URL")
        if MODEL_URL:
            try:
                requests.post(
                    f"{MODEL_URL}/predict",
                    json={
                        "session_id": str(new_session.id),
                        "video_path": video.original_filename # HOẶC thay bằng trường chứa đường dẫn video thực tế của ông
                    },
                    timeout=5 
                )
                logger.info("Đã bắn tín hiệu sang AI Server thành công!")
            except requests.exceptions.ReadTimeout:
                # Bắt lỗi Timeout (Do mình set timeout=5 nên nó báo lỗi là bình thường, AI vẫn đang chạy ngầm)
                logger.info("Đã gửi lệnh cho AI (Bỏ qua Timeout)")
            except Exception as e:
                logger.error(f"Lỗi khi gọi AI Server: {e}")

        return new_session
    except Exception as e:
        db.rollback()
        logger.error(f"❌ START ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="DB Error")

# 🔄 2. SYNC ANALYSIS (AI 8001 gọi sang - ĐÃ FIX BYPASS ENUM)
@router.post("/internal/sync-analysis")
def sync_analysis_from_ai(
    payload: AISyncPayload = Body(...), 
    db: Session = Depends(get_db),
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")
):
    if x_internal_secret != INTERNAL_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        session = db.query(AnalysisSession).filter(AnalysisSession.id == payload.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # CẬP NHẬT DỮ LIỆU, NÉ TRƯỜNG STATUS ĐỂ TRÁNH LỖI ENUM POSTGRES
        # CẬP NHẬT DỮ LIỆU ĐẦY ĐỦ
        session.finished_at = datetime.utcnow()
        session.processed_video_path = payload.processed_video_path
        
        # 🔥 ÉP BUỘC CẬP NHẬT STATUS ĐỂ FRONTEND BIẾT LÀ ĐÃ XONG
        session.status = payload.status or "completed" 
        session.max_prob = payload.max_prob or 0.0

        if payload.analysis_hash:
            session.analysis_hash = payload.analysis_hash

        # Cập nhật danh sách Events
        db.query(AnalysisEvent).filter(AnalysisEvent.session_id == session.id).delete()
        for i, ev in enumerate(payload.events):
            if not isinstance(ev, dict): continue
            db.add(AnalysisEvent(
                id=uuid.uuid4(),
                session_id=session.id,
                event_type=str(ev.get("label") or "violence"),
                score=float(ev.get("score") or 0.0),
                t_start=float(ev.get("start") or 0.0),
                t_end=float(ev.get("end") or 0.0),
                payload=ev.get("metadata") or {}, 
                ml_review_status="pending", 
                event_hash=f"{session.id}_{i}_{uuid.uuid4().hex[:4]}",
                created_at=datetime.utcnow()
            ))
        
        db.commit()
        logger.info(f"✅ Sync SUCCESS for {payload.session_id}")
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"❌ SYNC ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 📑 3. LIST SESSIONS
@router.get("", response_model=List[AnalysisSessionRead])
def get_sessions(db: Session = Depends(get_db), current_user: Any = Depends(get_current_user)):
    return db.query(AnalysisSession).filter(
        AnalysisSession.owner_user_id == current_user.id
    ).order_by(AnalysisSession.created_at.desc()).all()

# 🔍 4. SESSION DETAIL
@router.get("/{session_id}")
def get_session_detail(session_id: UUID, db: Session = Depends(get_db), current_user: Any = Depends(get_current_user)):
    
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id, 
        AnalysisSession.owner_user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    events = db.query(AnalysisEvent).filter(AnalysisEvent.session_id == session.id).all()
    
    # Ép thành JSON Dictionary
    data = jsonable_encoder(session)
    data["events"] = jsonable_encoder(events)
    
    return JSONResponse(content=data)