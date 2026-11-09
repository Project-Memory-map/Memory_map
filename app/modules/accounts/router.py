import os
import shutil
from fastapi import UploadFile, File, Form
from app.modules.accounts.deps import get_current_user # hoặc hàm lấy user hiện tại của nhóm

@router.put("/profile")
def update_profile(
    display_name: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Kiểm tra độ dài tên hiển thị
    if display_name:
        if len(display_name.strip()) > 100:
            raise HTTPException(status_code=400, detail="Tên hiển thị không được vượt quá 100 ký tự")
        current_user.display_name = display_name.strip()

    if bio is not None:
        current_user.bio = bio.strip()

    # Kiểm tra và lưu file ảnh đại diện (<= 5MB)
    if avatar:
        # 5MB = 5 * 1024 * 1024 bytes
        MAX_SIZE = 5 * 1024 * 1024
        contents = avatar.file.read()
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="Ảnh đại diện không được vượt quá 5MB")
        
        # Reset con trỏ file sau khi đọc độ lớn
        avatar.file.seek(0)
        
        # Thư mục lưu avatar
        os.makedirs("uploads/avatars", exist_ok=True)
        file_path = f"uploads/avatars/user_{current_user.id}_{avatar.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
            
        current_user.avatar_url = f"/{file_path}"

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Cập nhật hồ sơ thành công",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "display_name": current_user.display_name,
            "bio": getattr(current_user, "bio", None),
            "avatar_url": current_user.avatar_url
        }
    }