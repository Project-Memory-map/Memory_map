"""Kết nối MySQL bằng SQLAlchemy.

Cách dùng trong router:
    from sqlalchemy.orm import Session
    from app.core.database import get_db

    @router.get("/...")
    def handler(db: Session = Depends(get_db)):
        ...
"""
from collections.abc import Generator

from sqlalchemy import BigInteger, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Kiểu khóa chính dùng chung cho các model (khớp BIGINT UNSIGNED trong schema.sql)
BigIntId = BigInteger

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
