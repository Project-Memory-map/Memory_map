from sqlalchemy.orm import Session

from app.modules.explore import repository
from app.modules.explore.schemas import BoundingBox, PublicPinResponse


def list_public_pins(db: Session, box: BoundingBox) -> list[PublicPinResponse]:
    return [PublicPinResponse.model_validate(dict(row)) for row in repository.find_public_pins(db, box)]
