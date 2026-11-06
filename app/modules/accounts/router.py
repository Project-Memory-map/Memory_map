from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import build_response
from app.modules.accounts import service
from app.modules.accounts.deps import get_current_user
from app.modules.accounts.models import User
from app.modules.accounts.schemas import RegisterRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["M1 - Tài khoản"])


@router.post("/register", status_code=201)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    data = service.register(db, display_name=payload.display_name, email=payload.email, password=payload.password)
    return build_response(201, service.MSG_REGISTER_OK, request, data=data)


@router.get("/me")
def read_me(request: Request, current_user: User = Depends(get_current_user)):
    data = UserResponse.model_validate(current_user)
    return build_response(200, "Lấy thông tin tài khoản thành công", request, data=data)
