from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 1. Tạo engine kết nối (Chỉ cần create_engine là đủ)
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

# 2. Tạo SessionLocal để các API có thể mở/đóng kết nối
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Định nghĩa Base class cho các Models
Base = declarative_base()

# 4. Dependency: Hàm này giúp các API lấy Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()