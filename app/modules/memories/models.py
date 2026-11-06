from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    region_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("regions.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"))
    memory_date: Mapped[date] = mapped_column(Date)
    place_name: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    visibility: Mapped[str] = mapped_column(Enum("private", "public"), default="private")
    status: Mapped[str] = mapped_column(Enum("active", "hidden"), default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    memory_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("memories.id", ondelete="CASCADE"))
    media_type: Mapped[str] = mapped_column(Enum("image", "video"))
    file_path: Mapped[str] = mapped_column(String(500))
    thumb_path: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TripMemory(Base):
    __tablename__ = "trip_memories"

    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True)
    memory_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Hashtag(Base):
    __tablename__ = "hashtags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MemoryHashtag(Base):
    __tablename__ = "memory_hashtags"

    memory_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True)
    hashtag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(Enum("manual", "ai"), default="manual")
