"""add wallet transaction integrity fields

Revision ID: 3c1f7a9b2d40
Revises: 5899dfda9364
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "3c1f7a9b2d40"
down_revision: Union[str, Sequence[str], None] = "5899dfda9364"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Support one wallet per player and currency rather than one wallet total.
    # Create the replacement index before dropping the old unique index.
    op.create_unique_constraint(
        "uq_wallets_player_currency",
        "wallets",
        ["player_id", "currency"],
    )
    op.drop_constraint(
        "uq_wallets_player_id",
        "wallets",
        type_="unique",
    )

    # Keep refund/rollback history linked to its original transaction.
    op.add_column(
        "transactions",
        sa.Column("parent_transaction_id", mysql.BIGINT(unsigned=True), nullable=True),
    )
    op.add_column(
        "transactions", sa.Column("reason", sa.String(length=255), nullable=True)
    )
    op.create_foreign_key(
        "fk_transactions_parent_transaction_id",
        "transactions",
        "transactions",
        ["parent_transaction_id"],
        ["id"],
    )
    op.create_index(
        "ix_transactions_parent_transaction_id",
        "transactions",
        ["parent_transaction_id"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_wallets_balance_nonnegative", "wallets", "balance >= 0"
    )
    op.create_check_constraint(
        "ck_transactions_amount_positive", "transactions", "amount > 0"
    )
    op.create_check_constraint(
        "ck_transactions_type_valid",
        "transactions",
        "type IN ('DEBIT', 'CREDIT', 'REFUND', 'ROLLBACK', 'ADJUSTMENT')",
    )
    op.create_check_constraint(
        "ck_transactions_status_valid",
        "transactions",
        "status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'REVERSED')",
    )
    op.create_check_constraint(
        "ck_wallet_ledger_amount_positive", "wallet_ledger", "amount > 0"
    )
    op.create_check_constraint(
        "ck_wallet_ledger_balance_equation",
        "wallet_ledger",
        "(entry_type = 'DEBIT' AND balance_after = balance_before - amount) "
        "OR (entry_type = 'CREDIT' AND balance_after = balance_before + amount)",
    )

    # Client API keys are stored as SHA-256 hashes, never as plaintext.
    op.add_column("clients", sa.Column("api_key_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_clients_api_key_hash", "clients", ["api_key_hash"])


def downgrade() -> None:
    op.drop_constraint("ck_wallet_ledger_balance_equation", "wallet_ledger", type_="check")
    op.drop_constraint("ck_wallet_ledger_amount_positive", "wallet_ledger", type_="check")
    op.drop_constraint("ck_transactions_status_valid", "transactions", type_="check")
    op.drop_constraint("ck_transactions_type_valid", "transactions", type_="check")
    op.drop_constraint("ck_transactions_amount_positive", "transactions", type_="check")
    op.drop_constraint("ck_wallets_balance_nonnegative", "wallets", type_="check")
    op.drop_constraint("uq_clients_api_key_hash", "clients", type_="unique")
    op.drop_column("clients", "api_key_hash")

    op.drop_index("ix_transactions_parent_transaction_id", table_name="transactions")
    op.drop_constraint(
        "fk_transactions_parent_transaction_id", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "reason")
    op.drop_column("transactions", "parent_transaction_id")

    op.drop_constraint("uq_wallets_player_currency", "wallets", type_="unique")
    op.create_unique_constraint("uq_wallets_player_id", "wallets", ["player_id"])
