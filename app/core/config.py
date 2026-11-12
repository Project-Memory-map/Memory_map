"""Cấu hình hệ thống, đọc từ file .env ở thư mục gốc (copy từ .env.example).

Thành viên nào làm chức năng cần thêm cấu hình (JWT, SMTP, Google OAuth, Gemini...)
thì thêm biến vào class Settings và vào .env.example.
"""
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Ban Do Ky Uc"
    app_env: str = "dev"

    # MySQL – mỗi thành viên điền thông tin MySQL trên máy mình
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ban_do_ky_uc"

    # JWT – dùng chung cho mọi API cần đăng nhập
    jwt_secret: str = "doi-chuoi-nay-trong-file-env"
    access_token_minutes: int = 60 * 24

    # Facebook OAuth (US-ACC-004) & Media (US-MEM-003 / US-MEM-004)
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_redirect_uri: str = "http://127.0.0.1:8000/api/auth/facebook/callback"
    facebook_http_timeout_seconds: float = 5.0
    media_secret: str = "doi-chuoi-nay-trong-file-env-it-nhat-32-ky-tu"
    media_url_expire_seconds: int = 3600
    upload_dir: Path = BASE_DIR / "uploads"

    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in {"dev", "development", "local", "test"}

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
