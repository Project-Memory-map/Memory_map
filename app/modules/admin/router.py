from fastapi import APIRouter, Depends

from app.modules.accounts.deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["M4 - Quản trị"], dependencies=[Depends(require_admin)])
