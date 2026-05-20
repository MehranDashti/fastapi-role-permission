import pytest
from fastapi_role_permission import Permission, Role
from fastapi_role_permission.exceptions import PermissionDoesNotExist


# ------------------------------------------------------------------ #
# Role assignment                                                      #
# ------------------------------------------------------------------ #

async def test_assign_role_by_name(db, user):
    await Role.create(db, "admin")
    await user.assign_role(db, "admin")
    assert await user.has_role(db, "admin")


async def test_assign_role_by_object(db, user):
    role = await Role.create(db, "editor")
    await user.assign_role(db, role)
    assert await user.has_role(db, role)


async def test_assign_multiple_roles(db, user):
    await Role.create(db, "admin")
    await Role.create(db, "editor")
    await user.assign_role(db, "admin", "editor")
    assert await user.has_role(db, "admin")
    assert await user.has_role(db, "editor")


async def test_assign_role_idempotent(db, user):
    await Role.create(db, "admin")
    await user.assign_role(db, "admin")
    await user.assign_role(db, "admin")  # no duplicate
    roles = await user.get_role_names(db)
    assert roles.count("admin") == 1


async def test_remove_role(db, user):
    await Role.create(db, "editor")
    await user.assign_role(db, "editor")
    await user.remove_role(db, "editor")
    assert not await user.has_role(db, "editor")


async def test_sync_roles(db, user):
    await Role.create(db, "admin")
    await Role.create(db, "editor")
    await Role.create(db, "viewer")
    await user.assign_role(db, "admin", "editor")
    await user.sync_roles(db, ["viewer"])
    assert not await user.has_role(db, "admin")
    assert not await user.has_role(db, "editor")
    assert await user.has_role(db, "viewer")


async def test_sync_roles_empty(db, user):
    await Role.create(db, "admin")
    await user.assign_role(db, "admin")
    await user.sync_roles(db, [])
    assert not await user.has_role(db, "admin")


# ------------------------------------------------------------------ #
# Role checks                                                         #
# ------------------------------------------------------------------ #

async def test_has_any_role(db, user):
    await Role.create(db, "admin")
    await Role.create(db, "editor")
    await user.assign_role(db, "editor")
    assert await user.has_any_role(db, "admin", "editor")
    assert not await user.has_any_role(db, "admin")


async def test_has_all_roles(db, user):
    await Role.create(db, "admin")
    await Role.create(db, "editor")
    await user.assign_role(db, "admin", "editor")
    assert await user.has_all_roles(db, "admin", "editor")
    assert not await user.has_all_roles(db, "admin", "editor", "viewer")


async def test_has_exact_roles(db, user):
    await Role.create(db, "admin")
    await Role.create(db, "editor")
    await user.assign_role(db, "admin", "editor")
    assert await user.has_exact_roles(db, "admin", "editor")
    assert not await user.has_exact_roles(db, "admin")


async def test_get_role_names(db, user):
    await Role.create(db, "admin")
    await Role.create(db, "viewer")
    await user.assign_role(db, "admin", "viewer")
    names = await user.get_role_names(db)
    assert set(names) == {"admin", "viewer"}


# ------------------------------------------------------------------ #
# Direct permissions                                                   #
# ------------------------------------------------------------------ #

async def test_give_direct_permission(db, user):
    await Permission.create(db, "special.access")
    await user.give_permission_to(db, "special.access")
    assert await user.has_direct_permission(db, "special.access")


async def test_give_direct_permission_object(db, user):
    perm = await Permission.create(db, "perm.obj")
    await user.give_permission_to(db, perm)
    assert await user.has_direct_permission(db, perm)


async def test_give_direct_permission_idempotent(db, user):
    await Permission.create(db, "dup.perm")
    await user.give_permission_to(db, "dup.perm")
    await user.give_permission_to(db, "dup.perm")
    direct = await user.get_direct_permissions(db)
    assert sum(1 for p in direct if p.name == "dup.perm") == 1


async def test_revoke_direct_permission(db, user):
    await Permission.create(db, "posts.delete")
    await user.give_permission_to(db, "posts.delete")
    await user.revoke_permission_to(db, "posts.delete")
    assert not await user.has_direct_permission(db, "posts.delete")


