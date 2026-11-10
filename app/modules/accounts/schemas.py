from pydantic import BaseModel, Field


class FacebookTokenRequest(BaseModel):
    access_token: str = Field(min_length=1)