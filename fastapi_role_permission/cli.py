"""
fastapi-rbac CLI — migration helpers for fastapi-role-permission.

Commands:
  fastapi-rbac init-migrations [--directory PATH]
      Copy the Alembic migration stub into your project.

  fastapi-rbac create-tables --url DATABASE_URL
      Create all RBAC tables directly (no Alembic needed).

  fastapi-rbac drop-tables --url DATABASE_URL
      Drop all RBAC tables (dev / test resets).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.resources
import shutil
import sys
from pathlib import Path


def _get_stub_path() -> Path:
    pkg = importlib.resources.files("fastapi_role_permission") / "stubs" / "create_rbac_tables.py"
    # files() returns a Traversable; materialize to a real path for shutil.copy
    with importlib.resources.as_file(pkg) as p:
        return p


def cmd_init_migrations(args: argparse.Namespace) -> None:
    target_dir = Path(args.directory).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    stub_path = _get_stub_path()
    dest = target_dir / "create_rbac_tables.py"

    shutil.copy(stub_path, dest)
    print(f"Migration stub copied to: {dest}")
    print()
    print("Next steps:")
    print("  1. Open the file and set down_revision to your latest revision (if any).")
    print("  2. Run:  alembic upgrade head")


def cmd_create_tables(args: argparse.Namespace) -> None:
    async def _run() -> None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from .migrations import create_tables

        engine = create_async_engine(args.url, echo=args.verbose)
        try:
            await create_tables(engine)
            print("RBAC tables created successfully.")
        finally:
            await engine.dispose()

    asyncio.run(_run())


def cmd_drop_tables(args: argparse.Namespace) -> None:
    confirm = getattr(args, "yes", False)
    if not confirm:
        answer = input("This will DROP all RBAC tables. Type 'yes' to confirm: ")
        if answer.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    async def _run() -> None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from .migrations import drop_tables

        engine = create_async_engine(args.url, echo=args.verbose)
        try:
            await drop_tables(engine)
            print("RBAC tables dropped successfully.")
        finally:
            await engine.dispose()

    asyncio.run(_run())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fastapi-rbac",
        description="fastapi-role-permission migration helper",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (fastapi-role-permission)",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # init-migrations
    p_init = sub.add_parser(
        "init-migrations",
        help="Copy the Alembic migration stub into your project.",
    )
    p_init.add_argument(
        "--directory",
        default="migrations/versions",
        metavar="PATH",
        help="Target directory (default: migrations/versions)",
    )
    p_init.set_defaults(func=cmd_init_migrations)

    # create-tables
    p_create = sub.add_parser(
        "create-tables",
        help="Create all RBAC tables directly (no Alembic needed).",
    )
    p_create.add_argument(
        "--url",
        required=True,
        metavar="DATABASE_URL",
        help="Async SQLAlchemy database URL (e.g. postgresql+asyncpg://user:pass@host/db)",
    )
    p_create.add_argument("--verbose", action="store_true", help="Echo SQL statements")
    p_create.set_defaults(func=cmd_create_tables)

    # drop-tables
    p_drop = sub.add_parser(
        "drop-tables",
        help="Drop all RBAC tables (dev/test resets).",
    )
    p_drop.add_argument(
        "--url",
        required=True,
        metavar="DATABASE_URL",
        help="Async SQLAlchemy database URL",
    )
    p_drop.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt",
    )
    p_drop.add_argument("--verbose", action="store_true", help="Echo SQL statements")
    p_drop.set_defaults(func=cmd_drop_tables)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
