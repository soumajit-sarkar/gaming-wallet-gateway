"""add transactional outbox and consumer inbox

Revision ID: 5a7d2c9e4b61
Revises: 3c1f7a9b2d40
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "5a7d2c9e4b61"
down_revision: Union[str, Sequence[str], None] = "3c1f7a9b2d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("event_uuid", mysql.CHAR(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("payload", mysql.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("locked_until", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("published_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHING', 'PUBLISHED')",
            name="ck_outbox_events_status_valid",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_uuid", name="uq_outbox_events_event_uuid"),
    )
    op.create_index(
        "ix_outbox_events_status_available",
        "outbox_events",
        ["status", "available_at"],
    )
    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )

    op.create_table(
        "processed_messages",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("message_uuid", mysql.CHAR(length=36), nullable=False),
        sa.Column("processed_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consumer_name",
            "message_uuid",
            name="uq_processed_messages_consumer_message",
        ),
    )


def downgrade() -> None:
    op.drop_table("processed_messages")
    op.drop_index("ix_outbox_events_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_available", table_name="outbox_events")
    op.drop_table("outbox_events")
