from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings
from app.core.database import UserRepository
from app.modules.accounts.router import router as accounts_router
from app.modules.accounts.services.facebook_auth import FacebookAuthService


def create_app(
    settings: Settings | None = None,
    facebook_auth: FacebookAuthService | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.user_repository.initialize()
        yield

    app = FastAPI(title="Bản đồ Ký ức API", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.user_repository = UserRepository(app_settings.database_path)
    app.state.facebook_auth = facebook_auth or FacebookAuthService(app_settings)

    @app.middleware("http")
    async def disable_api_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(accounts_router, prefix="/api/accounts")
    return app


app = create_app()