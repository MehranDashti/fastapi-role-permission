import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String

from fastapi_role_permission import init_rbac, HasRoles, PermissionConfig
from fastapi_role_permission.models.base import RBACBase
from fastapi_role_permission import _state
from fastapi_role_permission.cache.memory_cache import InMemoryCache
from fastapi_role_permission.registrar import PermissionRegistrar


# --------------------------------------------------------------------------- #
# Host-app User model (simulates what a real app would define)                 #
# --------------------------------------------------------------------------- #

class AppBase(DeclarativeBase):
    pass


class User(AppBase, HasRoles):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r}>"


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)
        await conn.run_sync(RBACBase.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def cache():
    return InMemoryCache()


@pytest_asyncio.fixture(autouse=True)
async def setup_state(cache):
    """Initialize _state before each test and reset after."""
    cfg = PermissionConfig()
    registrar = PermissionRegistrar(config=cfg, cache=cache)
    _state.set_config(cfg)
    _state.set_registrar(registrar)

    async def get_db():
        pass

    async def get_current_user():
        pass

    _state.set_get_db(get_db)
    _state.set_get_current_user(get_current_user)

    yield

    _state.reset()


@pytest_asyncio.fixture
async def registrar(cache):
    cfg = _state.get_config()
    return PermissionRegistrar(config=cfg, cache=cache)


@pytest_asyncio.fixture
async def user(db):
    u = User(name="alice")
    db.add(u)
    await db.flush()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def user2(db):
    u = User(name="bob")
    db.add(u)
    await db.flush()
    await db.refresh(u)
    return u
