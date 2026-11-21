
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    event_uuid: Mapped[str] = mapped_column(
        CHAR(36),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    aggregate_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    aggregate_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    claim_token: Mapped[str | None] = mapped_column(
        CHAR(36),
        nullable=True,
    )

    available_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PUBLISHING', 'PUBLISHED', 'DEAD')",
            name="ck_outbox_events_status_valid",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_outbox_events_attempts_nonnegative",
        ),
        UniqueConstraint(
            "event_uuid",
            name="uq_outbox_events_event_uuid",
        ),
        Index(
            "ix_outbox_events_status_available",
            "status",
            "available_at",
        ),
        Index(
            "ix_outbox_events_status_locked_until",
            "status",
            "locked_until",
        ),
        Index(
            "ix_outbox_events_aggregate",
            "aggregate_type",
            "aggregate_id",
        ),
    )
