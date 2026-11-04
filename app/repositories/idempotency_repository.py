from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.idempotency_record import IdempotencyRecord


class IdempotencyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        record: IdempotencyRecord,
    ) -> IdempotencyRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def get_by_client_and_key(
        self,
        client_id: int,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        statement = select(IdempotencyRecord).where(
            IdempotencyRecord.client_id == client_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        return self.db.scalar(statement)

    def get_by_client_and_key_for_update(
        self,
        client_id: int,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        statement = (
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.client_id == client_id,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def mark_completed(
        self,
        record: IdempotencyRecord,
        response_data: dict,
    ) -> IdempotencyRecord:
        record.status = "COMPLETED"
        record.response_data = response_data

        self.db.flush()
        return record

    def mark_failed(
        self,
        record: IdempotencyRecord,
        response_data: dict | None = None,
    ) -> IdempotencyRecord:
        record.status = "FAILED"
        record.response_data = response_data

        self.db.flush()
        return record
