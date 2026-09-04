from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    wallet_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("wallets.id"),
        nullable=False,
    )

    transaction_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("transactions.id"),
        nullable=False,
    )

    entry_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
    )

    balance_before: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            name="uq_wallet_ledger_transaction_id",
        ),
        Index(
            "ix_wallet_ledger_wallet_id",
            "wallet_id",
        ),
        Index(
            "ix_wallet_ledger_wallet_created_at",
            "wallet_id",
            "created_at",
        ),
    )
