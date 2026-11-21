import os
from datetime import datetime, timezone
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Client, Player, Wallet  # noqa: F401
from app.core.security import hash_client_api_key


@compiles(BIGINT, "sqlite")
def compile_bigint_sqlite(_type, _compiler, **_kw):
    # SQLite requires INTEGER PRIMARY KEY for rowid-backed autoincrement.
    return "INTEGER"


@compiles(DATETIME, "sqlite")
def compile_datetime_sqlite(_type, _compiler, **_kw):
    return "DATETIME"


@compiles(JSON, "sqlite")
def compile_mysql_json_sqlite(_type, _compiler, **_kw):
    return "JSON"


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = factory()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    client = Client(
        code="TEST_CLIENT",
        name="Test Client",
        status="ACTIVE",
        api_key_hash=hash_client_api_key("test-client-secret"),
        created_at=now,
        updated_at=now,
    )
    session.add(client)
    session.flush()

    player = Player(
        client_id=client.id,
        external_id="player-001",
        username="test-player",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    session.add(player)
    session.flush()

    wallet = Wallet(
        player_id=player.id,
        currency="INR",
        balance=Decimal("1000.0000"),
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    session.add(wallet)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
