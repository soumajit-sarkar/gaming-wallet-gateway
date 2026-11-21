from functools import lru_cache

from app.core.config import settings
from app.locks.redis_lock import RedisLockManager


@lru_cache(maxsize=1)
def get_redis_lock_manager() -> RedisLockManager | None:
    if not settings.redis_url:
        return None
    return RedisLockManager.from_url(settings.redis_url)
