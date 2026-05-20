# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Integration tests for all `require_*` FastAPI dependencies and `*Middleware` classes (200/403/401)
- `seed_roles()` utility to bootstrap roles and permissions from a config dict
- Audit logging support: `enable_audit_logging` and `audit_logger_name` fields on `PermissionConfig`
- `py.typed` marker for PEP 561 compliance (IDE autocomplete and mypy support)
- GitHub Actions CI workflow: tests on Python 3.10/3.11/3.12 with coverage upload
- GitHub Actions publish workflow: automatic PyPI release on version tag
- Pre-commit configuration with ruff and mypy hooks
- Composite database indexes on `(model_type, model_id)` and `team_id` for junction tables
- N+1 query fix: `_get_roles_from_db` now eagerly loads `Role.permissions` via `selectinload`
- Example FastAPI application in `examples/basic_app/main.py`
- Batch operations: `bulk_assign_roles()` and `bulk_give_permission_to()` in mixins
- Optional `description` field on `Permission` and `Role` models

### Changed
- Redis moved from hard dependency to optional (`pip install fastapi-role-permission[redis]`)
- Middleware (`RoleMiddleware`, `PermissionMiddleware`, `RoleOrPermissionMiddleware`) now
  return `JSONResponse` instead of raising `HTTPException` for compatibility with Starlette 1.0

## [0.1.0] - 2026-05-20

### Added
- Initial release
- `HasRoles` and `HasPermissions` mixins for SQLAlchemy models
- `Permission` and `Role` models with async CRUD classmethods
- `init_rbac()` — one-call setup that wires FastAPI app, database, and user model
- `require_permission`, `require_any_permission`, `require_role`, `require_any_role`,
  `require_role_or_permission` FastAPI dependency factories
- `RoleMiddleware`, `PermissionMiddleware`, `RoleOrPermissionMiddleware` Starlette middleware
- Teams/multi-tenancy support via `teams_enabled` config and per-request `ContextVar`
- Wildcard permission patterns (`posts.*`, `*`) via `WildcardPermission`
- Redis cache (`redis.asyncio`) with `InMemoryCache` fallback
- `PermissionRegistrar` for cache management
- `create_tables()` / `drop_tables()` for programmatic table management
- Alembic migration stub via `fastapi-rbac init-migrations`
- `fastapi-rbac` CLI for table creation and migration scaffolding
