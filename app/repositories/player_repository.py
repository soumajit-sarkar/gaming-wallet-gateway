from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.player import Player


class PlayerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, player_id: int) -> Player | None:
        statement = select(Player).where(
            Player.id == player_id
        )
        return self.db.scalar(statement)

    def get_by_client_and_external_id(
        self,
        client_id: int,
        external_player_id: str,
    ) -> Player | None:
        statement = select(Player).where(
            Player.client_id == client_id,
            Player.external_id == external_player_id,
        )
        return self.db.scalar(statement)

    def get_by_client_and_external_id_for_update(
        self,
        client_id: int,
        external_player_id: str,
    ) -> Player | None:
        statement = (
            select(Player)
            .where(
                Player.client_id == client_id,
                Player.external_id == external_player_id,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)
