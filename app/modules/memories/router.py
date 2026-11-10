from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models import Memory, User
from .schemas import MemoryDetailResponse

# Import hàm lấy user hiện tại (nếu có đăng nhập)
# Nếu nhóm dùng deps chung thì import từ app.core.deps hoặc app.modules.accounts.deps
try:
    from app.modules.accounts.deps import get_current_user_optional
except ImportError:
    # Hàm dự phòng nếu dự án chưa viết get_current_user_optional
    def get_current_user_optional():
        return None

router = APIRouter(prefix="/memories", tags=["Quản lý Ký ức"])

@router.get("/{memory_id}", response_model=MemoryDetailResponse)
def get_memory_detail(
    memory_id: int, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    # 1. Tìm ký ức trong database
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy ký ức yêu cầu"
        )

    # 2. Kiểm tra phân quyền xem ký ức (BR-03, BR-04)
    # Nếu ký ức là riêng tư (is_public == False)
    is_public = getattr(memory, "is_public", True)
    if not is_public:
        # Nếu chưa đăng nhập hoặc không phải chủ sở hữu thì chặn
        if not current_user or current_user.id != memory.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Bạn không có quyền xem ký ức riêng tư này"
            )

    return memory