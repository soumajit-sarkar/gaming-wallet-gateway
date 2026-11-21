
"""enforce valid idempotency record statuses

Revision ID: 9f4c2a7b1d60
Revises: 7d2a6c4f9b31
Create Date: 2026-11-19
"""

from typing import Sequence, Union

from alembic import op


revision: str = "9f4c2a7b1d60"
down_revision: Union[str, Sequence[str], None] = "7d2a6c4f9b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_idempotency_records_status_valid",
        "idempotency_records",
        "status IN ('PROCESSING', 'COMPLETED', 'FAILED')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_idempotency_records_status_valid",
        "idempotency_records",
        type_="check",
    )
