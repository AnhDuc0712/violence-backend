from sqlalchemy import text
from app.core.database import engine

def disable_rls():
    try:
        with engine.begin() as conn:  # ✅ tự commit / rollback
            conn.execute(text("ALTER TABLE user_credentials DISABLE ROW LEVEL SECURITY;"))
            conn.execute(text("ALTER TABLE users DISABLE ROW LEVEL SECURITY;"))

        print("✅ Đã tắt Row-Level Security thành công!")

    except Exception as e:
        print("❌ Lỗi khi tắt RLS:", e)


if __name__ == "__main__":
    disable_rls()