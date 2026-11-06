from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import build_response


class AppException(Exception):
    status_code = 400
    error = "BAD_REQUEST"
    message = "Yêu cầu không hợp lệ"

    def __init__(self, message: str | None = None, data=None):
        self.message = message or self.message
        self.data = data
        super().__init__(self.message)


class UnauthorizedException(AppException):
    status_code = 401
    error = "UNAUTHORIZED"
    message = "Bạn cần đăng nhập để tiếp tục"


class ForbiddenException(AppException):
    status_code = 403
    error = "FORBIDDEN"
    message = "Bạn không có quyền thực hiện thao tác này"


class NotFoundException(AppException):
    status_code = 404
    error = "NOT_FOUND"
    message = "Không tìm thấy dữ liệu"


class ConflictException(AppException):
    status_code = 409
    error = "CONFLICT"
    message = "Dữ liệu đã tồn tại"


class TooManyRequestsException(AppException):
    status_code = 429
    error = "TOO_MANY_REQUESTS"
    message = "Bạn thao tác quá nhanh, vui lòng thử lại sau"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException):
        return build_response(exc.status_code, exc.message, request, error=exc.error, data=exc.data)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(part) for part in item["loc"][1:]), "message": item["msg"]}
            for item in exc.errors()
        ]
        return build_response(422, "Dữ liệu gửi lên không hợp lệ", request, error="VALIDATION_ERROR", data=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        message = "Không tìm thấy đường dẫn" if exc.status_code == 404 else str(exc.detail)
        return build_response(exc.status_code, message, request, error="HTTP_ERROR")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return build_response(500, "Lỗi hệ thống, vui lòng thử lại sau", request, error="INTERNAL_ERROR")
