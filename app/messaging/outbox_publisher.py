
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import sessionmaker

from app.repositories.outbox_repository import OutboxRepository


def utcnow_naive() -> datetime:
    """Return UTC time as a naive datetime for MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OutboxPublisher:
    """Publishes committed outbox events with at-least-once delivery."""

    def __init__(
        self,
        session_factory: sessionmaker,
        publish_event: Callable[[dict[str, Any]], None],
        *,
        batch_size: int = 50,
        lease_seconds: int = 60,
        max_backoff_seconds: int = 300,
        max_attempts: int = 8,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")

        if lease_seconds < 1:
            raise ValueError("lease_seconds must be greater than zero")

        if max_backoff_seconds < 1:
            raise ValueError("max_backoff_seconds must be greater than zero")

        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")

        self.session_factory = session_factory
        self.publish_event = publish_event
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.max_attempts = max_attempts

    def run_once(self) -> int:
        # Phase 1: Claim events and commit ownership before
        # making any network calls.
        claim_session = self.session_factory()

        try:
            events = OutboxRepository(claim_session).claim_batch(
                now=utcnow_naive(),
                limit=self.batch_size,
                lease_seconds=self.lease_seconds,
                max_attempts=self.max_attempts,
            )
            claim_session.commit()

        except Exception:
            claim_session.rollback()
            raise

        finally:
            claim_session.close()

        # Phase 2: Publish each claimed event independently.
        for event in events:
            try:
                self.publish_event(event)

            except Exception as exc:
                retry_session = self.session_factory()

                try:
                    # First failed attempt gets a 1-second delay.
                    # Subsequent failures use exponential backoff.
                    exponent = min(event["attempts"] - 1, 8)
                    backoff = min(
                        self.max_backoff_seconds,
                        2 ** exponent,
                    )

                    updated = OutboxRepository(
                        retry_session
                    ).schedule_retry(
                        event_uuid=event["event_uuid"],
                        claim_token=event["claim_token"],
                        now=utcnow_naive(),
                        error=f"{type(exc).__name__}: {exc}",
                        backoff_seconds=backoff,
                        max_attempts=self.max_attempts,
                    )

                    retry_session.commit()

                except Exception:
                    retry_session.rollback()
                    raise

                finally:
                    retry_session.close()

            else:
                success_session = self.session_factory()

                try:
                    OutboxRepository(
                        success_session
                    ).mark_published(
                        event_uuid=event["event_uuid"],
                        claim_token=event["claim_token"],
                        now=utcnow_naive(),
                    )

                    success_session.commit()

                except Exception:
                    success_session.rollback()
                    raise

                finally:
                    success_session.close()

        return len(events)
