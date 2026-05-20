"""
Seeder utility — bootstrap roles and permissions from a config dict.

Example:
    from fastapi_role_permission.seeders import seed_roles

    await seed_roles(db, {
        "admin":  ["*"],
        "editor": ["posts.read", "posts.write"],
        "viewer": ["posts.read"],
    })

Wildcard permissions like "*" are stored as literal permission names.
The function is idempotent: safe to call multiple times or in migrations.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def seed_roles(
    db: AsyncSession,
    config: dict[str, list[str]],
    guard_name: str | None = None,
) -> None:
    """
    Create roles and their permissions from a mapping.

    Args:
        db:         Open AsyncSession to use for all operations.
        config:     Dict of ``{role_name: [permission_name, ...]}``.
        guard_name: Guard to use (falls back to the global config default).
    """
    from .models.permission import Permission
    from .models.role import Role

    # Collect all unique permission names across all roles
    all_permission_names: set[str] = set()
    for perms in config.values():
        all_permission_names.update(perms)

    # Ensure every permission exists (find_or_create is idempotent)
    for perm_name in sorted(all_permission_names):
        await Permission.find_or_create(db, perm_name, guard_name)

    # Ensure every role exists and has the correct permissions synced
    for role_name, perm_names in config.items():
        role = await Role.find_or_create(db, role_name, guard_name)
        await role.sync_permissions(db, perm_names)
