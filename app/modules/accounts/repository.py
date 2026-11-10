from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from app.modules.accounts.models import OAuthAccount, User
from app.modules.accounts.services.facebook_auth import FacebookProfile


class FacebookAccountConflict(Exception):
    """The Facebook identity is already attached to a different account."""


class UserRepository:
    def __init__(self, engine: Engine, database_path: str | None = None) -> None:
        self._sessions = sessionmaker(bind=engine, expire_on_commit=False)
        self.database_path = database_path

    def get_by_id(self, user_id: int) -> User | None:
        with self._sessions() as session:
            return session.get(User, user_id)

    def get_providers(self, user_id: int) -> list[str]:
        with self._sessions() as session:
            providers = list(
                session.scalars(
                    select(OAuthAccount.provider).where(OAuthAccount.user_id == user_id)
                )
            )
            if "facebook" not in providers:
                user = session.get(User, user_id)
                if user is not None and user.facebook_id:
                    providers.append("facebook")
            return providers

    def resolve_facebook_profile(self, profile: FacebookProfile) -> User:
        email = profile.email.strip().lower() if profile.email else None
        with self._sessions.begin() as session:
            user = session.scalar(
                select(User).where(User.facebook_id == profile.facebook_id)
            )
            if user is None:
                user = session.scalar(
                    select(User)
                    .join(OAuthAccount, OAuthAccount.user_id == User.id)
                    .where(
                        OAuthAccount.provider == "facebook",
                        OAuthAccount.provider_user_id == profile.facebook_id,
                    )
                )
            if user is None and email:
                user = session.scalar(select(User).where(User.email == email))

            if user is None:
                user = User(
                    email=email,
                    facebook_id=profile.facebook_id,
                    password_hash=None,
                    display_name=profile.display_name,
                    role="user",
                    status="active",
                )
                session.add(user)
                session.flush()
            else:
                if user.facebook_id and user.facebook_id != profile.facebook_id:
                    raise FacebookAccountConflict
                linked_account = session.scalar(
                    select(OAuthAccount).where(
                        OAuthAccount.user_id == user.id,
                        OAuthAccount.provider == "facebook",
                    )
                )
                if (
                    linked_account is not None
                    and linked_account.provider_user_id != profile.facebook_id
                ):
                    raise FacebookAccountConflict
                user.facebook_id = profile.facebook_id

            link = session.scalar(
                select(OAuthAccount).where(
                    OAuthAccount.provider == "facebook",
                    OAuthAccount.provider_user_id == profile.facebook_id,
                )
            )
            if link is None:
                session.add(
                    OAuthAccount(
                        user_id=user.id,
                        provider="facebook",
                        provider_user_id=profile.facebook_id,
                    )
                )
            elif link.user_id != user.id:
                raise FacebookAccountConflict

            if user.status != "locked":
                user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.flush()
            session.refresh(user)
            return user
