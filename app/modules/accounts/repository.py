from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User


def find_by_email(db: Session, email: str) -> User | None:
    # BR-08: email duy nhất, không phân biệt hoa thường.
    statement = select(User).where(func.lower(User.email) == email.lower())
    return db.execute(statement).scalar_one_or_none()


def create_user(db: Session, *, email: str, password_hash: str, display_name: str, last_login_at: datetime) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        role="user",
        status="active",
        token_version=0,
        last_login_at=last_login_at,
    )
    db.add(user)
    db.flush()
    return user
