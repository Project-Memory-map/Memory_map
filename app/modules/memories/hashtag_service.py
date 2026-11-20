"""US-MEM-010 & FR-3.6 (T05B590) – Chuẩn hóa, kiểm tra BR-06, lưu và gợi ý hashtag bằng Gemini AI."""
from __future__ import annotations

import json
import logging
import re
import unicodedata

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationException
from app.modules.memories.models import Hashtag, Memory, MemoryHashtag

logger = logging.getLogger(__name__)

MAX_HASHTAGS_PER_MEMORY = 10
MAX_HASHTAG_LENGTH = 30
MAX_SUGGESTED_HASHTAGS = 6

MSG_INVALID_HASHTAG = "Hashtag chỉ gồm chữ, số, dấu gạch dưới (tối đa 30 ký tự)"
MSG_TOO_MANY_HASHTAGS = "Mỗi ký ức tối đa 10 hashtag"


def _is_valid_tag_chars(tag: str) -> bool:
    if not (1 <= len(tag) <= MAX_HASHTAG_LENGTH):
        return False
    return all(ch.isalpha() or ch.isdigit() or ch == "_" for ch in tag)


def normalize_hashtag(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValidationException(MSG_INVALID_HASHTAG)
    trimmed = raw.strip()
    if not trimmed:
        raise ValidationException(MSG_INVALID_HASHTAG)
    without_hash = trimmed.lstrip("#")
    if not without_hash or any(ch.isspace() for ch in without_hash):
        raise ValidationException(MSG_INVALID_HASHTAG)
    normalized = unicodedata.normalize("NFC", without_hash).lower()
    if not _is_valid_tag_chars(normalized):
        raise ValidationException(MSG_INVALID_HASHTAG)
    return normalized


def parse_hashtags(
    raw: str | list[str] | None,
    *,
    require_non_empty: bool = False,
) -> list[str]:
    if raw is None:
        if require_non_empty:
            raise ValidationException(MSG_INVALID_HASHTAG)
        return []

    tokens: list[object]
    if isinstance(raw, list):
        if not raw:
            if require_non_empty:
                raise ValidationException(MSG_INVALID_HASHTAG)
            return []
        tokens = raw
    elif isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            if require_non_empty:
                raise ValidationException(MSG_INVALID_HASHTAG)
            return []
        tokens = [part for part in re.split(r"[\s,;]+", stripped) if part]
    else:
        raise ValidationException(MSG_INVALID_HASHTAG)

    unique_tags: list[str] = []
    for token in tokens:
        tag = normalize_hashtag(token)
        if tag not in unique_tags:
            unique_tags.append(tag)

    if len(unique_tags) > MAX_HASHTAGS_PER_MEMORY:
        raise ValidationException(MSG_TOO_MANY_HASHTAGS)
    return unique_tags


def get_or_create_hashtag(db: Session, tag_name: str) -> Hashtag:
    existing = db.scalar(
        select(Hashtag).where(func.lower(Hashtag.name) == tag_name)
    )
    if existing is not None:
        return existing
    hashtag = Hashtag(name=tag_name)
    db.add(hashtag)
    db.flush()
    return hashtag


def sync_memory_hashtags(
    db: Session,
    memory: Memory,
    raw_hashtags: str | list[str] | None,
    raw_ai_hashtags: str | list[str] | None = None,
    *,
    replace: bool = False,
) -> list[str]:
    new_tags = parse_hashtags(raw_hashtags, require_non_empty=not replace)
    ai_tags = set(parse_hashtags(raw_ai_hashtags, require_non_empty=False))

    existing_links = db.scalars(
        select(MemoryHashtag).where(MemoryHashtag.memory_id == memory.id)
    ).all()
    existing_by_name: dict[str, MemoryHashtag] = {}
    for link in existing_links:
        tag_obj = link.hashtag or db.get(Hashtag, link.hashtag_id)
        if tag_obj is not None:
            existing_by_name[tag_obj.name.lower()] = link

    if replace:
        target_names = new_tags
    else:
        target_names = list(existing_by_name.keys())
        for tag in new_tags:
            if tag not in target_names:
                target_names.append(tag)

    if len(target_names) > MAX_HASHTAGS_PER_MEMORY:
        raise ValidationException(MSG_TOO_MANY_HASHTAGS)

    if replace:
        to_remove_ids = [
            link.hashtag_id
            for name, link in existing_by_name.items()
            if name not in set(target_names)
        ]
        if to_remove_ids:
            db.execute(
                delete(MemoryHashtag).where(
                    MemoryHashtag.memory_id == memory.id,
                    MemoryHashtag.hashtag_id.in_(to_remove_ids),
                )
            )
            db.flush()

    for tag_name in new_tags:
        source = "ai" if tag_name in ai_tags else "manual"
        if tag_name in existing_by_name:
            if tag_name in ai_tags:
                existing_by_name[tag_name].source = "ai"
            continue
        hashtag = get_or_create_hashtag(db, tag_name)
        db.add(
            MemoryHashtag(
                memory_id=memory.id,
                hashtag_id=hashtag.id,
                source=source,
            )
        )
    db.flush()
    db.expire(memory, ["hashtag_links"])
    return sorted(target_names)


def _clean_ai_candidate_tags(raw_items: list[str]) -> list[str]:
    cleaned_tags: list[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            continue
        token = unicodedata.normalize("NFC", item.strip().lstrip("#")).lower()
        token = re.sub(r"\s+", "", token)
        token = "".join(ch for ch in token if ch.isalpha() or ch.isdigit() or ch == "_")
        if 2 <= len(token) <= MAX_HASHTAG_LENGTH and _is_valid_tag_chars(token):
            if token not in cleaned_tags:
                cleaned_tags.append(token)
        if len(cleaned_tags) >= MAX_SUGGESTED_HASHTAGS:
            break
    return cleaned_tags


def _suggest_with_gemini(
    title: str | None,
    content: str | None,
    place_name: str | None,
) -> list[str]:
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        return []

    context_parts = []
    if title and title.strip():
        context_parts.append(f"Tiêu đề: {title.strip()}")
    if place_name and place_name.strip():
        context_parts.append(f"Địa điểm: {place_name.strip()}")
    if content and content.strip():
        context_parts.append(f"Nội dung: {content.strip()}")
    if not context_parts:
        return []

    prompt = (
        "Bạn là trợ lý gợi ý hashtag cho ứng dụng nhật ký du lịch và kỷ niệm 'Bản đồ Ký ức'.\n"
        "Dựa vào thông tin ký ức dưới đây, hãy gợi ý từ 4 đến 6 hashtag tiếng Việt (viết liền, "
        "không dấu # ở đầu, chữ thường, chỉ gồm chữ cái tiếng Việt/số/dấu gạch dưới, tối đa 30 ký tự mỗi tag).\n"
        "Chỉ trả về một mảng JSON gồm các chuỗi string, ví dụ: [\"dalat\", \"sanmay\", \"kyniem\"].\n"
        "Không giải thích thêm.\n\n"
        + "\n".join(context_parts)
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }

    with httpx.Client(timeout=settings.gemini_timeout_seconds) as client:
        response = client.post(url, params={"key": api_key}, json=payload)
        response.raise_for_status()
        body = response.json()

    candidates = body.get("candidates") or []
    if not candidates:
        return []
    parts = (candidates[0].get("content") or {}).get("parts") or []
    raw_text = "".join(part.get("text", "") for part in parts).strip()
    if not raw_text:
        return []

    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            parsed = parsed.get("hashtags", [])
        if isinstance(parsed, list):
            return _clean_ai_candidate_tags([str(x) for x in parsed])
    except json.JSONDecodeError:
        tokens = [t for t in re.split(r"[\s,;\"'\[\]]+", raw_text) if t]
        return _clean_ai_candidate_tags(tokens)
    return []


def _suggest_locally(
    title: str | None = None,
    content: str | None = None,
    place_name: str | None = None,
) -> list[str]:
    candidates: list[str] = []
    for raw_piece in (place_name or "", title or "", content or ""):
        for piece in re.split(r"[,.;:!?/\\|\-–—()\[\]\n\r]+", raw_piece):
            words = [w for w in piece.strip().split() if w]
            if not words:
                continue
            joined = unicodedata.normalize("NFC", "".join(words)).lower()
            cleaned = "".join(ch for ch in joined if ch.isalpha() or ch.isdigit())
            if 2 <= len(cleaned) <= MAX_HASHTAG_LENGTH and cleaned not in candidates:
                candidates.append(cleaned)
            for word in words:
                w_clean = "".join(
                    ch
                    for ch in unicodedata.normalize("NFC", word).lower()
                    if ch.isalpha() or ch.isdigit()
                )
                if 3 <= len(w_clean) <= MAX_HASHTAG_LENGTH and w_clean not in candidates:
                    candidates.append(w_clean)
            if len(candidates) >= 8:
                break
        if len(candidates) >= 8:
            break

    if not candidates:
        candidates = ["kyuc", "hanhtrinh", "kyniem"]
    return candidates[:MAX_SUGGESTED_HASHTAGS]


def suggest_hashtags_from_text(
    title: str | None = None,
    content: str | None = None,
    place_name: str | None = None,
) -> dict[str, object]:
    try:
        gemini_tags = _suggest_with_gemini(title=title, content=content, place_name=place_name)
        if gemini_tags:
            return {"hashtags": gemini_tags, "engine": "gemini"}
    except Exception as exc:
        logger.warning("Gemini hashtag suggestion fallback to local: %s", exc)

    return {
        "hashtags": _suggest_locally(title=title, content=content, place_name=place_name),
        "engine": "local",
    }