from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    level: Mapped[str] = mapped_column(Enum("province", "city", "other"), default="province")
