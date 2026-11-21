from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentClient
from app.db.session import get_db
from app.schemas.player import PlayerCreateRequest, PlayerResponse
from app.services.player_service import PlayerService

router = APIRouter(prefix="/players", tags=["Players"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=PlayerResponse, status_code=201)
def create_player(
    payload: PlayerCreateRequest,
    client: CurrentClient,
    db: DbSession,
) -> PlayerResponse:
    player = PlayerService(db).create_player(
        client_id=client.id,
        external_id=payload.external_id,
        username=payload.username,
    )
    return PlayerResponse.model_validate(player, from_attributes=True)
