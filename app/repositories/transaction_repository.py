from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        statement = select(Transaction).where(
            Transaction.id == transaction_id
        )
        return self.db.scalar(statement)

    def get_by_id_for_update(
        self,
        transaction_id: int,
    ) -> Transaction | None:
        statement = (
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_uuid(
        self,
        transaction_uuid: UUID | str,
    ) -> Transaction | None:
        statement = select(Transaction).where(
            Transaction.transaction_uuid == str(transaction_uuid)
        )
        return self.db.scalar(statement)

    def get_by_uuid_for_update(
        self,
        transaction_uuid: UUID | str,
    ) -> Transaction | None:
        statement = (
            select(Transaction)
            .where(
                Transaction.transaction_uuid == str(transaction_uuid)
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_wallet(
        self,
        wallet_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Transaction], int]:
        filters = Transaction.wallet_id == wallet_id

        items_statement = (
            select(Transaction)
            .where(filters)
            .order_by(
                Transaction.created_at.desc(),
                Transaction.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        count_statement = (
            select(func.count())
            .select_from(Transaction)
            .where(filters)
        )

        items = list(self.db.scalars(items_statement).all())
        total = self.db.scalar(count_statement) or 0

        return items, total
