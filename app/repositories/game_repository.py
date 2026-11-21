from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game


class GameRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_provider_and_external_id(
        self, provider_id: int, external_game_id: str
    ) -> Game | None:
        statement = select(Game).where(
            Game.provider_id == provider_id,
            Game.external_id == external_game_id,
        )
        return self.db.scalar(statement)
