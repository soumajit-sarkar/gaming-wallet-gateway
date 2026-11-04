from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wallet_ledger import WalletLedger


class WalletLedgerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, entry: WalletLedger) -> WalletLedger:
        self.db.add(entry)
        self.db.flush()
        return entry

    def get_by_transaction_id(
        self,
        transaction_id: int,
    ) -> WalletLedger | None:
        statement = select(WalletLedger).where(
            WalletLedger.transaction_id == transaction_id
        )
        return self.db.scalar(statement)

    def get_by_wallet(
        self,
        wallet_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[WalletLedger], int]:
        items_statement = (
            select(WalletLedger)
            .where(WalletLedger.wallet_id == wallet_id)
            .order_by(
                WalletLedger.created_at.desc(),
                WalletLedger.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        count_statement = (
            select(func.count())
            .select_from(WalletLedger)
            .where(WalletLedger.wallet_id == wallet_id)
        )

        items = list(self.db.scalars(items_statement).all())
        total = self.db.scalar(count_statement) or 0

        return items, total
