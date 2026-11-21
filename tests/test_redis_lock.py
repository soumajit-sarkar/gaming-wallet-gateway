import pytest

from app.locks.redis_lock import RedisLock, RedisLockManager
from app.services.errors import ConcurrencyLockError


class FakeRedis:
    def __init__(self, acquire=True, release=1):
        self.acquire_result = acquire
        self.release_result = release
        self.set_calls = []
        self.eval_calls = []

    def set(self, *args, **kwargs):
        self.set_calls.append((args, kwargs))
        return self.acquire_result

    def eval(self, *args):
        self.eval_calls.append(args)
        return self.release_result


def test_redis_lock_uses_nx_and_expiring_ttl_and_releases_with_owner_check():
    client = FakeRedis()
    lock = RedisLock(client, "gwg:wallet-lock:test", ttl_ms=5000)
    with lock:
        assert lock.token is not None
    assert client.set_calls[0][1] == {"nx": True, "px": 5000}
    assert len(client.eval_calls) == 1
    assert lock.token is None


def test_redis_lock_fails_after_blocking_timeout():
    client = FakeRedis(acquire=None)
    lock = RedisLock(
        client,
        "gwg:wallet-lock:test",
        blocking_timeout=0,
        retry_interval=0,
    )
    with pytest.raises(ConcurrencyLockError, match="Wallet is busy"):
        with lock:
            pass


def test_wallet_lock_key_does_not_expose_external_player_id():
    manager = RedisLockManager(FakeRedis())
    lock = manager.wallet_lock(
        client_id=12,
        external_player_id="sensitive-player-reference",
        currency="inr",
    )
    assert "sensitive-player-reference" not in lock.key
    assert lock.key.startswith("gwg:wallet-lock:")
