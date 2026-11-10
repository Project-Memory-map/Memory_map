from datetime import datetime, timezone

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def build_response(status_code: int, message: str, request: Request, data=None, error: str | None = None) -> JSONResponse:
    body = {
        "statusCode": status_code,
        "message": message,
        "error": error,
        "data": data,
        "path": request.url.path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))
