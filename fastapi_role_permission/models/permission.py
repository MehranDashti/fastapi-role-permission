from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import RBACBase

if TYPE_CHECKING:
    from .role import Role

# Junction table: role_has_permissions
# Created here because Permission is the "owned" side of the many-to-many.
role_has_permissions_table = Table(
    "role_has_permissions",
    RBACBase.metadata,
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Junction tables for polymorphic model associations
model_has_permissions_table = Table(
    "model_has_permissions",
    RBACBase.metadata,
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("model_type", String(125), nullable=False),
    Column("model_id", Integer, nullable=False),
    Column("team_id", Integer, nullable=True),
)

model_has_roles_table = Table(
    "model_has_roles",
    RBACBase.metadata,
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("model_type", String(125), nullable=False),
    Column("model_id", Integer, nullable=False),
    Column("team_id", Integer, nullable=True),
)


class Permission(RBACBase):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("name", "guard_name", name="uq_permissions_name_guard"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(125), nullable=False)
    guard_name: Mapped[str] = mapped_column(String(125), nullable=False, default="default")
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

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_has_permissions_table,
        back_populates="permissions",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Permission name={self.name!r} guard={self.guard_name!r}>"

    # ------------------------------------------------------------------ #
    # Factory classmethods                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str | None = None,
    ) -> "Permission":
        from .._state import get_config
        from ..exceptions import PermissionAlreadyExists

        guard = guard_name or get_config().guard_name
        existing = await cls._find(db, name, guard)
        if existing is not None:
            raise PermissionAlreadyExists.create(name, guard)

        permission = cls(name=name, guard_name=guard)
        db.add(permission)
        await db.flush()
        await db.refresh(permission)
        await cls._bust_cache()
        return permission

    @classmethod
    async def find_by_name(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str | None = None,
    ) -> "Permission":
        from .._state import get_config
        from ..exceptions import PermissionDoesNotExist

        guard = guard_name or get_config().guard_name
        result = await cls._find(db, name, guard)
        if result is None:
            raise PermissionDoesNotExist.create(name, guard)
        return result

    @classmethod
    async def find_by_id(
        cls,
        db: AsyncSession,
        id: int,
        guard_name: str | None = None,
    ) -> "Permission":
        from .._state import get_config
        from ..exceptions import PermissionDoesNotExist

        guard = guard_name or get_config().guard_name
        stmt = select(cls).where(cls.id == id, cls.guard_name == guard)
        result = await db.execute(stmt)
        permission = result.scalar_one_or_none()
        if permission is None:
            raise PermissionDoesNotExist.with_id(id, guard)
        return permission

    @classmethod
    async def find_or_create(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str | None = None,
    ) -> "Permission":
        from .._state import get_config

        guard = guard_name or get_config().guard_name
        existing = await cls._find(db, name, guard)
        if existing is not None:
            return existing
        return await cls.create(db, name, guard)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    async def _find(
        cls,
        db: AsyncSession,
        name: str,
        guard_name: str,
    ) -> "Permission | None":
        stmt = select(cls).where(cls.name == name, cls.guard_name == guard_name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _bust_cache() -> None:
        try:
            from .._state import get_registrar
            await get_registrar().forget_cached_permissions()
        except RuntimeError:
            pass
