from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.wallet import Wallet


class WalletRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(
        self,
        wallet_id: int,
    ) -> Wallet | None:
        statement = select(Wallet).where(
            Wallet.id == wallet_id
        )

        return self.db.scalar(statement)

    def get_by_id_for_update(
        self,
        wallet_id: int,
    ) -> Wallet | None:
        statement = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        return self.db.scalar(statement)

    def get_by_player_id_and_currency(
        self,
        player_id: int,
        currency: str,
    ) -> Wallet | None:
        normalized_currency = currency.strip().upper()

        statement = select(Wallet).where(
            Wallet.player_id == player_id,
            Wallet.currency == normalized_currency,
        )

        return self.db.scalar(statement)

    def get_by_player_id_and_currency_for_update(
        self,
        player_id: int,
        currency: str,
    ) -> Wallet | None:
        normalized_currency = currency.strip().upper()

        statement = (
            select(Wallet)
            .where(
                Wallet.player_id == player_id,
                Wallet.currency == normalized_currency,
            )
            .with_for_update()
        )

        return self.db.scalar(statement)
