# TRONG FILE: app/api/routes/analysis.py (CỦA BACKEND 8000)

import uuid
import logging
import requests
import json
import numpy as np # ✅ BẮT BUỘC PHẢI CÓ ĐỂ TRÁNH LỖI NP NOT DEFINED
from datetime import datetime
from typing import List, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Body
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.analysis import AnalysisSession, AnalysisEvent
from app.models.video import Video
from app.schemas.analysis import (
    AnalysisSessionCreate, 
    AnalysisSessionRead, 
)
from app.services.s3_service import generate_presigned_url
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# ✅ Dùng settings thay vì hardcode
INTERNAL_SECRET_KEY = getattr(settings, 'INTERNAL_SECRET_KEY', "toi_nho_ngoc_nhu_vai_ca_lon")

class AnalysisEventRead(BaseModel):
    id: UUID
    event_type: str
    t_start: Optional[float] = 0.0
    t_end: Optional[float] = 0.0
    score: Optional[float] = 0.0  
    class Config:
        from_attributes = True

class AnalysisSessionDetail(BaseModel): 
    id: UUID
    status: str
    max_prob: Optional[float] = 0.0  
    events: List[AnalysisEventRead] = [] 
    class Config:
        from_attributes = True

class AISyncPayload(BaseModel):
    session_id: Optional[UUID] = None
    video_id: Optional[UUID] = None
    status: Optional[str] = None
    processed_video_path: Optional[str] = None
    max_prob: Optional[float] = 0.0
    events: List[Any] = []
    analysis_hash: Optional[str] = None
    failure_reason: Optional[str] = None 

