from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    facebook_id: str | None
    email: str | None
    display_name: str
    role: str
    password_hash: str | None
    status: str
    token_version: int