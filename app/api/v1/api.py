from fastapi import APIRouter
from app.api.v1.endpoints import (
    videos,
    analysis,
    realtime,
    auth,
    profile,
    feedback,
    reports,
    admin_dashboard,
    admin_users,
    admin_analysis,
    admin_ml_review,
    admin_reports,
)

api_router = APIRouter()

# --- USER PORTAL ENDPOINTS ---
api_router.include_router(auth.router, prefix="/auth", tags=["A. Authentication"])
api_router.include_router(profile.router, prefix="/profile", tags=["B. Profile"])
api_router.include_router(videos.router, prefix="/videos", tags=["C. Video Management"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["D. Analysis"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["D2. Realtime Camera"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["E. Feedback"])
api_router.include_router(reports.router, prefix="/reports", tags=["F. Reports"])

# --- ADMIN PORTAL ENDPOINTS ---
api_router.include_router(admin_dashboard.router, prefix="/admin/dashboard", tags=["Admin B. Dashboard"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["Admin C. User Management"])
api_router.include_router(admin_analysis.router, prefix="/admin/analysis", tags=["Admin D. Analysis Management"])
api_router.include_router(admin_ml_review.router, prefix="/admin/ml-review", tags=["Admin E. ML Review"])
api_router.include_router(admin_reports.router, prefix="/admin/reports", tags=["Admin F. Reports & Moderation"])
