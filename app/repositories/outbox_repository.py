
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, case, or_, select, update
from sqlalchemy.orm import Session

from app.models.outbox_event import OutboxEvent


class OutboxRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def claim_batch(
        self,
        *,
        now: datetime,
        limit: int = 50,
        lease_seconds: int = 60,
        max_attempts: int = 8,
    ) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be greater than zero")
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")

        statement = (
            select(OutboxEvent)
            .where(
                or_(
                    and_(
                        OutboxEvent.status == "PENDING",
                        OutboxEvent.available_at <= now,
                    ),
                    and_(
                        OutboxEvent.status == "PUBLISHING",
                        OutboxEvent.locked_until <= now,
                    ),
                )
            )
            .order_by(OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        rows = list(self.db.scalars(statement).all())
        claimed: list[dict] = []

        for row in rows:
            if row.attempts >= max_attempts:
                row.status = "DEAD"
                row.claim_token = None
                row.locked_until = None
                row.updated_at = now
                row.last_error = (
                    row.last_error
                    or "Maximum publish attempts exhausted."
                )
                continue

            claim_token = str(uuid4())

            row.status = "PUBLISHING"
            row.attempts += 1
            row.claim_token = claim_token
            row.locked_until = now + timedelta(seconds=lease_seconds)
            row.updated_at = now

            claimed.append(
                {
                    "event_uuid": row.event_uuid,
                    "event_type": row.event_type,
                    "payload": row.payload,
                    "attempts": row.attempts,
                    "claim_token": claim_token,
                }
            )

        self.db.flush()
        return claimed

    def mark_published(
        self,
        *,
        event_uuid: str,
        claim_token: str,
        now: datetime,
    ) -> bool:
        statement = (
            update(OutboxEvent)
            .where(
                OutboxEvent.event_uuid == event_uuid,
                OutboxEvent.status == "PUBLISHING",
                OutboxEvent.claim_token == claim_token,
            )
            .values(
                status="PUBLISHED",
                published_at=now,
                locked_until=None,
                claim_token=None,
                last_error=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )

        result = self.db.execute(statement)
        self.db.flush()
        return result.rowcount == 1

    def schedule_retry(
        self,
        *,
        event_uuid: str,
        claim_token: str,
        now: datetime,
        error: str,
        backoff_seconds: int,
        max_attempts: int = 8,
    ) -> bool:
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")

        next_status = case(
            (
                OutboxEvent.attempts >= max_attempts,
                "DEAD",
            ),
            else_="PENDING",
        )

        statement = (
            update(OutboxEvent)
            .where(
                OutboxEvent.event_uuid == event_uuid,
                OutboxEvent.status == "PUBLISHING",
                OutboxEvent.claim_token == claim_token,
            )
            .values(
                status=next_status,
                available_at=now + timedelta(seconds=backoff_seconds),
                locked_until=None,
                claim_token=None,
                last_error=error[:4000],
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )

        result = self.db.execute(statement)
        self.db.flush()
        return result.rowcount == 1
