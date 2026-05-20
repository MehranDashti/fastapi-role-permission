"""
Integration tests for require_* FastAPI dependencies and *Middleware classes.
Tests 200 (granted) / 403 (forbidden) / 401 (unauthenticated) response codes.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String

from fastapi_role_permission import HasRoles, Permission, Role
from fastapi_role_permission.models.base import RBACBase
from fastapi_role_permission import _state
from fastapi_role_permission.dependencies.checks import (
    require_permission,
    require_any_permission,
    require_role,
    require_any_role,
    require_role_or_permission,
)
from fastapi_role_permission.middleware.role import RoleMiddleware
from fastapi_role_permission.middleware.permission import PermissionMiddleware
from fastapi_role_permission.middleware.role_or_permission import RoleOrPermissionMiddleware


# ---------------------------------------------------------------------------
# Dedicated model — separate __tablename__ avoids conflicts with conftest User
# ---------------------------------------------------------------------------


class _IntBase(DeclarativeBase):
    pass


class IntUser(_IntBase, HasRoles):
    __tablename__ = "int_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def int_engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(_IntBase.metadata.create_all)
        await conn.run_sync(RBACBase.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def user_holder():
    """Mutable dict so tests can swap the active user between requests."""
    return {"current": None}


@pytest_asyncio.fixture
async def int_ctx(int_engine, user_holder):
    """
    Yields (session, get_db, get_current_user) and wires _state.
    get_db yields the *same* session used for setup so uncommitted
    data is immediately visible inside dependency/middleware handlers.
    Overrides the autouse setup_state fixture from conftest.py.
    """
    factory = async_sessionmaker(int_engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:

        async def get_db():
            yield session

        async def get_current_user(db=None):
            return user_holder["current"]

        _state.set_get_db(get_db)
        _state.set_get_current_user(get_current_user)

        yield session, get_db, get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(get_db, get_current_user):
    """Create a bare FastAPI app with app.state wired for middleware tests."""
    app = FastAPI()
    app.state.rbac_get_db = get_db
    app.state.rbac_get_current_user = get_current_user
    return app


async def _get(app, path: str = "/protected") -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(path)
    return r.status_code


# ---------------------------------------------------------------------------
# require_permission
# ---------------------------------------------------------------------------


async def test_require_permission_grants_200(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Permission.create(session, "posts.read")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.give_permission_to(session, "posts.read")
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_permission("posts.read")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_require_permission_returns_403(int_ctx, user_holder):
    session, _, _ = int_ctx

    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user  # no permissions

    app = FastAPI()

    @app.get("/protected", dependencies=[require_permission("posts.read")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


# ---------------------------------------------------------------------------
# require_any_permission
# ---------------------------------------------------------------------------


async def test_require_any_permission_grants_200(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Permission.create(session, "posts.write")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.give_permission_to(session, "posts.write")
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_any_permission("posts.read", "posts.write")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_require_any_permission_returns_403(int_ctx, user_holder):
    session, _, _ = int_ctx

    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_any_permission("posts.read", "posts.write")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------


async def test_require_role_grants_200(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Role.create(session, "admin")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.assign_role(session, "admin")
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_role("admin")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_require_role_returns_403(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Role.create(session, "admin")
    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user  # no roles

    app = FastAPI()

    @app.get("/protected", dependencies=[require_role("admin")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


# ---------------------------------------------------------------------------
# require_any_role
# ---------------------------------------------------------------------------


async def test_require_any_role_grants_200(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Role.create(session, "editor")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.assign_role(session, "editor")
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_any_role("admin", "editor")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_require_any_role_returns_403(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Role.create(session, "admin")
    await Role.create(session, "editor")
    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_any_role("admin", "editor")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


# ---------------------------------------------------------------------------
# require_role_or_permission
# ---------------------------------------------------------------------------


async def test_require_role_or_permission_grants_200_via_role(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Role.create(session, "admin")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.assign_role(session, "admin")
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_role_or_permission("admin", "posts.delete")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_require_role_or_permission_grants_200_via_permission(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Permission.create(session, "posts.delete")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.give_permission_to(session, "posts.delete")
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_role_or_permission("admin", "posts.delete")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_require_role_or_permission_returns_403(int_ctx, user_holder):
    session, _, _ = int_ctx

    await Role.create(session, "admin")
    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user

    app = FastAPI()

    @app.get("/protected", dependencies=[require_role_or_permission("admin", "posts.delete")])
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


# ---------------------------------------------------------------------------
# RoleMiddleware
# ---------------------------------------------------------------------------


async def test_role_middleware_grants_200(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Role.create(session, "admin")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.assign_role(session, "admin")
    user_holder["current"] = user

    app = _make_app(get_db, get_current_user)
    app.add_middleware(RoleMiddleware, roles="admin")

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_role_middleware_returns_403(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Role.create(session, "admin")
    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user  # no roles

    app = _make_app(get_db, get_current_user)
    app.add_middleware(RoleMiddleware, roles="admin")

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


async def test_role_middleware_returns_401_when_no_user(int_ctx, user_holder):
    _, get_db, get_current_user = int_ctx
    user_holder["current"] = None  # unauthenticated

    app = _make_app(get_db, get_current_user)
    app.add_middleware(RoleMiddleware, roles="admin")

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 401


async def test_role_middleware_skips_excluded_path(int_ctx, user_holder):
    _, get_db, get_current_user = int_ctx
    user_holder["current"] = None  # no user — would 401 if checked

    app = _make_app(get_db, get_current_user)
    app.add_middleware(RoleMiddleware, roles="admin", exclude_paths=["/public"])

    @app.get("/public")
    async def _():
        return {"ok": True}

    assert await _get(app, "/public") == 200


# ---------------------------------------------------------------------------
# PermissionMiddleware
# ---------------------------------------------------------------------------


async def test_permission_middleware_grants_200(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Permission.create(session, "reports.view")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.give_permission_to(session, "reports.view")
    user_holder["current"] = user

    app = _make_app(get_db, get_current_user)
    app.add_middleware(PermissionMiddleware, permissions="reports.view")

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_permission_middleware_returns_403(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user  # no permissions

    app = _make_app(get_db, get_current_user)
    app.add_middleware(PermissionMiddleware, permissions="reports.view")

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


async def test_permission_middleware_returns_401_when_no_user(int_ctx, user_holder):
    _, get_db, get_current_user = int_ctx
    user_holder["current"] = None

    app = _make_app(get_db, get_current_user)
    app.add_middleware(PermissionMiddleware, permissions="reports.view")

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 401


async def test_permission_middleware_any_of_grants_200(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Permission.create(session, "reports.export")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.give_permission_to(session, "reports.export")
    user_holder["current"] = user

    # require_all=False: user only needs one of the two permissions
    app = _make_app(get_db, get_current_user)
    app.add_middleware(
        PermissionMiddleware,
        permissions="reports.view|reports.export",
        require_all=False,
    )

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


# ---------------------------------------------------------------------------
# RoleOrPermissionMiddleware
# ---------------------------------------------------------------------------


async def test_role_or_permission_middleware_grants_200_via_role(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Role.create(session, "superuser")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.assign_role(session, "superuser")
    user_holder["current"] = user

    app = _make_app(get_db, get_current_user)
    app.add_middleware(
        RoleOrPermissionMiddleware,
        roles_or_permissions="superuser|posts.delete",
    )

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_role_or_permission_middleware_grants_200_via_permission(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Permission.create(session, "posts.delete")
    user = IntUser(name="alice")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    await user.give_permission_to(session, "posts.delete")
    user_holder["current"] = user

    app = _make_app(get_db, get_current_user)
    app.add_middleware(
        RoleOrPermissionMiddleware,
        roles_or_permissions="superuser|posts.delete",
    )

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 200


async def test_role_or_permission_middleware_returns_403(int_ctx, user_holder):
    session, get_db, get_current_user = int_ctx

    await Role.create(session, "superuser")
    user = IntUser(name="bob")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    user_holder["current"] = user

    app = _make_app(get_db, get_current_user)
    app.add_middleware(
        RoleOrPermissionMiddleware,
        roles_or_permissions="superuser|posts.delete",
    )

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 403


async def test_role_or_permission_middleware_returns_401_when_no_user(int_ctx, user_holder):
    _, get_db, get_current_user = int_ctx
    user_holder["current"] = None

    app = _make_app(get_db, get_current_user)
    app.add_middleware(
        RoleOrPermissionMiddleware,
        roles_or_permissions="superuser|posts.delete",
    )

    @app.get("/protected")
    async def _():
        return {"ok": True}

    assert await _get(app) == 401
