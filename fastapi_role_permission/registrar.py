from __future__ import annotations

import contextvars
import json
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from .cache.base import BaseCache
    from .config import PermissionConfig

# Per-request team context — safe for concurrent async requests
_team_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "rbac_team_id", default=None
)


class PermissionRegistrar:
    """
    Central cache manager — mirrors Laravel's PermissionRegistrar.

    Stores on FastAPI app.state.rbac after init_rbac() is called.
    """

    def __init__(self, config: "PermissionConfig", cache: "BaseCache") -> None:
        self._config = config
        self._cache = cache

    # ------------------------------------------------------------------ #
    # Team context (per-request via ContextVar)                           #
    # ------------------------------------------------------------------ #

    def set_team_id(self, team_id: int | None) -> None:
        _team_id_var.set(team_id)

    def get_team_id(self) -> int | None:
        return _team_id_var.get()

    # ------------------------------------------------------------------ #
    # Cache management                                                    #
    # ------------------------------------------------------------------ #

    async def get_all_permissions(self, db: "AsyncSession") -> list[dict]:
        """
        Load all permissions (with their role IDs) from cache or DB.
        Returns a list of dicts: {id, name, guard_name, role_ids}.
        """
        raw = await self._cache.get(self._config.get_cache_key())
        if raw is not None:
            return json.loads(raw)

        from .models.permission import Permission

        result = await db.execute(
            select(Permission).options(selectinload(Permission.roles))
        )
        permissions = result.scalars().all()

        data = [
            {
                "id": p.id,
                "name": p.name,
                "guard_name": p.guard_name,
                "role_ids": [r.id for r in p.roles],
            }
            for p in permissions
        ]
        await self._cache.set(
            self._config.get_cache_key(),
            json.dumps(data).encode(),
            ex=self._config.cache_expiration,
        )
        return data

    async def forget_cached_permissions(self) -> None:
        await self._cache.delete(self._config.get_cache_key())

    async def reload_permissions(self, db: "AsyncSession") -> list[dict]:
        await self.forget_cached_permissions()
        return await self.get_all_permissions(db)
