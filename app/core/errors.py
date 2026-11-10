import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import build_response

logger = logging.getLogger("bandokyuc")


class AppException(Exception):
    status_code = 400
    error = "BAD_REQUEST"
    message = "Yêu cầu không hợp lệ"

    def __init__(self, message: str | None = None, data=None):
        self.message = message or self.message
        self.data = data
        super().__init__(self.message)


class BadRequestException(AppException):
    pass


class ValidationException(AppException):
    status_code = 422
    error = "VALIDATION_ERROR"
    message = "Dữ liệu gửi lên không hợp lệ"


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


class PayloadTooLargeException(AppException):
    status_code = 413
    error = "PAYLOAD_TOO_LARGE"
    message = "Tệp tải lên quá lớn"


class TooManyRequestsException(AppException):
    status_code = 429
    error = "TOO_MANY_REQUESTS"
    message = "Bạn thao tác quá nhanh, vui lòng thử lại sau"


class ServiceUnavailableException(AppException):
    status_code = 503
    error = "SERVICE_UNAVAILABLE"
    message = "Dịch vụ tạm thời không khả dụng"


_TYPE_MESSAGES = {
    "missing": "Vui lòng nhập trường này",
    "string_too_short": "Giá trị quá ngắn",
    "string_too_long": "Giá trị quá dài",
    "int_parsing": "Giá trị phải là số nguyên",
    "float_parsing": "Giá trị phải là số",
    "date_from_datetime_parsing": "Ngày không hợp lệ",
    "date_parsing": "Ngày không hợp lệ",
    "greater_than_equal": "Giá trị quá nhỏ",
    "less_than_equal": "Giá trị quá lớn",
    "enum": "Giá trị không hợp lệ",
    "literal_error": "Giá trị không hợp lệ",
    "value_error": None,
}


def _friendly(item: dict) -> str:
    kind = item.get("type", "")
    if kind == "value_error":
        message = str(item.get("msg", ""))
        return message.removeprefix("Value error, ")
    if kind.startswith("value_error") and "email" in str(item.get("msg", "")).lower():
        return "Email không hợp lệ"
    return _TYPE_MESSAGES.get(kind) or str(item.get("msg", "Giá trị không hợp lệ"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException):
        return build_response(exc.status_code, exc.message, request, error=exc.error, data=exc.data)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(part) for part in item["loc"][1:]), "message": _friendly(item)}
            for item in exc.errors()
        ]
        message = details[0]["message"] if len(details) == 1 else "Dữ liệu gửi lên không hợp lệ"
        if details and any(item.get("type") == "value_error" for item in exc.errors()):
            message = next(
                _friendly(item) for item in exc.errors() if item.get("type") == "value_error"
            )
        return build_response(422, message, request, error="VALIDATION_ERROR", data=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        message = "Không tìm thấy đường dẫn" if exc.status_code == 404 else str(exc.detail)
        return build_response(exc.status_code, message, request, error="HTTP_ERROR")

    @app.exception_handler(DBAPIError)
    async def handle_database_error(request: Request, exc: DBAPIError):
        code = exc.orig.args[0] if getattr(exc, "orig", None) is not None and exc.orig.args else None
        if code == 1644:  # SIGNAL từ trigger trong database/schema.sql (Phần 5)
            trigger_message = str(exc.orig.args[-1])  # vd "BR-06: Mỗi ký ức tối đa 10 ảnh"
            logger.warning("Trigger chặn thao tác tại %s: %s", request.url.path, trigger_message)
            return build_response(422, trigger_message, request, error="BUSINESS_RULE")
        if isinstance(exc, IntegrityError):
            return build_response(409, "Dữ liệu bị trùng hoặc không hợp lệ", request, error="CONFLICT")
        logger.exception("Lỗi cơ sở dữ liệu tại %s", request.url.path)
        return build_response(500, "Lỗi hệ thống, vui lòng thử lại sau", request, error="INTERNAL_ERROR")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Lỗi không mong muốn tại %s", request.url.path)
        return build_response(500, "Lỗi hệ thống, vui lòng thử lại sau", request, error="INTERNAL_ERROR")
