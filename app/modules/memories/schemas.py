from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class MemoryDetailResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_public: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True