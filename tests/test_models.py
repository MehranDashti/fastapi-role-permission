import pytest
from fastapi_role_permission import Permission, Role
from fastapi_role_permission.exceptions import (
    PermissionAlreadyExists,
    PermissionDoesNotExist,
    RoleAlreadyExists,
    RoleDoesNotExist,
)


# ------------------------------------------------------------------ #
# Permission CRUD                                                      #
# ------------------------------------------------------------------ #

async def test_create_permission(db):
    perm = await Permission.create(db, "posts.read")
    assert perm.id is not None
    assert perm.name == "posts.read"
    assert perm.guard_name == "default"


async def test_create_permission_custom_guard(db):
    perm = await Permission.create(db, "posts.read", guard_name="api")
    assert perm.guard_name == "api"


async def test_create_permission_duplicate_raises(db):
    await Permission.create(db, "posts.read")
    with pytest.raises(PermissionAlreadyExists):
        await Permission.create(db, "posts.read")


async def test_find_by_name(db):
    await Permission.create(db, "posts.write")
    found = await Permission.find_by_name(db, "posts.write")
    assert found.name == "posts.write"


async def test_find_by_name_not_found(db):
    with pytest.raises(PermissionDoesNotExist):
        await Permission.find_by_name(db, "nonexistent")


async def test_find_by_id(db):
    created = await Permission.create(db, "posts.delete")
    found = await Permission.find_by_id(db, created.id)
    assert found.id == created.id


async def test_find_by_id_not_found(db):
    with pytest.raises(PermissionDoesNotExist):
        await Permission.find_by_id(db, 99999)


async def test_find_or_create_creates_new(db):
    perm = await Permission.find_or_create(db, "articles.read")
    assert perm.id is not None


async def test_find_or_create_returns_existing(db):
    p1 = await Permission.create(db, "articles.write")
    p2 = await Permission.find_or_create(db, "articles.write")
    assert p1.id == p2.id


# ------------------------------------------------------------------ #
# Role CRUD                                                            #
# ------------------------------------------------------------------ #

async def test_create_role(db):
    role = await Role.create(db, "admin")
    assert role.id is not None
    assert role.name == "admin"
    assert role.guard_name == "default"
    assert role.team_id is None


async def test_create_role_with_team(db):
    role = await Role.create(db, "manager", team_id=5)
    assert role.team_id == 5


async def test_create_role_duplicate_raises(db):
    await Role.create(db, "editor")
    with pytest.raises(RoleAlreadyExists):
        await Role.create(db, "editor")


async def test_find_role_by_name(db):
    await Role.create(db, "viewer")
    found = await Role.find_by_name(db, "viewer")
    assert found.name == "viewer"


async def test_find_role_by_name_not_found(db):
    with pytest.raises(RoleDoesNotExist):
        await Role.find_by_name(db, "ghost")


async def test_find_role_by_id(db):
    created = await Role.create(db, "moderator")
    found = await Role.find_by_id(db, created.id)
    assert found.id == created.id


async def test_find_role_or_create_creates_new(db):
    role = await Role.find_or_create(db, "superadmin")
    assert role.id is not None


async def test_find_role_or_create_returns_existing(db):
    r1 = await Role.create(db, "staff")
    r2 = await Role.find_or_create(db, "staff")
    assert r1.id == r2.id


# ------------------------------------------------------------------ #
# Role permission management                                           #
# ------------------------------------------------------------------ #

async def test_role_give_permission(db):
    perm = await Permission.create(db, "posts.edit")
    role = await Role.create(db, "editor")
    await role.give_permission_to(db, "posts.edit")
    assert await role.has_permission_to(db, "posts.edit")


async def test_role_give_permission_object(db):
    perm = await Permission.create(db, "posts.publish")
    role = await Role.create(db, "publisher")
    await role.give_permission_to(db, perm)
    assert await role.has_permission_to(db, perm)


async def test_role_give_multiple_permissions(db):
    await Permission.create(db, "p1")
    await Permission.create(db, "p2")
    role = await Role.create(db, "multi")
    await role.give_permission_to(db, "p1", "p2")
    assert await role.has_permission_to(db, "p1")
    assert await role.has_permission_to(db, "p2")


async def test_role_revoke_permission(db):
    await Permission.create(db, "posts.delete")
    role = await Role.create(db, "deleter")
    await role.give_permission_to(db, "posts.delete")
    await role.revoke_permission_to(db, "posts.delete")
    assert not await role.has_permission_to(db, "posts.delete")


async def test_role_sync_permissions(db):
    await Permission.create(db, "read")
    await Permission.create(db, "write")
    await Permission.create(db, "delete")
    role = await Role.create(db, "synced")
    await role.give_permission_to(db, "read", "write", "delete")
    await role.sync_permissions(db, ["read"])
    assert await role.has_permission_to(db, "read")
    assert not await role.has_permission_to(db, "write")
    assert not await role.has_permission_to(db, "delete")
