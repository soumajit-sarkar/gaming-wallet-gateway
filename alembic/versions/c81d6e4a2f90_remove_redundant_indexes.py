
"""remove redundant single-column indexes

Revision ID: c81d6e4a2f90
Revises: 9f4c2a7b1d60
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c81d6e4a2f90"
down_revision: Union[str, Sequence[str], None] = "9f4c2a7b1d60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_transactions_wallet_id",
        table_name="transactions",
    )
    op.drop_index(
        "ix_idempotency_records_client_id",
        table_name="idempotency_records",
    )


def downgrade() -> None:
    op.create_index(
        "ix_transactions_wallet_id",
        "transactions",
        ["wallet_id"],
        unique=False,
    )
    op.create_index(
        "ix_idempotency_records_client_id",
        "idempotency_records",
        ["client_id"],
        unique=False,
    )
