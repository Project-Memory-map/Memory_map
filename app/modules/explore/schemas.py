from datetime import date

from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def check_order(self):
        if self.south > self.north:
            raise ValueError(
                "Vùng bản đồ không hợp lệ"
            )

        # west > east được phép khi vùng nhìn
        # đi qua kinh tuyến ±180 độ.
        return self


class PublicPinResponse(BaseModel):
    id: int
    title: str
    place_name: str
    memory_date: date
    latitude: float
    longitude: float
    author_name: str