from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from .permission import Permission
    from .role import Role


def _audit(cfg: "Any", action: str, subject: str, model_type: str, model_id: int) -> None:
    if not cfg.enable_audit_logging:
        return
    logging.getLogger(cfg.audit_logger_name).info(
        json.dumps({
            "action": action,
            "subject": subject,
            "model_type": model_type,
            "model_id": model_id,
        })
    )


class HasPermissions:
    """
    Mixin that adds permission management to any SQLAlchemy model (e.g. User).

    Requires:
    - self.id       — primary key
    - self.__tablename__  — used as model_type in junction tables

    setup_relationships() must be called via init_rbac() before use.
    """

    # ------------------------------------------------------------------ #
    # Grant / revoke direct permissions                                   #
    # ------------------------------------------------------------------ #

    async def give_permission_to(
        self,
        db: AsyncSession,
        *permissions: "str | Permission",
        team_id: int | None = None,
    ) -> "Any":
        from .permission import Permission, model_has_permissions_table
        from .._state import get_config, get_registrar

        cfg = get_config()
        t = model_has_permissions_table
        tid = team_id if cfg.teams_enabled else None

        for perm in permissions:
            resolved = await self._resolve_permission(db, perm)
            # Skip if already granted
            cond = [
                t.c.model_type == self.__tablename__,
                t.c.model_id == self.id,
                t.c.permission_id == resolved.id,
            ]
            if cfg.teams_enabled:
                cond.append(t.c.team_id == tid)
            exists = (await db.execute(select(t).where(*cond))).first()
            if exists is None:
                values: dict = {
                    "model_type": self.__tablename__,
                    "model_id": self.id,
                    "permission_id": resolved.id,
                }
                if cfg.teams_enabled:
                    values["team_id"] = tid
                await db.execute(insert(t).values(**values))

        await db.flush()
        await get_registrar().forget_cached_permissions()
        for perm in permissions:
            name = perm.name if not isinstance(perm, str) else perm
            _audit(cfg, "give_permission", name, self.__tablename__, self.id)
        return self

    async def revoke_permission_to(
        self,
        db: AsyncSession,
        *permissions: "str | Permission",
        team_id: int | None = None,
    ) -> "Any":
        from .permission import Permission, model_has_permissions_table
        from .._state import get_config, get_registrar

        cfg = get_config()
        t = model_has_permissions_table
        tid = team_id if cfg.teams_enabled else None

        for perm in permissions:
            resolved = await self._resolve_permission(db, perm)
            cond = [
                t.c.model_type == self.__tablename__,
                t.c.model_id == self.id,
                t.c.permission_id == resolved.id,
            ]
            if cfg.teams_enabled:
                cond.append(t.c.team_id == tid)
            await db.execute(delete(t).where(*cond))

        await db.flush()
        await get_registrar().forget_cached_permissions()
        for perm in permissions:
            name = perm.name if not isinstance(perm, str) else perm
            _audit(cfg, "revoke_permission", name, self.__tablename__, self.id)
        return self

    async def sync_permissions(
        self,
        db: AsyncSession,
        permissions: list["str | Permission"],
        team_id: int | None = None,
    ) -> "Any":
        from .permission import model_has_permissions_table
        from .._state import get_config, get_registrar

        cfg = get_config()
        t = model_has_permissions_table
        tid = team_id if cfg.teams_enabled else None

        # Remove all existing direct permissions
        cond = [
            t.c.model_type == self.__tablename__,
            t.c.model_id == self.id,
        ]
        if cfg.teams_enabled:
            cond.append(t.c.team_id == tid)
        await db.execute(delete(t).where(*cond))

        # Re-add the new set
        for perm in permissions:
            resolved = await self._resolve_permission(db, perm)
            values: dict = {
                "model_type": self.__tablename__,
                "model_id": self.id,
                "permission_id": resolved.id,
            }
            if cfg.teams_enabled:
                values["team_id"] = tid
            await db.execute(insert(t).values(**values))

        await db.flush()
        await get_registrar().forget_cached_permissions()
        return self

    # ------------------------------------------------------------------ #
    # Permission checks                                                    #
    # ------------------------------------------------------------------ #

    async def has_permission_to(
        self,
        db: AsyncSession,
        permission: "str | Permission",
        guard_name: str | None = None,
        team_id: int | None = None,
    ) -> bool:
        from .._state import get_config
        from .permission import Permission

        cfg = get_config()

        if isinstance(permission, str):
            name = permission
        else:
            name = permission.name

        if cfg.wildcard_enabled:
            all_names = await self.get_permission_names(db, team_id=team_id)
            from ..wildcard import WildcardPermission
            return WildcardPermission.check(name, all_names)

        if await self.has_direct_permission(db, permission, team_id=team_id):
            return True
        return await self.has_permission_via_role(db, permission, team_id=team_id)

    async def check_permission_to(
        self,
        db: AsyncSession,
        permission: "str | Permission",
        guard_name: str | None = None,
        team_id: int | None = None,
    ) -> bool:
        """Silent version — returns False instead of raising PermissionDoesNotExist."""
        try:
            return await self.has_permission_to(db, permission, guard_name, team_id)
        except Exception:
            return False

    async def has_direct_permission(
        self,
        db: AsyncSession,
        permission: "str | Permission",
        team_id: int | None = None,
    ) -> bool:
        from .permission import Permission, model_has_permissions_table
        from .._state import get_config

        cfg = get_config()
        resolved = await self._resolve_permission(db, permission)
        t = model_has_permissions_table
        tid = team_id if cfg.teams_enabled else None

        cond = [
            t.c.model_type == self.__tablename__,
            t.c.model_id == self.id,
            t.c.permission_id == resolved.id,
        ]
        if cfg.teams_enabled:
            cond.append(t.c.team_id == tid)

        result = (await db.execute(select(t).where(*cond))).first()
        return result is not None

    async def has_permission_via_role(
        self,
        db: AsyncSession,
        permission: "str | Permission",
        team_id: int | None = None,
    ) -> bool:
        resolved = await self._resolve_permission(db, permission)
        roles = await self._get_roles_from_db(db, team_id=team_id)
        for role in roles:
            if resolved in role.permissions:
                return True
        return False

    async def has_any_permission(
        self,
        db: AsyncSession,
        *permissions: str,
        team_id: int | None = None,
    ) -> bool:
        for perm in permissions:
            if await self.check_permission_to(db, perm, team_id=team_id):
                return True
        return False

    async def has_all_permissions(
        self,
        db: AsyncSession,
        *permissions: str,
        team_id: int | None = None,
    ) -> bool:
        for perm in permissions:
            if not await self.check_permission_to(db, perm, team_id=team_id):
                return False
        return True

    async def has_any_direct_permission(
        self,
        db: AsyncSession,
        *permissions: str,
        team_id: int | None = None,
    ) -> bool:
        for perm in permissions:
            try:
                if await self.has_direct_permission(db, perm, team_id=team_id):
                    return True
            except Exception:
                pass
        return False

    async def has_all_direct_permissions(
        self,
        db: AsyncSession,
        *permissions: str,
        team_id: int | None = None,
    ) -> bool:
        for perm in permissions:
            try:
                if not await self.has_direct_permission(db, perm, team_id=team_id):
                    return False
            except Exception:
                return False
        return True

    # ------------------------------------------------------------------ #
    # Getters                                                              #
    # ------------------------------------------------------------------ #

    async def get_direct_permissions(
        self,
        db: AsyncSession,
        team_id: int | None = None,
    ) -> list["Permission"]:
        from .permission import Permission, model_has_permissions_table
        from .._state import get_config

        cfg = get_config()
        t = model_has_permissions_table
        tid = team_id if cfg.teams_enabled else None

        cond = [
            t.c.model_type == self.__tablename__,
            t.c.model_id == self.id,
        ]
        if cfg.teams_enabled:
            cond.append(t.c.team_id == tid)

        perm_ids_result = await db.execute(select(t.c.permission_id).where(*cond))
        perm_ids = [row[0] for row in perm_ids_result]
        if not perm_ids:
            return []

        result = await db.execute(
            select(Permission).where(Permission.id.in_(perm_ids))
        )
        return list(result.scalars().all())

    async def get_permissions_via_roles(
        self,
        db: AsyncSession,
        team_id: int | None = None,
    ) -> list["Permission"]:
        roles = await self._get_roles_from_db(db, team_id=team_id)
        perms: list["Permission"] = []
        seen: set[int] = set()
        for role in roles:
            for perm in role.permissions:
                if perm.id not in seen:
                    seen.add(perm.id)
                    perms.append(perm)
        return perms

    async def get_all_permissions(
        self,
        db: AsyncSession,
        team_id: int | None = None,
    ) -> list["Permission"]:
        direct = await self.get_direct_permissions(db, team_id=team_id)
        via_roles = await self.get_permissions_via_roles(db, team_id=team_id)
        seen: set[int] = set()
        result: list["Permission"] = []
        for p in direct + via_roles:
            if p.id not in seen:
                seen.add(p.id)
                result.append(p)
        return result

    async def get_permission_names(
        self,
        db: AsyncSession,
        team_id: int | None = None,
    ) -> list[str]:
        perms = await self.get_all_permissions(db, team_id=team_id)
        return [p.name for p in perms]

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _resolve_permission(
        self,
        db: AsyncSession,
        permission: "str | Permission",
    ) -> "Permission":
        from .permission import Permission
        if isinstance(permission, str):
            return await Permission.find_by_name(db, permission)
        return permission

    async def _get_roles_from_db(
        self,
        db: AsyncSession,
        team_id: int | None = None,
    ) -> list["Role"]:
        from .role import Role
        from .permission import model_has_roles_table
        from .._state import get_config

        cfg = get_config()
        t = model_has_roles_table
        tid = team_id if cfg.teams_enabled else None

        cond = [
            t.c.model_type == self.__tablename__,
            t.c.model_id == self.id,
        ]
        if cfg.teams_enabled:
            cond.append(t.c.team_id == tid)

        role_ids_result = await db.execute(select(t.c.role_id).where(*cond))
        role_ids = [row[0] for row in role_ids_result]
        if not role_ids:
            return []

        result = await db.execute(
            select(Role).where(Role.id.in_(role_ids)).options(selectinload(Role.permissions))
        )
        return list(result.scalars().all())


