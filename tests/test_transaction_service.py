
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.idempotency_record import IdempotencyRecord
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.services.errors import (
    IdempotencyConflictError,
    InsufficientBalanceError,
)
from app.services.transaction_service import TransactionService


CLIENT_ID = 1
PLAYER_ID = "player-001"


def test_debit_updates_balance_and_creates_ledger(db_session):
    result = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="debit-001",
        external_player_id=PLAYER_ID,
        amount=Decimal("125.5000"),
        currency="INR",
    )

    wallet = db_session.query(Wallet).one()
    assert wallet.balance == Decimal("874.5000")
    assert result["type"] == "DEBIT"
    assert result["balance_before"] == "1000.0000"
    assert result["balance_after"] == "874.5000"
    assert db_session.query(Transaction).count() == 1
    assert db_session.query(Transaction).one().status == "SUCCESS"


def test_same_idempotency_key_replays_original_result(db_session):
    service = TransactionService(db_session)
    first = service.debit(
        client_id=CLIENT_ID,
        idempotency_key="debit-replay",
        external_player_id=PLAYER_ID,
        amount=Decimal("25.0000"),
        currency="INR",
    )
    second = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="debit-replay",
        external_player_id=PLAYER_ID,
        amount=Decimal("25.0000"),
        currency="INR",
    )

    assert first == second
    assert db_session.query(Transaction).count() == 1
    assert db_session.query(Wallet).one().balance == Decimal("975.0000")


def test_reusing_idempotency_key_with_different_payload_conflicts(db_session):
    service = TransactionService(db_session)
    service.debit(
        client_id=CLIENT_ID,
        idempotency_key="same-key",
        external_player_id=PLAYER_ID,
        amount=Decimal("10.0000"),
        currency="INR",
    )

    with pytest.raises(IdempotencyConflictError):
        TransactionService(db_session).debit(
            client_id=CLIENT_ID,
            idempotency_key="same-key",
            external_player_id=PLAYER_ID,
            amount=Decimal("11.0000"),
            currency="INR",
        )

    assert db_session.query(Transaction).count() == 1


def test_insufficient_balance_is_recorded_and_does_not_change_wallet(db_session):
    with pytest.raises(InsufficientBalanceError):
        TransactionService(db_session).debit(
            client_id=CLIENT_ID,
            idempotency_key="too-large",
            external_player_id=PLAYER_ID,
            amount=Decimal("1001.0000"),
            currency="INR",
        )

    assert db_session.query(Wallet).one().balance == Decimal("1000.0000")
    assert db_session.query(Transaction).count() == 0

    with pytest.raises(InsufficientBalanceError):
        TransactionService(db_session).debit(
            client_id=CLIENT_ID,
            idempotency_key="too-large",
            external_player_id=PLAYER_ID,
            amount=Decimal("1001.0000"),
            currency="INR",
        )


def test_partial_refund_creates_child_transaction(db_session):
    service = TransactionService(db_session)
    debit = service.debit(
        client_id=CLIENT_ID,
        idempotency_key="original-debit",
        external_player_id=PLAYER_ID,
        amount=Decimal("200.0000"),
        currency="INR",
    )
    refund = TransactionService(db_session).refund(
        client_id=CLIENT_ID,
        idempotency_key="partial-refund",
        external_player_id=PLAYER_ID,
        original_transaction_uuid=debit["transaction_uuid"],
        amount=Decimal("75.0000"),
        currency="INR",
    )

    original = db_session.query(Transaction).filter_by(
        transaction_uuid=debit["transaction_uuid"]
    ).one()
    refund_row = db_session.query(Transaction).filter_by(
        transaction_uuid=refund["transaction_uuid"]
    ).one()
    assert refund_row.parent_transaction_id == original.id
    assert refund_row.type == "REFUND"
    assert db_session.query(Wallet).one().balance == Decimal("875.0000")


def test_rollback_reverses_original_debit_once(db_session):
    debit = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="debit-for-rollback",
        external_player_id=PLAYER_ID,
        amount=Decimal("80.0000"),
        currency="INR",
    )
    rollback = TransactionService(db_session).rollback(
        client_id=CLIENT_ID,
        idempotency_key="rollback-once",
        external_player_id=PLAYER_ID,
        original_transaction_uuid=debit["transaction_uuid"],
        currency="INR",
    )

    assert rollback["type"] == "ROLLBACK"
    assert db_session.query(Wallet).one().balance == Decimal("1000.0000")


