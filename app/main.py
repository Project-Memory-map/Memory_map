"""Khởi tạo FastAPI: gắn API của 4 module + phục vụ giao diện (ui/) và JS (js/)."""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import check_database
from app.core.errors import NotFoundException, register_exception_handlers
from app.core.response import build_response
from app.models import register_models
from app.modules.accounts.facebook_router import router as facebook_router
from app.modules.accounts.logout_router import router as logout_router
from app.modules.accounts.router import router as accounts_router
from app.modules.admin.router import router as admin_router
from app.modules.explore.router import router as explore_router
from app.modules.memories.images_router import router as memory_images_router
from app.modules.memories.router import router as memories_router
from app.modules.memories.video_router import router as memory_videos_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

APP_DIR = Path(__file__).resolve().parent

MODULE_ROUTERS = {
    "accounts": accounts_router,
    "memories": memories_router,
    "explore": explore_router,
    "admin": admin_router,
}

app = FastAPI(title="Bản đồ Ký ức API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
register_models()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if not request.url.path.startswith("/api"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.get("/api/health", tags=["Core"])
def health(request: Request):
    """Kiểm tra kết nối MySQL."""
    database_ok = check_database()
    status_code = 200 if database_ok else 503
    message = "Hệ thống hoạt động bình thường" if database_ok else "Không kết nối được cơ sở dữ liệu"
    return build_response(status_code, message, request, data={"database": database_ok})


@app.get("/ban-do", include_in_schema=False)
def map_page():
    """Trang chủ bản đồ; trang mở đầu nằm ở / (shared/ui/index.html)."""
    return FileResponse(APP_DIR / "shared" / "ui" / "map.html")


# API + giao diện + JS của từng module
for module_name, module_router in MODULE_ROUTERS.items():
    app.include_router(module_router)
    module_dir = APP_DIR / "modules" / module_name
    # Xử lý phía trình duyệt: /<module>/js/*.js  (phải gắn trước /<module>)
    app.mount(f"/{module_name}/js", StaticFiles(directory=module_dir / "js"), name=f"{module_name}-js")
    # Giao diện: /<module>/*.html, *.css
    app.mount(f"/{module_name}", StaticFiles(directory=module_dir / "ui", html=True), name=f"{module_name}-ui")

app.include_router(facebook_router)        # US-ACC-004
app.include_router(logout_router)          # US-ACC-008
app.include_router(memory_images_router)   # US-MEM-003
app.include_router(memory_videos_router)   # US-MEM-004


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(path: str):
    """API chưa có ai làm thì giao diện nhận thông báo này thay vì lỗi trắng trang."""
    raise NotFoundException("Chức năng này chưa được xây dựng")


# Phần dùng chung: JS xử lý rồi giao diện (/, /css, /img)
app.mount("/js", StaticFiles(directory=APP_DIR / "shared" / "js"), name="shared-js")
app.mount("/", StaticFiles(directory=APP_DIR / "shared" / "ui", html=True), name="shared-ui")
