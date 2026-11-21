from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    client_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("clients.id"), nullable=False
    )
    wallet_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("wallets.id"), nullable=False
    )
    game_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("games.id"), nullable=True
    )
    parent_transaction_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("transactions.id"), nullable=True
    )
    transaction_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "type IN ('DEBIT', 'CREDIT', 'REFUND', 'ROLLBACK', 'ADJUSTMENT')",
            name="ck_transactions_type_valid",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'REVERSED')",
            name="ck_transactions_status_valid",
        ),
        UniqueConstraint("transaction_uuid", name="uq_transactions_transaction_uuid"),
        Index("ix_transactions_client_id", "client_id"),
        Index("ix_transactions_game_id", "game_id"),
        Index("ix_transactions_provider_reference", "provider_reference"),
        Index("ix_transactions_wallet_created_at", "wallet_id", "created_at"),
        Index("ix_transactions_parent_transaction_id", "parent_transaction_id"),
    )