def test_refunds_cannot_exceed_original_debit(db_session):
    service = TransactionService(db_session)
    debit = service.debit(
        client_id=CLIENT_ID,
        idempotency_key="debit-refund-cap",
        external_player_id=PLAYER_ID,
        amount=Decimal("100.0000"),
        currency="INR",
    )
    service.refund(
        client_id=CLIENT_ID,
        idempotency_key="refund-60",
        external_player_id=PLAYER_ID,
        original_transaction_uuid=debit["transaction_uuid"],
        amount=Decimal("60.0000"),
        currency="INR",
    )

    from app.services.errors import BusinessRuleError

    with pytest.raises(BusinessRuleError):
        TransactionService(db_session).refund(
            client_id=CLIENT_ID,
            idempotency_key="refund-50",
            external_player_id=PLAYER_ID,
            original_transaction_uuid=debit["transaction_uuid"],
            amount=Decimal("50.0000"),
            currency="INR",
        )

    assert db_session.query(Wallet).one().balance == Decimal("960.0000")


def test_rollback_of_credit_debits_wallet(db_session):
    credit = TransactionService(db_session).credit(
        client_id=CLIENT_ID,
        idempotency_key="credit-to-rollback",
        external_player_id=PLAYER_ID,
        amount=Decimal("50.0000"),
        currency="INR",
    )
    result = TransactionService(db_session).rollback(
        client_id=CLIENT_ID,
        idempotency_key="rollback-credit",
        external_player_id=PLAYER_ID,
        original_transaction_uuid=credit["transaction_uuid"],
        currency="INR",
    )

    assert result["balance_after"] == "1000.0000"
    assert db_session.query(Wallet).one().balance == Decimal("1000.0000")


def test_rollback_is_rejected_after_partial_refund(db_session):
    from app.services.errors import BusinessRuleError

    debit = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="debit-partial-before-rollback",
        external_player_id=PLAYER_ID,
        amount=Decimal("100.0000"),
        currency="INR",
    )
    TransactionService(db_session).refund(
        client_id=CLIENT_ID,
        idempotency_key="refund-partial-before-rollback",
        external_player_id=PLAYER_ID,
        original_transaction_uuid=debit["transaction_uuid"],
        amount=Decimal("20.0000"),
        currency="INR",
    )

    with pytest.raises(BusinessRuleError):
        TransactionService(db_session).rollback(
            client_id=CLIENT_ID,
            idempotency_key="rollback-after-partial-refund",
            external_player_id=PLAYER_ID,
            original_transaction_uuid=debit["transaction_uuid"],
            currency="INR",
        )

    assert db_session.query(Wallet).one().balance == Decimal("920.0000")


def test_successful_transaction_writes_outbox_event_atomically(db_session):
    from app.models.outbox_event import OutboxEvent

    result = TransactionService(db_session).credit(
        client_id=CLIENT_ID,
        idempotency_key="credit-outbox-event",
        external_player_id=PLAYER_ID,
        amount=Decimal("12.5000"),
        currency="INR",
    )

    event = db_session.query(OutboxEvent).one()
    assert event.status == "PENDING"
    assert event.event_type == "wallet.transaction.completed"
    assert event.payload["transaction_uuid"] == result["transaction_uuid"]
    assert event.payload["balance_after"] == "1012.5000"


