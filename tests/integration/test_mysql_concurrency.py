"""Optional InnoDB concurrency tests.

Set MYSQL_TEST_DATABASE_URL to a disposable MySQL database that has had
`alembic upgrade head` applied before running these tests.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_client_api_key
from app.models.client import Client
from app.models.idempotency_record import IdempotencyRecord
from app.models.outbox_event import OutboxEvent
from app.models.player import Player
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.models.wallet_ledger import WalletLedger
from app.services.errors import InsufficientBalanceError
from app.services.transaction_service import TransactionService


DATABASE_URL = os.getenv("MYSQL_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set MYSQL_TEST_DATABASE_URL to run the InnoDB concurrency test.",
)


def cleanup_test_client(factory, client_code: str) -> None:
    """Remove all database records belonging to one concurrency test client."""

    with factory() as db:
        client = db.query(Client).filter(Client.code == client_code).one_or_none()

        # Setup may have failed before the client was committed.
        if client is None:
            return

        client_id = client.id

        player_ids = select(Player.id).where(
            Player.client_id == client_id
        )

        wallet_ids = select(Wallet.id).where(
            Wallet.player_id.in_(player_ids)
        )

        transaction_ids = select(Transaction.id).where(
            Transaction.wallet_id.in_(wallet_ids)
        )

        # Outbox events reference transaction IDs through aggregate_id.
        db.query(OutboxEvent).filter(
            OutboxEvent.aggregate_id.in_(transaction_ids)
        ).delete(synchronize_session=False)

        # Ledger rows reference transactions and wallets.
        db.query(WalletLedger).filter(
            WalletLedger.wallet_id.in_(wallet_ids)
        ).delete(synchronize_session=False)

        # Delete child/refund transactions before their parent transactions.
        db.query(Transaction).filter(
            Transaction.wallet_id.in_(wallet_ids),
            Transaction.parent_transaction_id.is_not(None),
        ).delete(synchronize_session=False)

        db.query(Transaction).filter(
            Transaction.wallet_id.in_(wallet_ids)
        ).delete(synchronize_session=False)

        db.query(IdempotencyRecord).filter(
            IdempotencyRecord.client_id == client_id
        ).delete(synchronize_session=False)

        db.query(Wallet).filter(
            Wallet.player_id.in_(player_ids)
        ).delete(synchronize_session=False)

        db.query(Player).filter(
            Player.client_id == client_id
        ).delete(synchronize_session=False)

        db.query(Client).filter(
            Client.id == client_id
        ).delete(synchronize_session=False)

        db.commit()


def create_test_database(pool_size: int = 20):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=pool_size,
    )

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
        autoflush=False,
    )

    return engine, factory


def test_concurrent_debits_never_overdraw_wallet():
    engine, factory = create_test_database(pool_size=20)

    suffix = uuid4().hex[:12]
    client_code = f"CONCURRENCY_{suffix}"

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Setup is now protected by the outer try/finally.
        with factory() as db:
            client = Client(
                code=client_code,
                name="Concurrency Test",
                api_key_hash=hash_client_api_key(uuid4().hex),
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(client)
            db.flush()

            player = Player(
                client_id=client.id,
                external_id=f"player-{suffix}",
                username=None,
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(player)
            db.flush()

            wallet = Wallet(
                player_id=player.id,
                currency="INR",
                balance=Decimal("1000.0000"),
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(wallet)
            db.commit()

            client_id = client.id
            external_player_id = player.external_id
            wallet_id = wallet.id

        def debit(index: int) -> str:
            with factory() as db:
                try:
                    TransactionService(db).debit(
                        client_id=client_id,
                        idempotency_key=f"concurrency-{suffix}-{index}",
                        external_player_id=external_player_id,
                        amount=Decimal("100.0000"),
                        currency="INR",
                    )
                    return "SUCCESS"
                except InsufficientBalanceError:
                    return "INSUFFICIENT"

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(debit, range(20)))

        assert results.count("SUCCESS") == 10
        assert results.count("INSUFFICIENT") == 10

        with factory() as db:
            final_wallet = db.get(Wallet, wallet_id)
            assert final_wallet.balance == Decimal("0.0000")

            assert len(
                db.scalars(
                    select(Transaction).where(
                        Transaction.wallet_id == wallet_id
                    )
                ).all()
            ) == 10

            assert len(
                db.scalars(
                    select(WalletLedger).where(
                        WalletLedger.wallet_id == wallet_id
                    )
                ).all()
            ) == 10

            assert len(
                db.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.aggregate_id.in_(
                            select(Transaction.id).where(
                                Transaction.wallet_id == wallet_id
                            )
                        )
                    )
                ).all()
            ) == 10

            assert len(
                db.scalars(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.client_id == client_id
                    )
                ).all()
            ) == 20

    finally:
        try:
            cleanup_test_client(factory, client_code)
        finally:
            engine.dispose()


def test_concurrent_partial_refunds_cannot_exceed_original_amount():
    from app.services.errors import BusinessRuleError

    engine, factory = create_test_database(pool_size=12)

    suffix = uuid4().hex[:12]
    client_code = f"REFUND_CONCURRENCY_{suffix}"

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Setup is now protected by the outer try/finally.
        with factory() as db:
            client = Client(
                code=client_code,
                name="Refund Concurrency Test",
                api_key_hash=hash_client_api_key(uuid4().hex),
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(client)
            db.flush()

            player = Player(
                client_id=client.id,
                external_id=f"refund-player-{suffix}",
                username=None,
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(player)
            db.flush()

            wallet = Wallet(
                player_id=player.id,
                currency="INR",
                balance=Decimal("1000.0000"),
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(wallet)
            db.commit()

            client_id = client.id
            external_player_id = player.external_id
            wallet_id = wallet.id

        # The original debit is also inside the protected try block.
        with factory() as db:
            debit = TransactionService(db).debit(
                client_id=client_id,
                idempotency_key=f"refund-original-{suffix}",
                external_player_id=external_player_id,
                amount=Decimal("100.0000"),
                currency="INR",
            )

        original_uuid = debit["transaction_uuid"]

        def refund(index: int) -> str:
            with factory() as db:
                try:
                    TransactionService(db).refund(
                        client_id=client_id,
                        idempotency_key=f"refund-race-{suffix}-{index}",
                        external_player_id=external_player_id,
                        original_transaction_uuid=original_uuid,
                        amount=Decimal("20.0000"),
                        currency="INR",
                    )
                    return "SUCCESS"
                except BusinessRuleError:
                    return "EXCEEDS_REMAINING"

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(refund, range(10)))

        assert results.count("SUCCESS") == 5
        assert results.count("EXCEEDS_REMAINING") == 5

        with factory() as db:
            final_wallet = db.get(Wallet, wallet_id)
            assert final_wallet.balance == Decimal("1000.0000")

            original_id = db.scalar(
                select(Transaction.id).where(
                    Transaction.transaction_uuid == original_uuid
                )
            )

            children = db.scalars(
                select(Transaction).where(
                    Transaction.parent_transaction_id == original_id
                )
            ).all()

            assert len(children) == 5

            assert sum(
                (Decimal(row.amount) for row in children),
                Decimal("0"),
            ) == Decimal("100.0000")

    finally:
        try:
            cleanup_test_client(factory, client_code)
        finally:
            engine.dispose()
