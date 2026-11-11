import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import false, func, or_, select, text
from sqlalchemy.dialects.mysql import match
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.explore.models import Region
from app.modules.explore.schemas import BoundingBox
from app.modules.memories.models import (
    Hashtag,
    Memory,
    MemoryHashtag,
)


PUBLIC_PIN_LIMIT = 500


def fold(value):
    value = unicodedata.normalize(
        "NFKD",
        (value or "").casefold(),
    ).replace("đ", "d")

    return "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )


def keyword(value):
    value = unicodedata.normalize(
        "NFC",
        (value or "").strip(),
    )

    if value and len(value) < 2:
        raise HTTPException(
            400,
            "Nhập ít nhất 2 ký tự",
        )

    if len(value) > 100:
        raise HTTPException(
            400,
            "Từ khóa tối đa 100 ký tự",
        )

    return value


def public_conditions():
    return (
        Memory.visibility == "public",
        Memory.status == "active",
        Memory.deleted_at.is_(None),
        User.status == "active",
    )


def search_mode(db):
    dialect = db.get_bind().dialect

    if dialect.name == "sqlite":
        connection = (
            db.connection()
            .connection
            .driver_connection
        )

        connection.create_function(
            "fold_text",
            1,
            fold,
            deterministic=True,
        )

        return "sqlite-demo"

    version = str(
        db.scalar(text("SELECT VERSION()"))
    )

    if "mariadb" in version.lower():
        return "mariadb-demo"

    return "mysql-ngram"


def build_query(
    db,
    box=None,
    q="",
    hashtags="",
    region="",
):
    q = keyword(q)

    stmt = (
        select(
            Memory.id,
            Memory.title,
            Memory.place_name,
            Memory.memory_date,
            Memory.latitude,
            Memory.longitude,
            User.display_name.label("author_name"),
        )
        .join(
            User,
            User.id == Memory.user_id,
        )
        .where(*public_conditions())
    )

    if box:
        if box.west <= box.east:
            longitude = Memory.longitude.between(
                box.west,
                box.east,
            )
        else:
            longitude = or_(
                Memory.longitude >= box.west,
                Memory.longitude <= box.east,
            )

        stmt = stmt.where(
            Memory.latitude.between(
                box.south,
                box.north,
            ),
            longitude,
        )

    if region:
        stmt = (
            stmt.join(
                Region,
                Region.id == Memory.region_id,
            )
            .where(Region.slug == region)
        )

    tags = {
        tag.lstrip("#").casefold()
        for tag in hashtags.split()
        if tag.lstrip("#")
    }

    if tags:
        linked = (
            select(MemoryHashtag.memory_id)
            .join(
                Hashtag,
                Hashtag.id == MemoryHashtag.hashtag_id,
            )
            .where(
                func.lower(Hashtag.name).in_(tags)
            )
        )

        stmt = stmt.where(
            Memory.id.in_(linked)
        )

    if q:
        mode = search_mode(db)

        if mode == "mysql-ngram":
            # Tham số tìm kiếm được bind qua SQLAlchemy.
            phrase = " ".join(
                re.findall(
                    r"\w+",
                    q,
                    flags=re.UNICODE,
                )
            )

            if not phrase:
                stmt = stmt.where(false())
            else:
                score = match(
                    Memory.title,
                    Memory.place_name,
                    against='"' + phrase + '"',
                ).in_boolean_mode()

                stmt = (
                    stmt.where(score > 0)
                    .order_by(score.desc())
                )

        else:
            # Chế độ tương thích local.
            # Không thay thế nghiệm thu FULLTEXT ngram.
            columns = [
                Memory.title,
                Memory.place_name,
            ]

            if mode == "sqlite-demo":
                columns = [
                    func.fold_text(column)
                    for column in columns
                ]
                needle = fold(q)

            else:
                columns = [
                    column.collate(
                        "utf8mb4_unicode_ci"
                    )
                    for column in columns
                ]
                needle = q

            stmt = stmt.where(
                or_(
                    *[
                        column.contains(
                            needle,
                            autoescape=True,
                        )
                        for column in columns
                    ]
                )
            )

    return stmt.order_by(
        Memory.memory_date.desc(),
        Memory.id.desc(),
    )


def find_public_pins(
    db: Session,
    box: BoundingBox,
    q="",
    hashtags="",
    region="",
):
    return (
        db.execute(
            build_query(
                db,
                box,
                q,
                hashtags,
                region,
            ).limit(PUBLIC_PIN_LIMIT)
        )
        .mappings()
        .all()
    )