import asyncio
import time

import pytest

from fastapi_role_permission.cache.memory_cache import InMemoryCache
from fastapi_role_permission import Permission
from fastapi_role_permission.registrar import PermissionRegistrar
from fastapi_role_permission.config import PermissionConfig


# ------------------------------------------------------------------ #
# InMemoryCache                                                       #
# ------------------------------------------------------------------ #

async def test_set_and_get(cache):
    await cache.set("k1", b"hello", ex=60)
    assert await cache.get("k1") == b"hello"


async def test_get_missing_key(cache):
    assert await cache.get("missing") is None


async def test_delete(cache):
    await cache.set("k2", b"val", ex=60)
    await cache.delete("k2")
    assert await cache.get("k2") is None


async def test_exists(cache):
    await cache.set("k3", b"x", ex=60)
    assert await cache.exists("k3")
    await cache.delete("k3")
    assert not await cache.exists("k3")


async def test_expiry(cache):
    await cache.set("k4", b"expires", ex=1)
    assert await cache.get("k4") == b"expires"
    # Manually expire by manipulating store
    key = "k4"
    cache._store[key] = (cache._store[key][0], time.monotonic() - 1)
    assert await cache.get("k4") is None


# ------------------------------------------------------------------ #
# PermissionRegistrar caching                                         #
# ------------------------------------------------------------------ #

async def test_registrar_loads_permissions(db, cache):
    await Permission.create(db, "cached.perm")
    cfg = PermissionConfig()
    reg = PermissionRegistrar(config=cfg, cache=cache)
    perms = await reg.get_all_permissions(db)
    assert any(p["name"] == "cached.perm" for p in perms)


async def test_registrar_returns_from_cache_on_second_call(db, cache):
    await Permission.create(db, "repeat.perm")
    cfg = PermissionConfig()
    reg = PermissionRegistrar(config=cfg, cache=cache)
    perms1 = await reg.get_all_permissions(db)
    # Second call should be from cache (same data)
    perms2 = await reg.get_all_permissions(db)
    assert perms1 == perms2


async def test_registrar_forget_clears_cache(db, cache):
    await Permission.create(db, "forget.me")
    cfg = PermissionConfig()
    reg = PermissionRegistrar(config=cfg, cache=cache)
    await reg.get_all_permissions(db)
    assert await cache.exists(cfg.get_cache_key())
    await reg.forget_cached_permissions()
    assert not await cache.exists(cfg.get_cache_key())


async def test_registrar_busted_on_permission_create(db, cache):
    cfg = PermissionConfig()
    reg = PermissionRegistrar(config=cfg, cache=cache)

    from fastapi_role_permission import _state
    _state.set_registrar(reg)

    # Populate cache
    await reg.get_all_permissions(db)
    assert await cache.exists(cfg.get_cache_key())

    # Creating a new permission busts cache
    await Permission.create(db, "new.one")
    assert not await cache.exists(cfg.get_cache_key())

    # Reload shows new permission
    perms = await reg.get_all_permissions(db)
    assert any(p["name"] == "new.one" for p in perms)


async def test_registrar_reload(db, cache):
    await Permission.create(db, "before.reload")
    cfg = PermissionConfig()
    reg = PermissionRegistrar(config=cfg, cache=cache)
    await reg.get_all_permissions(db)

    from fastapi_role_permission import _state
    _state.set_registrar(reg)

    await Permission.create(db, "after.reload")
    reloaded = await reg.reload_permissions(db)
    names = [p["name"] for p in reloaded]
    assert "before.reload" in names
    assert "after.reload" in names


# ------------------------------------------------------------------ #
# Team context via ContextVar                                         #
# ------------------------------------------------------------------ #

async def test_team_id_context_var():
    cfg = PermissionConfig()
    cache = InMemoryCache()
    reg = PermissionRegistrar(config=cfg, cache=cache)

    reg.set_team_id(42)
    assert reg.get_team_id() == 42
    reg.set_team_id(None)
    assert reg.get_team_id() is None


async def test_team_id_isolated_between_concurrent_tasks():
    cfg = PermissionConfig()
    cache = InMemoryCache()
    reg = PermissionRegistrar(config=cfg, cache=cache)

    results = {}

    async def task(tid, name):
        reg.set_team_id(tid)
        await asyncio.sleep(0)  # yield control
        results[name] = reg.get_team_id()

    await asyncio.gather(task(1, "t1"), task(2, "t2"), task(3, "t3"))
    # Each task should have its own context
    assert results["t1"] == 1
    assert results["t2"] == 2
    assert results["t3"] == 3
