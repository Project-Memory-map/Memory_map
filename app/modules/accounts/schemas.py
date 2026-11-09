from pydantic import BaseModel, Field
from typing import Optional

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)