def safe_json(data):
    if isinstance(data, np.ndarray):
        return safe_json(data.tolist())
    elif isinstance(data, dict):
        return {str(k): safe_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [safe_json(item) for item in data]
    elif isinstance(data, (np.floating, np.float64, np.float32, float)):
        val = float(data)
        return 0.0 if np.isnan(val) or np.isinf(val) else val
    elif isinstance(data, (np.integer, np.int64, np.int32, int)):
        return int(data)
    else:
        return str(data) if data is not None else None

# 🚀 1. START ANALYSIS (API GATEWAY)
@router.post("/start", response_model=AnalysisSessionRead)
async def start_analysis(
    payload: AnalysisSessionCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    video = db.query(Video).filter(
        Video.id == payload.video_id, 
        Video.owner_user_id == current_user.id
    ).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video không tồn tại hoặc không có quyền truy cập.")
        
    if not video.s3_key:
        raise HTTPException(status_code=400, detail="Video này chưa được upload lên S3 thành công. Vui lòng tải lại.")

    existing = db.query(AnalysisSession).filter(
        AnalysisSession.video_id == video.id,
        AnalysisSession.status.in_(["pending", "processing"]) 
    ).first()
    
    if existing:
        logger.info(f"♻️ Reusing existing session (Status: {existing.status}): {existing.id}")
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
        
        AI_SERVER_URL = settings.AI_SERVER_URL
        
        try:
            response = requests.post(
                f"{AI_SERVER_URL}/api/analyze",
                json={
                    "video_id": str(video.id),
                    "session_id": str(new_session.id),
                    "video_url": video.s3_key,  
                },
                timeout=10  
            )
            response.raise_for_status() 
            
            res_data = response.json()
            logger.info(f"✅ AI Response: {res_data}")
            new_session.status = "processing"
            db.commit()
            
        except requests.exceptions.Timeout:
            logger.error("❌ AI Server Timeout (10s)! (Pending retry)")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Lỗi kết nối AI Server: {e}")
            new_session.status = "failed"
            new_session.failure_reason = f"Lỗi gọi AI: {str(e)}"
            db.commit()
                
        return new_session
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ START ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi khởi tạo phiên phân tích.")


# 🔄 2. SYNC ANALYSIS (WEBHOOK TỪ AI)
@router.post("/internal/sync-analysis")
def sync_analysis_from_ai(
    payload: AISyncPayload = Body(...), 
    db: Session = Depends(get_db),
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")
):
    if x_internal_secret != INTERNAL_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized - Sai Secret Key")

    try:
        session = None
        if payload.session_id:
            session = db.query(AnalysisSession).filter(AnalysisSession.id == payload.session_id).first()
        elif payload.video_id:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.video_id == payload.video_id,
                AnalysisSession.status.in_(["pending", "processing"]) 
            ).first()
            
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên phân tích (Session) tương ứng.")

        # CẬP NHẬT DỮ LIỆU CHÍNH
        session.finished_at = datetime.utcnow()
        session.processed_video_path = payload.processed_video_path 
        session.status = payload.status or "completed" 
        session.max_prob = float(payload.max_prob) if payload.max_prob else 0.0

        if session.status == "failed":
            session.failure_reason = payload.failure_reason or "AI processing failed (Không rõ lý do)"

        if payload.analysis_hash:
            session.analysis_hash = payload.analysis_hash

        # CẬP NHẬT EVENTS (VỚI TRY...EXCEPT BẢO VỆ TỪNG DÒNG)
        db.query(AnalysisEvent).filter(AnalysisEvent.session_id == session.id).delete()
        
        for i, ev in enumerate(payload.events):
            if not isinstance(ev, dict): continue
            
            try:
                new_event = AnalysisEvent(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    event_type=str(ev.get("label") or ev.get("type") or "violence"),
                    score=float(ev.get("score") or ev.get("peak_prob") or ev.get("max_prob") or 0.0),
                    t_start=float(ev.get("start") or ev.get("start_frame") or 0.0),
                    t_end=float(ev.get("end") or ev.get("end_frame") or 0.0),
                    # 🔥 DÙNG HÀM SAFE_JSON BỌC THÉP
                    payload=safe_json(ev.get("metadata") or ev), 
                    ml_review_status="pending", 
                    event_hash=f"{session.id}_{i}_{uuid.uuid4().hex[:4]}",
                    created_at=datetime.utcnow()
                )
                db.add(new_event)
            except Exception as ev_err:
                logger.warning(f"⚠️ Bỏ qua Event bị lỗi ({ev}): {ev_err}")
                continue # Nếu 1 event lỗi, bỏ qua nó, cứu các event còn lại
        
        db.commit()
        logger.info(f"✅ Sync SUCCESS for Session {session.id}")
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
    
    data = jsonable_encoder(session)

    # Lấy BASE_URL của Backend (có thể lấy từ config hoặc hardcode localhost lúc dev)
    # Nếu sếp deploy lên host, nhớ sửa cái này thành URL thật nghen!
    BACKEND_URL = getattr(settings, 'API_BASE_URL', "http://localhost:8000")

    # ✅ BƯỚC 1: LẤY LINK VIDEO GỐC 
    video = db.query(Video).filter(Video.id == session.video_id).first()
    if video and video.s3_key:
        data["video_url"] = f"{BACKEND_URL}/api/v1/videos/stream?s3_key={video.s3_key}"
    else:
        data["video_url"] = ""

    # ✅ BƯỚC 2: XỬ LÝ VIDEO ĐÃ PHÂN TÍCH (ĐÃ FIX LỖI CORS CỦA RUNPOD)
    if session.processed_video_path:
        path = session.processed_video_path
        
        # Nếu AI ngây thơ trả về nguyên cái link RunPod dài ngoằng (có chữ http)
        if path.startswith("http"):
            # Chúng ta sẽ dùng thủ thuật cắt chuỗi để bóc lấy cái s3_key thật sự
            # S3 key thường bắt đầu từ thư mục 'outputs/'
            if "/outputs/" in path:
                s3_key = "outputs/" + path.split("/outputs/", 1)[1]
            else:
                # Backup nếu path dị: bóc phần cuối cùng sau dấu gạch chéo
                s3_key = path.split("?")[0].split("/")[-1] 
        else:
            # Nếu AI ngoan ngoãn trả về s3_key thuần túy
            s3_key = path

        # 🚀 CƯỠNG CHẾ ÉP QUA PHỄU PROXY CỦA BACKEND 8000
        data["processed_video_url"] = f"{BACKEND_URL}/api/v1/videos/stream?s3_key={s3_key}"
    else:
        data["processed_video_url"] = None

    data["events"] = jsonable_encoder(events)

    return JSONResponse(content=data)