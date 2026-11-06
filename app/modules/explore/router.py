from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.explore import service
from app.modules.explore.schemas import BoundingBox

router = APIRouter(prefix="/api/explore", tags=["M3 - Khám phá"])


@router.get("/pins")
def list_public_pins(request: Request, box: Annotated[BoundingBox, Query()], db: Session = Depends(get_db)):
    pins = service.list_public_pins(db, box)
    return build_response(200, "Lấy danh sách ghim công khai thành công", request, data=pins)
