from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.repositories.player_repository import PlayerRepository
from app.repositories.wallet_repository import WalletRepository
from app.services.errors import BusinessRuleError, ResourceNotFoundError


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WalletService:
    """Wallet operations. `client_id` must be supplied by trusted auth."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.players = PlayerRepository(db)
        self.wallets = WalletRepository(db)

    def create_wallet(
        self, *, client_id: int, external_player_id: str, currency: str
    ) -> Wallet:
        currency = currency.strip().upper()
        player_id: int | None = None
        try:
            player = self.players.get_by_client_and_external_id_for_update(
                client_id, external_player_id
            )
            if player is None:
                raise ResourceNotFoundError("Player was not found for this client.")
            if player.status != "ACTIVE":
                raise BusinessRuleError("Player is not active.")
            player_id = player.id
            existing = self.wallets.get_by_player_id_and_currency(player_id, currency)
            if existing is not None:
                raise BusinessRuleError("A wallet already exists for this player and currency.")
            now = _utcnow_naive()
            wallet = Wallet(
                player_id=player_id,
                currency=currency,
                balance=Decimal("0.0000"),
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            self.db.add(wallet)
            self.db.flush()
            self.db.commit()
            return wallet
        except IntegrityError as exc:
            self.db.rollback()
            existing = (
                self.wallets.get_by_player_id_and_currency(player_id, currency)
                if player_id is not None
                else None
            )
            if existing is not None:
                raise BusinessRuleError(
                    "A wallet already exists for this player and currency."
                ) from exc
            raise
        except Exception:
            self.db.rollback()
            raise

    def get_balance(
        self, *, client_id: int, external_player_id: str, currency: str
    ) -> Wallet:
        player = self.players.get_by_client_and_external_id(
            client_id, external_player_id
        )
        if player is None:
            raise ResourceNotFoundError("Player was not found for this client.")
        wallet = self.wallets.get_by_player_id_and_currency(player.id, currency)
        if wallet is None:
            raise ResourceNotFoundError("Wallet was not found.")
        return wallet
