from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.report import Report
from app.models.analysis import AnalysisEvent, AnalysisSession

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """
    B1 & B2. View System Stats & Pending Tasks:
    Lấy tổng quan số liệu hệ thống và các tác vụ cần Admin xử lý.
    """
    # 1. System Stats cơ bản
    total_users = db.query(User).count()
    total_sessions = db.query(AnalysisSession).count()
    
    # 2. Pending Tasks (Công việc chờ xử lý)
    pending_reports = db.query(Report).filter(Report.status == "open").count()
    pending_ml_reviews = db.query(AnalysisEvent).filter(AnalysisEvent.ml_review_status == "pending").count()
    
    return {
        "system_stats": {
            "total_users": total_users,
            "total_analysis_sessions": total_sessions
        },
        "pending_tasks": {
            "open_reports": pending_reports,
            "pending_ml_reviews": pending_ml_reviews
        }
    }