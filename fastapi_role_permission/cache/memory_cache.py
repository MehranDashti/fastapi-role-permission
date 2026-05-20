import time

from .base import BaseCache


class InMemoryCache(BaseCache):
    """Simple in-memory cache with TTL. Not shared across processes."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, float]] = {}  # key -> (value, expire_at)

    async def get(self, key: str) -> bytes | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if time.monotonic() > expire_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: bytes, ex: int) -> None:
        self._store[key] = (value, time.monotonic() + ex)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    def clear(self) -> None:
        self._store.clear()
