# fastapi-role-permission — Project Memory

## What This Is
A pip-installable Python package (`fastapi-role-permission`) that replicates Laravel Spatie Permission for FastAPI.
- Inspired by: https://github.com/spatie/laravel-permission (source cloned at `/test/laravel-permission`)
- Module name: `fastapi_role_permission`
- Install via: `pip install fastapi-role-permission`

## Stack Decisions (locked in by user)
- **ORM**: SQLAlchemy 2.x async (`Mapped[]`, `mapped_column()`, `AsyncSession`)
- **Cache**: Redis primary (`redis.asyncio`), `InMemoryCache` fallback (no `redis_url`)
- **Teams**: Enabled — permissions/roles can be scoped to a `team_id`
- **Python**: 3.10+
- **Auth**: Auth-agnostic — user passes `get_current_user` dependency to `init_rbac`
- **Packaging**: `pyproject.toml` + setuptools, no `setup.py`

## Package Structure
```
fastapi_role_permission/
├── __init__.py          ← public API (all exports)
├── _state.py            ← module-level mutable state (config, registrar, get_db, get_current_user)
├── config.py            ← PermissionConfig, TableNames dataclasses
├── exceptions.py        ← all custom exceptions
├── wildcard.py          ← WildcardPermission (pattern matching like posts.*)
├── registrar.py         ← PermissionRegistrar (cache manager, team context via ContextVar)
├── setup.py             ← init_rbac() + setup_relationships()
├── models/
│   ├── base.py          ← RBACBase (separate DeclarativeBase for library models)
│   ├── permission.py    ← Permission model + async classmethods
│   ├── role.py          ← Role model + async classmethods + permission methods
│   └── mixins.py        ← HasPermissions, HasRoles mixins (add to user model)
├── cache/
│   ├── base.py          ← BaseCache ABC
│   ├── redis_cache.py   ← RedisCache
│   └── memory_cache.py  ← InMemoryCache (time-based TTL)
├── dependencies/
│   └── checks.py        ← require_permission, require_role, require_any_*, require_role_or_permission
└── middleware/
    ├── role.py           ← RoleMiddleware
    ├── permission.py     ← PermissionMiddleware
    └── role_or_permission.py ← RoleOrPermissionMiddleware
```

## Key Architecture Rules

### 1. Separate DeclarativeBase
`RBACBase` in `models/base.py` is the library's own `DeclarativeBase`. Never use the host app's `Base`. Users must include `RBACBase.metadata` in their `create_all` or Alembic setup.

### 2. Module-level State (`_state.py`)
Config, registrar, `get_db`, and `get_current_user` are stored as module globals in `_state.py`. Set once during `init_rbac`. Safe for single-process FastAPI; documented limitation for multi-worker.

### 3. Teams via ContextVar
`team_id` is per-request state. Use `contextvars.ContextVar` in `registrar.py` — NOT an instance attribute — for async-safe concurrent request handling.

### 4. Polymorphic Junction Tables
`model_has_roles` and `model_has_permissions` use `model_type` (= `__tablename__`) + `model_id` (= pk). No SQLAlchemy polymorphic_on needed. All writes use raw `insert()`/`delete()` SQL. Injected relationships are `viewonly=True`.

### 5. Dynamic Relationship Injection
`setup_relationships(user_model, config)` adds `.roles` and `.direct_permissions` to the user model at startup via `relationship()` with custom `primaryjoin`. Called inside `init_rbac`. Must run before first request.

### 6. Async-first Mixin Methods
All mixin methods (`has_role`, `has_permission_to`, etc.) are `async def` taking `db: AsyncSession` as first arg. They do NOT rely on pre-loaded relationship collections — they always issue explicit queries.

### 7. Cache Invalidation
Any Permission/Role create/update/delete must call `await registrar.forget_cached_permissions()`. The registrar is retrieved from `_state.get_registrar()` inside model methods.

### 8. Guard Name
Defaults to `"default"`. Used to namespace permissions for different user types. All lookups default to the config's `guard_name` unless explicitly passed.

## Database Tables
| Table | Columns |
|-------|---------|
| `permissions` | id, name, guard_name, created_at, updated_at; UNIQUE(name, guard_name) |
| `roles` | id, name, guard_name, team_id (nullable), created_at, updated_at |
| `role_has_permissions` | permission_id FK, role_id FK; PK both; cascade delete |
| `model_has_roles` | role_id FK, model_type str, model_id int, team_id (nullable) |
| `model_has_permissions` | permission_id FK, model_type str, model_id int, team_id (nullable) |

## Public API (from `__init__.py`)
```python
from fastapi_role_permission import (
    init_rbac, PermissionConfig, TableNames,
    Permission, Role, HasPermissions, HasRoles,
    PermissionRegistrar,
    require_permission, require_any_permission,
    require_role, require_any_role, require_role_or_permission,
    RoleMiddleware, PermissionMiddleware, RoleOrPermissionMiddleware,
    WildcardPermission,
    PermissionDoesNotExist, PermissionAlreadyExists,
    RoleDoesNotExist, RoleAlreadyExists,
    GuardDoesNotMatch, UnauthorizedException,
)
```

## Minimal Usage Example
```python
# 1. Add HasRoles to your User model
class User(Base, HasRoles):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)

# 2. Call init_rbac in your app startup
from fastapi_role_permission import init_rbac, PermissionConfig
init_rbac(
    app,
    get_db=get_db,
    get_current_user=get_current_user,
    user_model=User,
    redis_url="redis://localhost:6379/0",
    config=PermissionConfig(teams_enabled=True, wildcard_enabled=True),
)

# 3. Protect routes
@router.get("/admin", dependencies=[Depends(require_permission("admin.access"))])
async def admin(): ...

# 4. Manage permissions
await Permission.find_or_create(db, "posts.read")
await Role.find_or_create(db, "editor")
await role.give_permission_to(db, "posts.read")
await user.assign_role(db, "editor")
await user.has_permission_to(db, "posts.read")  # True
```

## Testing
- Test DB: `sqlite+aiosqlite:///:memory:` (no Redis/MySQL needed)
- Cache: `InMemoryCache` (default when no `redis_url`)
- Framework: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`)
- Run: `pytest tests/`

## Reference
- Spatie source: `/test/laravel-permission/src/`
- Existing FastAPI patterns: `/test/fastapi-rbac/app/` and `/test/fastapi-blueprint/app/`