def test_outbox_publisher_marks_confirmed_event_as_published(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.messaging.outbox_publisher import OutboxPublisher
    from app.models.outbox_event import OutboxEvent

    TransactionService(db_session).credit(
        client_id=CLIENT_ID,
        idempotency_key="credit-outbox-publish",
        external_player_id=PLAYER_ID,
        amount=Decimal("5.0000"),
        currency="INR",
    )
    published = []
    factory = sessionmaker(bind=db_session.bind, expire_on_commit=False)
    publisher = OutboxPublisher(factory, published.append)

    assert publisher.run_once() == 1
    assert len(published) == 1
    event = db_session.query(OutboxEvent).one()
    assert event.status == "PUBLISHED"
    assert event.published_at is not None


def test_outbox_publisher_schedules_retry_after_publish_failure(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.messaging.outbox_publisher import OutboxPublisher
    from app.models.outbox_event import OutboxEvent

    TransactionService(db_session).credit(
        client_id=CLIENT_ID,
        idempotency_key="credit-outbox-retry",
        external_player_id=PLAYER_ID,
        amount=Decimal("5.0000"),
        currency="INR",
    )

    def fail_publish(_event):
        raise RuntimeError("simulated broker outage")

    factory = sessionmaker(bind=db_session.bind, expire_on_commit=False)
    publisher = OutboxPublisher(factory, fail_publish)
    assert publisher.run_once() == 1

    event = db_session.query(OutboxEvent).one()
    assert event.status == "PENDING"
    assert event.attempts == 1
    assert "simulated broker outage" in event.last_error


def _create_outbox_event(db_session, idempotency_key: str) -> str:
    from app.models.outbox_event import OutboxEvent

    TransactionService(db_session).credit(
        client_id=CLIENT_ID,
        idempotency_key=idempotency_key,
        external_player_id=PLAYER_ID,
        amount=Decimal("5.0000"),
        currency="INR",
    )

    event = db_session.query(OutboxEvent).one()
    return event.event_uuid


def test_outbox_rejects_stale_claim_when_marking_published(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.models.outbox_event import OutboxEvent
    from app.repositories.outbox_repository import OutboxRepository

    event_uuid = _create_outbox_event(
        db_session,
        "outbox-stale-publish",
    )

    factory = sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Worker A claims the event.
    worker_a = factory()
    first_claim = OutboxRepository(worker_a).claim_batch(
        now=now,
        limit=1,
        lease_seconds=1,
    )
    worker_a.commit()
    worker_a.close()

    assert len(first_claim) == 1

    # Worker B reclaims the event after Worker A's lease expires.
    worker_b = factory()
    second_claim = OutboxRepository(worker_b).claim_batch(
        now=now + timedelta(seconds=2),
        limit=1,
        lease_seconds=60,
    )
    worker_b.commit()
    worker_b.close()

    assert len(second_claim) == 1
    assert first_claim[0]["claim_token"] != second_claim[0]["claim_token"]

    # Worker A must not mark Worker B's claim as published.
    stale_session = factory()

    updated = OutboxRepository(stale_session).mark_published(
        event_uuid=event_uuid,
        claim_token=first_claim[0]["claim_token"],
        now=now + timedelta(seconds=3),
    )
    stale_session.commit()
    stale_session.close()

    assert updated is False

    db_session.expire_all()
    event = db_session.query(OutboxEvent).one()

    assert event.status == "PUBLISHING"
    assert event.claim_token == second_claim[0]["claim_token"]
    assert event.published_at is None


def test_outbox_rejects_stale_claim_when_scheduling_retry(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.models.outbox_event import OutboxEvent
    from app.repositories.outbox_repository import OutboxRepository

    event_uuid = _create_outbox_event(
        db_session,
        "outbox-stale-retry",
    )

    factory = sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Worker A claims the event.
    worker_a = factory()
    first_claim = OutboxRepository(worker_a).claim_batch(
        now=now,
        limit=1,
        lease_seconds=1,
    )
    worker_a.commit()
    worker_a.close()

    # Worker B reclaims it after the lease expires.
    worker_b = factory()
    second_claim = OutboxRepository(worker_b).claim_batch(
        now=now + timedelta(seconds=2),
        limit=1,
        lease_seconds=60,
    )
    worker_b.commit()
    worker_b.close()

    assert len(first_claim) == 1
    assert len(second_claim) == 1

    # Worker A must not overwrite Worker B's ownership or schedule a retry.
    stale_session = factory()

    updated = OutboxRepository(stale_session).schedule_retry(
        event_uuid=event_uuid,
        claim_token=first_claim[0]["claim_token"],
        now=now + timedelta(seconds=3),
        error="Stale worker failure",
        backoff_seconds=10,
    )
    stale_session.commit()
    stale_session.close()

    assert updated is False

    db_session.expire_all()
    event = db_session.query(OutboxEvent).one()

    assert event.status == "PUBLISHING"
    assert event.claim_token == second_claim[0]["claim_token"]
    assert event.last_error is None


def test_outbox_marks_event_dead_after_maximum_attempts(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.models.outbox_event import OutboxEvent
    from app.repositories.outbox_repository import OutboxRepository

    event_uuid = _create_outbox_event(
        db_session,
        "outbox-max-attempts",
    )

    factory = sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = factory()

    claimed = OutboxRepository(session).claim_batch(
        now=now,
        limit=1,
        lease_seconds=60,
        max_attempts=1,
    )
    session.commit()

    assert len(claimed) == 1
    assert claimed[0]["attempts"] == 1

    updated = OutboxRepository(session).schedule_retry(
        event_uuid=event_uuid,
        claim_token=claimed[0]["claim_token"],
        now=now,
        error="Maximum attempts reached",
        backoff_seconds=1,
        max_attempts=1,
    )
    session.commit()
    session.close()

    assert updated is True

    db_session.expire_all()
    event = db_session.query(OutboxEvent).one()

    assert event.status == "DEAD"
    assert event.attempts == 1
    assert event.claim_token is None
    assert event.locked_until is None
    assert event.last_error == "Maximum attempts reached"


def test_outbox_reclaims_event_after_expired_lease(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.models.outbox_event import OutboxEvent
    from app.repositories.outbox_repository import OutboxRepository

    _create_outbox_event(
        db_session,
        "outbox-lease-reclaim",
    )

    factory = sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # First claim.
    first_session = factory()

    first_claim = OutboxRepository(first_session).claim_batch(
        now=now,
        limit=1,
        lease_seconds=1,
    )
    first_session.commit()
    first_session.close()

    assert len(first_claim) == 1
    assert first_claim[0]["attempts"] == 1

    # Second claim after the first lease expires.
    second_session = factory()

    second_claim = OutboxRepository(second_session).claim_batch(
        now=now + timedelta(seconds=2),
        limit=1,
        lease_seconds=60,
    )
    second_session.commit()
    second_session.close()

    assert len(second_claim) == 1
    assert second_claim[0]["attempts"] == 2

    assert first_claim[0]["claim_token"] != second_claim[0]["claim_token"]

    db_session.expire_all()
    event = db_session.query(OutboxEvent).one()

    assert event.status == "PUBLISHING"
    assert event.attempts == 2
    assert event.claim_token == second_claim[0]["claim_token"]


def test_transaction_links_to_active_provider_game(db_session):
    from app.models.game import Game
    from app.models.provider import Provider

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    provider = Provider(
        code="DEMO",
        name="Demo Provider",
        base_url="https://provider.example.test",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    db_session.add(provider)
    db_session.flush()
    game = Game(
        provider_id=provider.id,
        external_id="slot-001",
        name="Demo Slot",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    db_session.add(game)
    db_session.commit()

    result = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="provider-game-debit",
        external_player_id=PLAYER_ID,
        amount=Decimal("5.0000"),
        currency="INR",
        provider_code="DEMO",
        game_external_id="slot-001",
    )
    transaction = db_session.query(Transaction).filter_by(
        transaction_uuid=result["transaction_uuid"]
    ).one()
    assert transaction.game_id == game.id


def test_adjustment_creates_auditable_reason_and_correct_ledger_direction(db_session):
    from app.models.wallet_ledger import WalletLedger

    result = TransactionService(db_session).adjust(
        client_id=CLIENT_ID,
        idempotency_key="admin-adjustment-debit",
        external_player_id=PLAYER_ID,
        amount=Decimal("15.0000"),
        currency="INR",
        direction="DEBIT",
        reason="Manual correction",
    )

    transaction = db_session.query(Transaction).filter_by(
        transaction_uuid=result["transaction_uuid"]
    ).one()
    ledger = db_session.query(WalletLedger).filter_by(
        transaction_id=transaction.id
    ).one()
    assert transaction.type == "ADJUSTMENT"
    assert transaction.reason == "Manual correction"
    assert ledger.entry_type == "DEBIT"
    assert ledger.balance_after == Decimal("985.0000")


def test_service_rejects_float_money_values(db_session):
    from app.services.errors import InvalidTransactionError

    with pytest.raises(InvalidTransactionError):
        TransactionService(db_session).credit(
            client_id=CLIENT_ID,
            idempotency_key="float-amount",
            external_player_id=PLAYER_ID,
            amount=10.25,  # type: ignore[arg-type]
            currency="INR",
        )


def test_idempotency_hash_normalizes_decimal_scale_and_currency(db_session):
    first = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="canonical-money-request",
        external_player_id=PLAYER_ID,
        amount=Decimal("1.0"),
        currency="inr",
    )
    second = TransactionService(db_session).debit(
        client_id=CLIENT_ID,
        idempotency_key="canonical-money-request",
        external_player_id=PLAYER_ID,
        amount=Decimal("1.0000"),
        currency="INR",
    )
    assert first == second
    assert first["amount"] == "1.0000"
    assert db_session.query(Transaction).count() == 1


def test_idempotent_replay_does_not_require_redis_lock_service(db_session):
    class UnavailableLockManager:
        def wallet_lock(self, **_kwargs):
            from app.services.errors import ConcurrencyLockError

            raise ConcurrencyLockError("Redis unavailable")

    original = TransactionService(db_session).credit(
        client_id=CLIENT_ID,
        idempotency_key="replay-without-redis",
        external_player_id=PLAYER_ID,
        amount=Decimal("3.0000"),
        currency="INR",
    )
    replay = TransactionService(
        db_session, lock_manager=UnavailableLockManager()
    ).credit(
        client_id=CLIENT_ID,
        idempotency_key="replay-without-redis",
        external_player_id=PLAYER_ID,
        amount=Decimal("3.0000"),
        currency="INR",
    )
    assert replay == original


def test_idempotency_record_rejects_invalid_status(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    record = IdempotencyRecord(
        client_id=CLIENT_ID,
        idempotency_key="invalid-status-test",
        request_hash="a" * 64,
        response_data=None,
        status="INVALID",
        created_at=now,
        updated_at=now,
    )

    db_session.add(record)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()

    assert (
        db_session.query(IdempotencyRecord)
        .filter_by(idempotency_key="invalid-status-test")
        .count()
        == 0
    )
