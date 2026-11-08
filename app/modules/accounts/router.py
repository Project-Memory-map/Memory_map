from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Import db và security từ core của dự án
from app.core.database import get_db
from app.core.security import create_access_token
from app.models import User
from .schemas import GoogleAuthRequest

# Nếu trong router.py đã có sẵn router = APIRouter(...) thì không cần khai báo lại dòng này
router = APIRouter(prefix="/auth", tags=["Tài khoản & Xác thực"])

GOOGLE_CLIENT_ID = "855043085255-ohk0ptaea6h83v2dr6p7cv5nq90ut9ed.apps.googleusercontent.com"

@router.post("/google")
def google_login(req: GoogleAuthRequest, db: Session = Depends(get_db)):
    # 1. Xác thực Google Token
    try:
        id_info = id_token.verify_oauth2_token(
            req.id_token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
    except Exception:
        # Tiêu chí AC3: Token không hợp lệ hoặc lỗi
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đăng nhập Google chưa hoàn tất"
        )

    email = id_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Không lấy được email từ Google")
    
    email = email.lower()
    email_verified = id_info.get("email_verified", False)
    display_name = id_info.get("name", "Người dùng")
    avatar = id_info.get("picture", None)

    # 2. Tìm tài khoản trong database
    user = db.query(User).filter(User.email == email).first()

    # Tiêu chí AC4: Chặn tài khoản bị khóa
    if user and not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Tài khoản của bạn đã bị khóa"
        )

    # Tiêu chí AC2: Trùng email đã có -> tự động liên kết
    if user:
        if email_verified and not getattr(user, "avatar_url", None) and avatar:
            user.avatar_url = avatar
            db.commit()
    else:
        # Tiêu chí AC1: Đăng nhập lần đầu -> tạo tài khoản mới
        user = User(
            email=email,
            display_name=display_name[:100],
            avatar_url=avatar,
            role="user",
            is_active=True,
            token_version=1
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Tạo JWT token
    token = create_access_token({
        "sub": str(user.id),
        "token_version": getattr(user, "token_version", 1),
        "role": getattr(user, "role", "user")
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "display_name": user.display_name,
        "role": getattr(user, "role", "user")
    }