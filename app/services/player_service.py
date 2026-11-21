from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.player import Player
from app.repositories.player_repository import PlayerRepository


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PlayerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.players = PlayerRepository(db)

    def create_player(
        self, *, client_id: int, external_id: str, username: str | None = None
    ) -> Player:
        existing = self.players.get_by_client_and_external_id(client_id, external_id)
        if existing is not None:
            return existing

        now = _utcnow_naive()
        player = Player(
            client_id=client_id,
            external_id=external_id,
            username=username,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        try:
            self.db.add(player)
            self.db.commit()
            self.db.refresh(player)
            return player
        except IntegrityError:
            self.db.rollback()
            # Concurrent create requests for the same external player converge
            # on the row protected by uq_players_client_external_id.
            existing = self.players.get_by_client_and_external_id(
                client_id, external_id
            )
            if existing is None:
                raise
            return existing
        except Exception:
            self.db.rollback()
            raise
