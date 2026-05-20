import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine

from fastapi_role_permission.migrations import create_tables, drop_tables
from fastapi_role_permission.models.base import RBACBase

EXPECTED_TABLES = {
    "permissions",
    "roles",
    "role_has_permissions",
    "model_has_permissions",
    "model_has_roles",
}


@pytest.fixture
async def fresh_engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield eng
    await eng.dispose()


async def _get_table_names(engine) -> set[str]:
    from sqlalchemy import inspect, text
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    return set(tables)


# ------------------------------------------------------------------ #
# create_tables                                                        #
# ------------------------------------------------------------------ #

async def test_create_tables_creates_all_tables(fresh_engine):
    await create_tables(fresh_engine)
    tables = await _get_table_names(fresh_engine)
    assert EXPECTED_TABLES.issubset(tables), f"Missing tables: {EXPECTED_TABLES - tables}"


async def test_create_tables_idempotent(fresh_engine):
    await create_tables(fresh_engine)
    await create_tables(fresh_engine)  # second call should not raise
    tables = await _get_table_names(fresh_engine)
    assert EXPECTED_TABLES.issubset(tables)


# ------------------------------------------------------------------ #
# drop_tables                                                          #
# ------------------------------------------------------------------ #

async def test_drop_tables_removes_all_tables(fresh_engine):
    await create_tables(fresh_engine)
    await drop_tables(fresh_engine)
    tables = await _get_table_names(fresh_engine)
    for t in EXPECTED_TABLES:
        assert t not in tables, f"Table {t!r} still exists after drop_tables"


async def test_drop_then_recreate(fresh_engine):
    await create_tables(fresh_engine)
    await drop_tables(fresh_engine)
    await create_tables(fresh_engine)  # must succeed cleanly
    tables = await _get_table_names(fresh_engine)
    assert EXPECTED_TABLES.issubset(tables)


# ------------------------------------------------------------------ #
# Alembic stub                                                        #
# ------------------------------------------------------------------ #

def test_stub_file_exists():
    import importlib.resources
    pkg = importlib.resources.files("fastapi_role_permission") / "stubs" / "create_rbac_tables.py"
    with importlib.resources.as_file(pkg) as p:
        assert p.exists(), f"Stub file not found at {p}"


def test_stub_contains_upgrade_and_downgrade():
    import importlib.resources
    pkg = importlib.resources.files("fastapi_role_permission") / "stubs" / "create_rbac_tables.py"
    with importlib.resources.as_file(pkg) as p:
        content = p.read_text()
    assert "def upgrade()" in content
    assert "def downgrade()" in content
    assert "permissions" in content
    assert "roles" in content
    assert "model_has_roles" in content
    assert "model_has_permissions" in content


def test_cli_init_migrations_copies_stub(tmp_path):
    from fastapi_role_permission.cli import cmd_init_migrations
    import argparse

    args = argparse.Namespace(directory=str(tmp_path))
    cmd_init_migrations(args)

    dest = tmp_path / "create_rbac_tables.py"
    assert dest.exists(), "Stub was not copied"
    content = dest.read_text()
    assert "def upgrade()" in content
    assert "def downgrade()" in content