class HasRoles(HasPermissions):
    """
    Mixin that adds role AND permission management to any SQLAlchemy model.

    Add this to your User model:
        class User(Base, HasRoles):
            __tablename__ = "users"
            ...
    """

    # ------------------------------------------------------------------ #
    # Assign / remove roles                                               #
    # ------------------------------------------------------------------ #

    async def assign_role(
        self,
        db: AsyncSession,
        *roles: "str | Role",
        team_id: int | None = None,
    ) -> "Any":
        from .role import Role
        from .permission import model_has_roles_table
        from .._state import get_config, get_registrar

        cfg = get_config()
        t = model_has_roles_table
        tid = team_id if cfg.teams_enabled else None

        for role in roles:
            resolved = await self._resolve_role(db, role)
            cond = [
                t.c.model_type == self.__tablename__,
                t.c.model_id == self.id,
                t.c.role_id == resolved.id,
            ]
            if cfg.teams_enabled:
                cond.append(t.c.team_id == tid)
            exists = (await db.execute(select(t).where(*cond))).first()
            if exists is None:
                values: dict = {
                    "model_type": self.__tablename__,
                    "model_id": self.id,
                    "role_id": resolved.id,
                }
                if cfg.teams_enabled:
                    values["team_id"] = tid
                await db.execute(insert(t).values(**values))

        await db.flush()
        await get_registrar().forget_cached_permissions()
        for role in roles:
            name = role.name if not isinstance(role, str) else role
            _audit(cfg, "assign_role", name, self.__tablename__, self.id)
        return self

    async def remove_role(
        self,
        db: AsyncSession,
        *roles: "str | Role",
        team_id: int | None = None,
    ) -> "Any":
        from .permission import model_has_roles_table
        from .._state import get_config, get_registrar

        cfg = get_config()
        t = model_has_roles_table
        tid = team_id if cfg.teams_enabled else None

        for role in roles:
            resolved = await self._resolve_role(db, role)
            cond = [
                t.c.model_type == self.__tablename__,
                t.c.model_id == self.id,
                t.c.role_id == resolved.id,
            ]
            if cfg.teams_enabled:
                cond.append(t.c.team_id == tid)
            await db.execute(delete(t).where(*cond))

        await db.flush()
        await get_registrar().forget_cached_permissions()
        for role in roles:
            name = role.name if not isinstance(role, str) else role
            _audit(cfg, "remove_role", name, self.__tablename__, self.id)
        return self

    async def sync_roles(
        self,
        db: AsyncSession,
        roles: list["str | Role"],
        team_id: int | None = None,
    ) -> "Any":
        from .permission import model_has_roles_table
        from .._state import get_config, get_registrar

        cfg = get_config()
        t = model_has_roles_table
        tid = team_id if cfg.teams_enabled else None

        cond = [
            t.c.model_type == self.__tablename__,
            t.c.model_id == self.id,
        ]
        if cfg.teams_enabled:
            cond.append(t.c.team_id == tid)
        await db.execute(delete(t).where(*cond))

        for role in roles:
            resolved = await self._resolve_role(db, role)
            values: dict = {
                "model_type": self.__tablename__,
                "model_id": self.id,
                "role_id": resolved.id,
            }
            if cfg.teams_enabled:
                values["team_id"] = tid
            await db.execute(insert(t).values(**values))

        await db.flush()
        await get_registrar().forget_cached_permissions()
        return self

    # ------------------------------------------------------------------ #
    # Batch operations (class methods)                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    async def bulk_assign_roles(
        cls,
        db: AsyncSession,
        models: "list[Any]",
        role: "str | Role",
        team_id: int | None = None,
    ) -> None:
        """Assign a single role to many model instances in one INSERT."""
        from .role import Role
        from .permission import model_has_roles_table
        from .._state import get_config, get_registrar

        if not models:
            return

        cfg = get_config()
        t = model_has_roles_table
        tid = team_id if cfg.teams_enabled else None
        tablename = models[0].__tablename__

        resolved = await Role.find_by_name(db, role) if isinstance(role, str) else role

        existing_result = await db.execute(
            select(t.c.model_id).where(
                t.c.model_type == tablename,
                t.c.role_id == resolved.id,
            )
        )
        existing_ids = {row[0] for row in existing_result}

        rows = [
            {"model_type": tablename, "model_id": m.id, "role_id": resolved.id,
             **({} if not cfg.teams_enabled else {"team_id": tid})}
            for m in models
            if m.id not in existing_ids
        ]
        if rows:
            await db.execute(insert(t), rows)
            await db.flush()
            await get_registrar().forget_cached_permissions()

    @classmethod
    async def bulk_give_permission_to(
        cls,
        db: AsyncSession,
        models: "list[Any]",
        permission: "str | Permission",
        team_id: int | None = None,
    ) -> None:
        """Give a single permission to many model instances in one INSERT."""
        from .permission import Permission, model_has_permissions_table
        from .._state import get_config, get_registrar

        if not models:
            return

        cfg = get_config()
        t = model_has_permissions_table
        tid = team_id if cfg.teams_enabled else None
        tablename = models[0].__tablename__

        resolved = (
            await Permission.find_by_name(db, permission)
            if isinstance(permission, str)
            else permission
        )

        existing_result = await db.execute(
            select(t.c.model_id).where(
                t.c.model_type == tablename,
                t.c.permission_id == resolved.id,
            )
        )
        existing_ids = {row[0] for row in existing_result}

        rows = [
            {"model_type": tablename, "model_id": m.id, "permission_id": resolved.id,
             **({} if not cfg.teams_enabled else {"team_id": tid})}
            for m in models
            if m.id not in existing_ids
        ]
        if rows:
            await db.execute(insert(t), rows)
            await db.flush()
            await get_registrar().forget_cached_permissions()

    # ------------------------------------------------------------------ #
    # Role checks                                                         #
    # ------------------------------------------------------------------ #

    async def has_role(
        self,
        db: AsyncSession,
        *roles: "str | Role",
        team_id: int | None = None,
    ) -> bool:
        current_roles = await self._get_roles_from_db(db, team_id=team_id)
        current_names = {r.name for r in current_roles}
        current_ids = {r.id for r in current_roles}

        for role in roles:
            if isinstance(role, str):
                if role in current_names:
                    return True
            else:
                if role.id in current_ids:
                    return True
        return False

    async def has_any_role(
        self,
        db: AsyncSession,
        *roles: "str | Role",
        team_id: int | None = None,
    ) -> bool:
        return await self.has_role(db, *roles, team_id=team_id)

    async def has_all_roles(
        self,
        db: AsyncSession,
        *roles: "str | Role",
        team_id: int | None = None,
    ) -> bool:
        current_roles = await self._get_roles_from_db(db, team_id=team_id)
        current_names = {r.name for r in current_roles}
        current_ids = {r.id for r in current_roles}

        for role in roles:
            if isinstance(role, str):
                if role not in current_names:
                    return False
            else:
                if role.id not in current_ids:
                    return False
        return True

    async def has_exact_roles(
        self,
        db: AsyncSession,
        *roles: "str | Role",
        team_id: int | None = None,
    ) -> bool:
        current_roles = await self._get_roles_from_db(db, team_id=team_id)
        current_names = {r.name for r in current_roles}
        given_names: set[str] = set()

        for role in roles:
            if isinstance(role, str):
                given_names.add(role)
            else:
                given_names.add(role.name)

        return current_names == given_names

    async def get_role_names(
        self,
        db: AsyncSession,
        team_id: int | None = None,
    ) -> list[str]:
        roles = await self._get_roles_from_db(db, team_id=team_id)
        return [r.name for r in roles]

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _resolve_role(
        self,
        db: AsyncSession,
        role: "str | Role",
    ) -> "Role":
        from .role import Role
        if isinstance(role, str):
            return await Role.find_by_name(db, role)
        return role
