"""
Programmatic helpers to create / drop RBAC tables.

Usage in FastAPI app startup (lifespan):

    from fastapi_role_permission.migrations import create_tables

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await create_tables(engine)   # idempotent — safe to call every startup
        yield

Usage in tests:

    await create_tables(engine)
    # ... run tests ...
    await drop_tables(engine)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


async def create_tables(engine: "AsyncEngine") -> None:
    """
    Create all 5 RBAC tables if they don't already exist.

    Safe to call at every app startup — SQLAlchemy's create_all is idempotent
    (uses CREATE TABLE IF NOT EXISTS internally).

    Tables created:
      - permissions
      - roles
      - role_has_permissions
      - model_has_permissions
      - model_has_roles
    """
    from .models.base import RBACBase

    async with engine.begin() as conn:
        await conn.run_sync(RBACBase.metadata.create_all)


async def drop_tables(engine: "AsyncEngine") -> None:
    """
    Drop all RBAC tables.

    Useful for test teardown and development resets.
    Drops in reverse FK order to avoid constraint violations.
    """
    from .models.base import RBACBase

    async with engine.begin() as conn:
        await conn.run_sync(RBACBase.metadata.drop_all)
