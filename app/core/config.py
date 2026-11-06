from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Ban Do Ky Uc"
    app_env: str = "dev"

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ban_do_ky_uc"

    jwt_secret_key: str = "doi-chuoi-nay-trong-file-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    media_secret_key: str = "doi-chuoi-nay-trong-file-env"
    media_url_expire_seconds: int = 3600
    upload_dir: Path = BASE_DIR / "uploads"

    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

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
