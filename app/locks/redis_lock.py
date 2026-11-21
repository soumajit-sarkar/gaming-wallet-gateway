import hashlib
import secrets
import time
from types import TracebackType
from typing import Any

from app.services.errors import ConcurrencyLockError

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class RedisLock:
    def __init__(
        self,
        client: Any,
        key: str,
        *,
        ttl_ms: int = 30_000,
        blocking_timeout: float = 2.0,
        retry_interval: float = 0.05,
    ) -> None:
        if ttl_ms < 1_000:
            raise ValueError("Redis lock TTL must be at least 1000 milliseconds.")
        self.client = client
        self.key = key
        self.ttl_ms = ttl_ms
        self.blocking_timeout = blocking_timeout
        self.retry_interval = retry_interval
        self.token: str | None = None

    def acquire(self) -> bool:
        token = secrets.token_urlsafe(24)
        deadline = time.monotonic() + self.blocking_timeout
        while True:
            try:
                acquired = self.client.set(
                    self.key,
                    token,
                    nx=True,
                    px=self.ttl_ms,
                )
            except Exception as exc:
                raise ConcurrencyLockError(
                    "Redis wallet lock service is unavailable."
                ) from exc
            if acquired:
                self.token = token
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(self.retry_interval)

    def release(self) -> None:
        if self.token is None:
            return
        token = self.token
        self.token = None
        try:
            self.client.eval(_RELEASE_SCRIPT, 1, self.key, token)
        except Exception as exc:
            raise ConcurrencyLockError(
                "Redis wallet lock could not be released; its TTL will expire it."
            ) from exc

    def __enter__(self) -> "RedisLock":
        if not self.acquire():
            raise ConcurrencyLockError(
                "Wallet is busy. Retry the operation using the same Idempotency-Key."
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.release()
        except ConcurrencyLockError:
            if exc_type is None:
                raise


class RedisLockManager:
    def __init__(self, client: Any, *, key_prefix: str = "gwg:wallet-lock") -> None:
        self.client = client
        self.key_prefix = key_prefix

    @classmethod
    def from_url(cls, redis_url: str) -> "RedisLockManager":
        try:
            import redis
        except ImportError as exc:
            raise ConcurrencyLockError(
                "Redis is configured but redis-py is not installed. Install requirements-redis.txt."
            ) from exc

        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        # Connect lazily on SET. This lets MySQL serve already-recorded
        # idempotent replays even if Redis is temporarily unavailable.
        return cls(client)

    def wallet_lock(
        self,
        *,
        client_id: int,
        external_player_id: str,
        currency: str,
        ttl_ms: int = 30_000,
        blocking_timeout: float = 2.0,
    ) -> RedisLock:
        identity = f"{client_id}:{external_player_id}:{currency.strip().upper()}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return RedisLock(
            self.client,
            f"{self.key_prefix}:{digest}",
            ttl_ms=ttl_ms,
            blocking_timeout=blocking_timeout,
        )
