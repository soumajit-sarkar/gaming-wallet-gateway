from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class PlayerCreateRequest(APIModel):
    external_id: str = Field(min_length=1, max_length=100)
    username: str | None = Field(default=None, max_length=100)


class PlayerResponse(APIModel):
    id: int
    external_id: str
    username: str | None
    status: str
    created_at: datetime
    updated_at: datetime
