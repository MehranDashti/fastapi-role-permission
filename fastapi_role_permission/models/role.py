from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, UniqueConstraint, select, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import RBACBase
from .permission import Permission, role_has_permissions_table

if TYPE_CHECKING:
    pass


class Role(RBACBase):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", "guard_name", name="uq_roles_name_guard"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(125), nullable=False)
    guard_name: Mapped[str] = mapped_column(String(125), nullable=False, default="default")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary=role_has_permissions_table,
        back_populates="roles",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role name={self.name!r} guard={self.guard_name!r}>"

    # ------------------------------------------------------------------ #
    # Factory classmethods                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str | None = None,
        team_id: int | None = None,
        description: str | None = None,
    ) -> "Role":
        from .._state import get_config
        from ..exceptions import RoleAlreadyExists

        guard = guard_name or get_config().guard_name
        existing = await cls._find(db, name, guard, team_id)
        if existing is not None:
            raise RoleAlreadyExists.create(name, guard)

        role = cls(name=name, guard_name=guard, team_id=team_id, description=description)
        db.add(role)
        await db.flush()
        await db.refresh(role)
        await cls._bust_cache()
        return role

    @classmethod
    async def find_by_name(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str | None = None,
        team_id: int | None = None,
    ) -> "Role":
        from .._state import get_config
        from ..exceptions import RoleDoesNotExist

        guard = guard_name or get_config().guard_name
        result = await cls._find(db, name, guard, team_id)
        if result is None:
            raise RoleDoesNotExist.create(name, guard)
        return result

    @classmethod
    async def find_by_id(
        cls,
        db: AsyncSession,
        id: int,
        guard_name: str | None = None,
    ) -> "Role":
        from .._state import get_config
        from ..exceptions import RoleDoesNotExist

        guard = guard_name or get_config().guard_name
        stmt = select(cls).where(cls.id == id, cls.guard_name == guard)
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()
        if role is None:
            raise RoleDoesNotExist.with_id(id, guard)
        return role

    @classmethod
    async def find_or_create(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str | None = None,
        team_id: int | None = None,
    ) -> "Role":
        from .._state import get_config

        guard = guard_name or get_config().guard_name
        existing = await cls._find(db, name, guard, team_id)
        if existing is not None:
            return existing
        return await cls.create(db, name, guard, team_id)

    # ------------------------------------------------------------------ #
    # Permission management                                                #
    # ------------------------------------------------------------------ #

    async def give_permission_to(
        self,
        db: AsyncSession,
        *permissions: str | Permission,
    ) -> "Role":
        for perm in permissions:
            resolved = await self._resolve_permission(db, perm)
            if resolved not in self.permissions:
                self.permissions.append(resolved)
        await db.flush()
        await self._bust_cache()
        return self

    async def revoke_permission_to(
        self,
        db: AsyncSession,
        *permissions: str | Permission,
    ) -> "Role":
        for perm in permissions:
            resolved = await self._resolve_permission(db, perm)
            if resolved in self.permissions:
                self.permissions.remove(resolved)
        await db.flush()
        await self._bust_cache()
        return self

    async def sync_permissions(
        self,
        db: AsyncSession,
        permissions: list[str | Permission],
    ) -> "Role":
        resolved = [await self._resolve_permission(db, p) for p in permissions]
        self.permissions = resolved
        await db.flush()
        await self._bust_cache()
        return self

    async def has_permission_to(
        self,
        db: AsyncSession,
        permission: str | Permission,
    ) -> bool:
        resolved = await self._resolve_permission(db, permission)
        return resolved in self.permissions

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    async def _find(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str,
        team_id: int | None = None,
    ) -> "Role | None":
        stmt = select(cls).where(cls.name == name, cls.guard_name == guard_name)
        if team_id is not None:
            stmt = stmt.where(cls.team_id == team_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _resolve_permission(
        self,
        db: AsyncSession,
        permission: str | Permission,
    ) -> Permission:
        if isinstance(permission, str):
            return await Permission.find_by_name(db, permission)
        return permission

    @staticmethod
    async def _bust_cache() -> None:
        try:
            from .._state import get_registrar
            await get_registrar().forget_cached_permissions()
        except RuntimeError:
            pass
