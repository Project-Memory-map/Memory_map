from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.explore.schemas import BoundingBox
from app.modules.memories.models import Memory

PUBLIC_PIN_LIMIT = 500


def find_public_pins(db: Session, box: BoundingBox):
    statement = (
        select(
            Memory.id,
            Memory.title,
            Memory.place_name,
            Memory.memory_date,
            Memory.latitude,
            Memory.longitude,
            User.display_name.label("author_name"),
        )
        .join(User, User.id == Memory.user_id)
        .where(
            Memory.visibility == "public",
            Memory.status == "active",
            Memory.deleted_at.is_(None),
            User.status == "active",
            Memory.latitude.between(box.south, box.north),
            Memory.longitude.between(box.west, box.east),
        )
        .order_by(Memory.memory_date.desc(), Memory.id.desc())
        .limit(PUBLIC_PIN_LIMIT)
    )
    return db.execute(statement).mappings().all()
