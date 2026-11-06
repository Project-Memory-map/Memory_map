from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import check_database
from app.core.errors import NotFoundException, register_exception_handlers
from app.core.response import build_response
from app.core.storage import ensure_upload_dirs
from app.models import register_models
from app.modules.accounts.router import router as accounts_router
from app.modules.admin.router import router as admin_router
from app.modules.explore.router import router as explore_router
from app.modules.memories.router import router as memories_router

APP_DIR = Path(__file__).resolve().parent

MODULE_ROUTERS = {
    "accounts": accounts_router,
    "memories": memories_router,
    "explore": explore_router,
    "admin": admin_router,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_models()
    ensure_upload_dirs()
    yield


app = FastAPI(title="Bản đồ Ký ức API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)


@app.get("/api/health", tags=["Core"])
def health(request: Request):
    database_ok = check_database()
    status_code = 200 if database_ok else 503
    message = "Hệ thống hoạt động bình thường" if database_ok else "Không kết nối được cơ sở dữ liệu"
    return build_response(status_code, message, request, data={"database": database_ok})


for module_name, module_router in MODULE_ROUTERS.items():
    app.include_router(module_router)
    app.mount(
        f"/{module_name}",
        StaticFiles(directory=APP_DIR / "modules" / module_name / "ui", html=True),
        name=f"{module_name}-ui",
    )



@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(path: str):
    raise NotFoundException("Chức năng này chưa được xây dựng hoặc đường dẫn API không tồn tại")


app.mount("/", StaticFiles(directory=APP_DIR / "shared", html=True), name="shared-ui")
