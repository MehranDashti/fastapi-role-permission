from .base import BaseCache


class RedisCache(BaseCache):
    """Redis-backed cache using redis.asyncio."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(redis_url, decode_responses=False)

    async def get(self, key: str) -> bytes | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: bytes, ex: int) -> None:
        await self._redis.set(key, value, ex=ex)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def close(self) -> None:
        await self._redis.aclose()
