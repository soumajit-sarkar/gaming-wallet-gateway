
"""add outbox claim ownership and dead status

Revision ID: d4e8b1c6a902
Revises: c81d6e4a2f90
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "d4e8b1c6a902"
down_revision: Union[str, Sequence[str], None] = "c81d6e4a2f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column(
            "claim_token",
            mysql.CHAR(length=36),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "ck_outbox_events_status_valid",
        "outbox_events",
        type_="check",
    )

    op.create_check_constraint(
        "ck_outbox_events_status_valid",
        "outbox_events",
        "status IN ('PENDING', 'PUBLISHING', 'PUBLISHED', 'DEAD')",
    )

    op.create_index(
        "ix_outbox_events_status_locked_until",
        "outbox_events",
        ["status", "locked_until"],
        unique=False,
    )


def downgrade() -> None:
    # Restore DEAD events to PENDING so the old constraint remains valid.
    op.execute(
        """
        UPDATE outbox_events
        SET status = 'PENDING',
            claim_token = NULL,
            locked_until = NULL
        WHERE status = 'DEAD'
        """
    )

    op.drop_index(
        "ix_outbox_events_status_locked_until",
        table_name="outbox_events",
    )

    op.drop_constraint(
        "ck_outbox_events_status_valid",
        "outbox_events",
        type_="check",
    )

    op.create_check_constraint(
        "ck_outbox_events_status_valid",
        "outbox_events",
        "status IN ('PENDING', 'PUBLISHING', 'PUBLISHED')",
    )

    op.drop_column("outbox_events", "claim_token")
