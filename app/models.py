from sqlalchemy.orm import configure_mappers

from app.modules.accounts.models import OAuthAccount, PasswordResetToken, User
from app.modules.admin.models import AdminAction
from app.modules.explore.models import Region
from app.modules.memories.models import Hashtag, Media, Memory, MemoryHashtag, Trip, TripMemory

ALL_MODELS = (
    User,
    OAuthAccount,
    PasswordResetToken,
    Region,
    Memory,
    Media,
    Trip,
    TripMemory,
    Hashtag,
    MemoryHashtag,
    AdminAction,
)


def register_models() -> None:
    configure_mappers()
