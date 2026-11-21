"""Online status in Redis: one sorted set per workspace, each socket an entry scored by the
time it lapses (rules in apps/core/presence.py)."""

import time

import redis.asyncio as redis
from django.conf import settings

from apps.core.presence import TTL, entry, online


def _key(workspace_id: int) -> str:
    return f"{settings.PRESENCE_KEY_PREFIX}:{workspace_id}"


def _client() -> "redis.Redis":
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def _alive(client: "redis.Redis", key: str) -> set[int]:
    await client.zremrangebyscore(key, "-inf", time.time())
    members = await client.zrange(key, 0, -1)
    return online(str(member) for member in members)


async def connect(workspace_id: int, user_id: int, connection: str) -> bool:
    """Count this socket. True when the person was offline until now."""
    key = _key(workspace_id)
    async with _client() as client:
        was_online = user_id in await _alive(client, key)
        await client.zadd(key, {entry(user_id, connection): time.time() + TTL})
        await client.expire(key, TTL * 2)
    return not was_online


async def refresh(workspace_id: int, user_id: int, connection: str) -> None:
    key = _key(workspace_id)
    async with _client() as client:
        await client.zadd(key, {entry(user_id, connection): time.time() + TTL})
        await client.expire(key, TTL * 2)


async def disconnect(workspace_id: int, user_id: int, connection: str) -> bool:
    """Stop counting this socket. True when it was the person's last one."""
    key = _key(workspace_id)
    async with _client() as client:
        await client.zrem(key, entry(user_id, connection))
        return user_id not in await _alive(client, key)


async def online_users(workspace_id: int) -> set[int]:
    async with _client() as client:
        return await _alive(client, _key(workspace_id))
