import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from dotenv import load_dotenv
load_dotenv()
# Khởi tạo logger để ghi lại lỗi
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/swagger",
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

# CẤU HÌNH CORS
app.add_middleware(
    CORSMiddleware,
    # 🔥 TẠM THỜI MỞ "*" ĐỂ VERCEL GỌI ĐƯỢC NGAY
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cấu hình Media/Upload
settings.UPLOAD_DIR_PATH.mkdir(parents=True, exist_ok=True)
app.mount(settings.MEDIA_URL_PREFIX, StaticFiles(directory=settings.UPLOAD_DIR_PATH), name="media")

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="direct_uploads")
# Đăng ký Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}. Visit /swagger for docs.",
        "media_url_prefix": settings.MEDIA_URL_PREFIX,
    }