async def test_sync_permissions(db, user):
    await Permission.create(db, "read")
    await Permission.create(db, "write")
    await Permission.create(db, "delete")
    await user.give_permission_to(db, "read", "write", "delete")
    await user.sync_permissions(db, ["read"])
    direct = await user.get_direct_permissions(db)
    names = {p.name for p in direct}
    assert names == {"read"}


# ------------------------------------------------------------------ #
# Permission checks: direct vs via role                               #
# ------------------------------------------------------------------ #

async def test_has_permission_via_role(db, user):
    perm = await Permission.create(db, "articles.edit")
    role = await Role.create(db, "editor")
    await role.give_permission_to(db, "articles.edit")
    await user.assign_role(db, "editor")
    assert await user.has_permission_to(db, "articles.edit")
    assert not await user.has_direct_permission(db, "articles.edit")
    assert await user.has_permission_via_role(db, "articles.edit")


async def test_has_permission_direct_not_via_role(db, user):
    await Permission.create(db, "special")
    await user.give_permission_to(db, "special")
    assert await user.has_direct_permission(db, "special")
    assert not await user.has_permission_via_role(db, "special")


async def test_check_permission_to_silent_false(db, user):
    result = await user.check_permission_to(db, "nonexistent.perm")
    assert result is False


async def test_has_any_permission(db, user):
    await Permission.create(db, "p.a")
    await Permission.create(db, "p.b")
    await user.give_permission_to(db, "p.b")
    assert await user.has_any_permission(db, "p.a", "p.b")
    assert not await user.has_any_permission(db, "p.a")


async def test_has_all_permissions(db, user):
    await Permission.create(db, "x")
    await Permission.create(db, "y")
    await user.give_permission_to(db, "x", "y")
    assert await user.has_all_permissions(db, "x", "y")
    assert not await user.has_all_permissions(db, "x", "y", "z")


# ------------------------------------------------------------------ #
# Getters                                                             #
# ------------------------------------------------------------------ #

async def test_get_direct_permissions(db, user):
    await Permission.create(db, "d1")
    await Permission.create(db, "d2")
    await user.give_permission_to(db, "d1", "d2")
    direct = await user.get_direct_permissions(db)
    assert {p.name for p in direct} == {"d1", "d2"}


async def test_get_permissions_via_roles(db, user):
    await Permission.create(db, "r1")
    await Permission.create(db, "r2")
    role = await Role.create(db, "testrole")
    await role.give_permission_to(db, "r1", "r2")
    await user.assign_role(db, "testrole")
    via = await user.get_permissions_via_roles(db)
    assert {p.name for p in via} == {"r1", "r2"}


async def test_get_all_permissions_combined(db, user):
    await Permission.create(db, "direct.perm")
    await Permission.create(db, "role.perm")
    role = await Role.create(db, "combo")
    await role.give_permission_to(db, "role.perm")
    await user.assign_role(db, "combo")
    await user.give_permission_to(db, "direct.perm")
    all_perms = await user.get_all_permissions(db)
    names = {p.name for p in all_perms}
    assert "direct.perm" in names
    assert "role.perm" in names


async def test_get_permission_names(db, user):
    await Permission.create(db, "n1")
    await Permission.create(db, "n2")
    await user.give_permission_to(db, "n1", "n2")
    names = await user.get_permission_names(db)
    assert set(names) == {"n1", "n2"}


async def test_no_duplicate_in_get_all_permissions(db, user):
    perm = await Permission.create(db, "shared")
    role = await Role.create(db, "sharer")
    await role.give_permission_to(db, "shared")
    await user.assign_role(db, "sharer")
    await user.give_permission_to(db, "shared")
    all_perms = await user.get_all_permissions(db)
    assert sum(1 for p in all_perms if p.name == "shared") == 1


# ------------------------------------------------------------------ #
# Multiple users isolation                                            #
# ------------------------------------------------------------------ #

async def test_roles_isolated_between_users(db, user, user2):
    await Role.create(db, "admin")
    await user.assign_role(db, "admin")
    assert await user.has_role(db, "admin")
    assert not await user2.has_role(db, "admin")


async def test_permissions_isolated_between_users(db, user, user2):
    await Permission.create(db, "secret")
    await user.give_permission_to(db, "secret")
    assert await user.has_direct_permission(db, "secret")
    assert not await user2.has_direct_permission(db, "secret")
