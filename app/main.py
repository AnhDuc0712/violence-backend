import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.v1.endpoints import realtime
from app.api.v1.api import api_router
from app.core.config import settings
from dotenv import load_dotenv

from app.api.v1.endpoints import realtime
load_dotenv()
# Khởi tạo logger để ghi lại lỗi
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/swagger",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
# 🛠️ [DEBUG 422] MIDDLEWARE BẮT LỖI VALIDATION
# Thêm đoạn này để ép FastAPI phải "khai" ra lỗi nằm ở đâu
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Đọc body thô mà Client (React) gửi lên
    body = await request.body()
    body_str = body.decode() if body else "Empty Body"
    
    # In cực mạnh ra Console để mày soi
    print("\n" + "="*50)
    print(f"❌ PHÁT HIỆN LỖI 422 TẠI: {request.url}")
    print(f"🔍 CHI TIẾT LỖI (Pydantic): {exc.errors()}")
    print(f"📥 DỮ LIỆU NHẬN ĐƯỢC: {body_str}")
    print("="*50 + "\n")
    print("S3:", settings.S3_ACCESS_KEY_ID)
    # Ghi vào log file nếu có cấu hình
    logger.error(f"422 Validation Error: {exc.errors()} | Body: {body_str}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body_received": body_str,
            "message": "Dữ liệu gửi lên không đúng định dạng Schema của Backend."
        },
    )
# Đăng ký Router
app.include_router(api_router, prefix=settings.API_V1_STR)
api_router.include_router(realtime.router, prefix="", tags=["realtime"])

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}. Visit /swagger for docs.",
    }