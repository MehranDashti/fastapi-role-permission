# fastapi-role-permission

[![Tests](https://github.com/MehranDashti/fastapi-role-permission/actions/workflows/tests.yml/badge.svg)](https://github.com/MehranDashti/fastapi-role-permission/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/fastapi-role-permission.svg)](https://pypi.org/project/fastapi-role-permission/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-role-permission.svg)](https://pypi.org/project/fastapi-role-permission/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RBAC (Role-Based Access Control) for FastAPI, inspired by Laravel's [Spatie Permission](https://github.com/spatie/laravel-permission) package.

- Roles and permissions stored in the database
- Direct permissions **and** role-based permissions
- Redis cache (24h TTL) with in-memory fallback
- Teams / multi-tenancy support
- Wildcard permission patterns (`posts.*`, `*`)
- FastAPI `Depends`-based guards + Starlette middleware
- SQLAlchemy 2.x async
- Audit logging (optional, zero new dependencies)

---

## Installation

```bash
pip install fastapi-role-permission
```

**With Redis cache:**

```bash
pip install fastapi-role-permission[redis]
```

Without Redis the package automatically falls back to an in-memory cache (suitable for single-process apps and development).

---

## Migrations

After installing the package you need to create **5 RBAC tables** in your database:

| Table | Purpose |
|-------|---------|
| `permissions` | Stores every permission definition |
| `roles` | Stores every role definition |
| `role_has_permissions` | Which permissions belong to a role |
| `model_has_roles` | Which roles are assigned to a user |
| `model_has_permissions` | Direct permissions assigned to a user |

Pick the approach that matches your project setup:

---

### Approach 1 — CLI (quickest, no Alembic needed)

```bash
# PostgreSQL
fastapi-rbac create-tables --url postgresql+asyncpg://user:pass@localhost/mydb

# MySQL
fastapi-rbac create-tables --url mysql+aiomysql://user:pass@localhost/mydb

# SQLite (development)
fastapi-rbac create-tables --url sqlite+aiosqlite:///./dev.db
```

> `create-tables` uses SQLAlchemy's `create_all` — it is **idempotent** and will not drop or alter existing tables.

---

### Approach 2 — Alembic migration (recommended for production)

**Step 1 — Copy the migration stub into your project:**

```bash
fastapi-rbac init-migrations --directory migrations/versions
```

This creates `migrations/versions/create_rbac_tables.py` with a complete `upgrade()` and `downgrade()` already written.

**Step 2 — If you have an existing Alembic project**, open the copied file and set `down_revision` to your current latest revision:

```python
# migrations/versions/create_rbac_tables.py
revision = "fastapi_rbac_001"
down_revision = "your_latest_revision_id"   # ← set this
```

If this is a fresh project with no previous migrations, leave `down_revision = None`.

**Step 3 — Run the migration:**

```bash
alembic upgrade head
```

**To roll back:**

```bash
alembic downgrade -1
```

---

### Approach 3 — Programmatic (in app lifespan)

Useful when you don't use Alembic and want tables created automatically on startup.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi_role_permission import create_tables, init_rbac

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/mydb"
engine = create_async_engine(DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables(engine)   # creates tables if they don't exist
    yield

app = FastAPI(lifespan=lifespan)
init_rbac(app, get_db=get_db, get_current_user=get_current_user, user_model=User)
```

---

### Approach 4 — Alembic `env.py` (autogenerate)

If you prefer Alembic to detect and generate migrations automatically, add `RBACBase.metadata` to your Alembic environment:

```python
# migrations/env.py
from app.db.base import Base                          # your app's Base
from fastapi_role_permission.models.base import RBACBase  # RBAC Base

target_metadata = [Base.metadata, RBACBase.metadata]  # include both
```

Then generate and run:

```bash
alembic revision --autogenerate -m "add rbac tables"
alembic upgrade head
```

---

### Drop / reset tables (dev only)

```bash
# CLI — prompts for confirmation
fastapi-rbac drop-tables --url sqlite+aiosqlite:///./dev.db

# CLI — skip confirmation
fastapi-rbac drop-tables --url sqlite+aiosqlite:///./dev.db --yes
```

Or programmatically:

```python
from fastapi_role_permission import drop_tables
await drop_tables(engine)
```

---

## Quick Start

### 1. Add `HasRoles` to your User model

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String
from fastapi_role_permission import HasRoles

class Base(DeclarativeBase):
    pass

class User(Base, HasRoles):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    # ... your other fields
```

### 2. Run migrations

See the [Migrations](#migrations) section above for all options. Quickest for development:

```bash
fastapi-rbac create-tables --url sqlite+aiosqlite:///./dev.db
```

### 3. Initialize in your FastAPI app

```python
from fastapi import FastAPI
from fastapi_role_permission import init_rbac, PermissionConfig

app = FastAPI()

init_rbac(
    app,
    get_db=get_db,                    # your async db dependency
    get_current_user=get_current_user, # your auth dependency
    user_model=User,
    redis_url="redis://localhost:6379/0",  # omit for in-memory cache
    config=PermissionConfig(
        teams_enabled=False,
        wildcard_enabled=True,
    ),
)
```

### 4. Seed roles and permissions

```python
from fastapi_role_permission import seed_roles

# Call once at startup or in a migration — safe to call multiple times
await seed_roles(db, {
    "admin":  ["*"],
    "editor": ["posts.read", "posts.write"],
    "viewer": ["posts.read"],
})
```

### 5. Protect routes

```python
from fastapi_role_permission import require_permission, require_role, require_any_role

# require_* already returns a Depends() — no extra wrapping needed
@app.get("/posts", dependencies=[require_permission("posts.read")])
async def list_posts():
    return {"posts": [...]}

@app.post("/posts", dependencies=[require_permission("posts.write")])
async def create_post():
    ...

@app.get("/admin", dependencies=[require_role("admin")])
async def admin_panel():
    ...

@app.get("/content", dependencies=[require_any_role("admin", "editor")])
async def content_area():
    ...
```

---

## Managing Permissions and Roles

```python
from fastapi_role_permission import Permission, Role

# Create permissions (with optional description)
read_posts  = await Permission.find_or_create(db, "posts.read",   description="Read blog posts")
write_posts = await Permission.find_or_create(db, "posts.write",  description="Create/edit blog posts")
del_posts   = await Permission.find_or_create(db, "posts.delete", description="Delete blog posts")

# Create roles (with optional description)
editor = await Role.find_or_create(db, "editor", description="Can read and write posts")
admin  = await Role.find_or_create(db, "admin",  description="Full access")

# Assign permissions to roles
await editor.give_permission_to(db, "posts.read", "posts.write")
await admin.give_permission_to(db, "posts.read", "posts.write", "posts.delete")

# Assign roles to users
await user.assign_role(db, "editor")

# Assign direct permissions to a user
await user.give_permission_to(db, "posts.delete")

# Check permissions
await user.has_permission_to(db, "posts.read")        # True (via role)
await user.has_permission_to(db, "posts.delete")      # True (direct)
await user.has_direct_permission(db, "posts.delete")  # True
await user.has_permission_via_role(db, "posts.read")  # True

# Check roles
await user.has_role(db, "editor")               # True
await user.has_any_role(db, "admin", "editor")  # True
await user.has_all_roles(db, "admin", "editor") # False
```

---

## Full API Reference

### `init_rbac(app, get_db, get_current_user, *, user_model, redis_url=None, config=None)`

Initialize the package. Call once at app startup.

| Param | Type | Description |
|-------|------|-------------|
| `app` | `FastAPI` | Your FastAPI application |
| `get_db` | `Callable` | Async generator dependency yielding `AsyncSession` |
| `get_current_user` | `Callable` | FastAPI dependency returning the current user |
| `user_model` | `Type` | SQLAlchemy model class that inherits `HasRoles` |
| `redis_url` | `str \| None` | Redis URL. `None` = in-memory cache (single process only) |
| `config` | `PermissionConfig \| None` | Optional configuration |

### `PermissionConfig`

```python
PermissionConfig(
    guard_name="default",           # default guard name
    cache_expiration=86400,         # cache TTL in seconds (24h)
    cache_key="fastapi_permission.cache",
    teams_enabled=False,            # enable multi-tenancy
    wildcard_enabled=False,         # enable wildcard patterns
    display_permission_in_exception=False,  # show required perms in 403 detail
    display_role_in_exception=False,        # show required roles in 403 detail
    enable_audit_logging=False,     # log role/permission changes to standard logging
    audit_logger_name="fastapi_rbac.audit", # logger name for audit events
)
```

### `seed_roles(db, config, guard_name=None)`

Bootstrap roles and permissions from a dict. Idempotent — safe to call on every startup.

```python
from fastapi_role_permission import seed_roles

await seed_roles(db, {
    "admin":  ["*"],
    "editor": ["posts.read", "posts.write"],
    "viewer": ["posts.read"],
})
```

### `Permission` model

```python
# Create (description is optional)
perm = await Permission.create(db, "posts.read", description="Read blog posts")

# Find
perm = await Permission.find_by_name(db, "posts.read")
perm = await Permission.find_by_id(db, 1)
perm = await Permission.find_or_create(db, "posts.read")
```

### `Role` model

```python
# Create (description is optional)
role = await Role.create(db, "admin", description="Full access", team_id=None)

# Find
role = await Role.find_by_name(db, "admin")
role = await Role.find_by_id(db, 1)
role = await Role.find_or_create(db, "admin")

# Manage permissions on a role
await role.give_permission_to(db, "posts.read", "posts.write")
await role.revoke_permission_to(db, "posts.write")
await role.sync_permissions(db, ["posts.read"])  # replace all
await role.has_permission_to(db, "posts.read")   # True/False
```

### `HasRoles` / `HasPermissions` mixin methods

**Role management** (available when using `HasRoles`):

```python
await user.assign_role(db, "editor")              # assign one or more roles
await user.assign_role(db, "editor", "viewer")
await user.remove_role(db, "editor")
await user.sync_roles(db, ["admin"])              # replace all roles

await user.has_role(db, "editor")                 # True/False
await user.has_any_role(db, "admin", "editor")    # True if has at least one
await user.has_all_roles(db, "admin", "editor")   # True if has all
await user.has_exact_roles(db, "admin", "editor") # True if has exactly these
await user.get_role_names(db)                     # ["editor"]
```

**Permission management** (available on `HasPermissions` and `HasRoles`):

```python
await user.give_permission_to(db, "posts.delete")
await user.revoke_permission_to(db, "posts.delete")
await user.sync_permissions(db, ["posts.read"])   # replace all direct perms

await user.has_permission_to(db, "posts.read")    # True (direct or via role)
await user.check_permission_to(db, "posts.read")  # same, but never throws
await user.has_direct_permission(db, "posts.read")     # True only if direct
await user.has_permission_via_role(db, "posts.read")   # True only if via role
await user.has_any_permission(db, "posts.read", "posts.write")
await user.has_all_permissions(db, "posts.read", "posts.write")

await user.get_direct_permissions(db)       # [Permission, ...]
await user.get_permissions_via_roles(db)    # [Permission, ...]
await user.get_all_permissions(db)          # combined, deduped
await user.get_permission_names(db)         # ["posts.read", ...]
```

**Batch operations** (class methods for bulk assignments):

```python
# Assign one role to many users in a single INSERT
await User.bulk_assign_roles(db, [user1, user2, user3], "viewer")

# Give one permission to many users in a single INSERT
await User.bulk_give_permission_to(db, [user1, user2], "posts.read")
```

### Dependency guards

```python
from fastapi_role_permission import (
    require_permission,       # user must have ALL listed permissions
    require_any_permission,   # user must have at least ONE permission
    require_role,             # user must have ALL listed roles
    require_any_role,         # user must have at least ONE role
    require_role_or_permission,  # user must have a role OR permission from the list
)

# Each function already returns a Depends() — use directly in dependencies=[]
@router.get("/", dependencies=[require_permission("posts.read")])
@router.get("/", dependencies=[require_any_permission("posts.read", "articles.read")])
@router.get("/", dependencies=[require_role("admin")])
@router.get("/", dependencies=[require_any_role("admin", "editor")])
@router.get("/", dependencies=[require_role_or_permission("admin", "posts.delete")])
```

### Middleware

```python
from fastapi_role_permission import RoleMiddleware, PermissionMiddleware, RoleOrPermissionMiddleware

app.add_middleware(RoleMiddleware, roles="admin")
app.add_middleware(RoleMiddleware, roles="admin|editor", require_all=False)
app.add_middleware(PermissionMiddleware, permissions="posts.read")
app.add_middleware(PermissionMiddleware, permissions="posts.read|posts.write", require_all=False)
app.add_middleware(RoleOrPermissionMiddleware, roles_or_permissions="admin|posts.delete")

# Exclude paths from middleware enforcement
app.add_middleware(RoleMiddleware, roles="admin", exclude_paths=["/health", "/auth"])
```

### OpenAPI / Swagger annotation

```python
from fastapi_role_permission import rbac_summary, require_permission

@router.get(
    "/posts",
    **rbac_summary(permissions=["posts.read"]),
    dependencies=[require_permission("posts.read")],
)
async def list_posts():
    ...

@router.delete(
    "/posts/{id}",
    **rbac_summary(roles=["admin"], permissions=["posts.delete"]),
    dependencies=[require_role_or_permission("admin", "posts.delete")],
)
async def delete_post(id: int):
    ...
```

---

## Teams / Multi-tenancy

Enable teams in config:

```python
init_rbac(app, ..., config=PermissionConfig(teams_enabled=True))
```

Set the team context per-request in a middleware:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class TeamMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        team_id = request.headers.get("X-Team-ID")
        request.app.state.rbac.set_team_id(int(team_id) if team_id else None)
        return await call_next(request)

app.add_middleware(TeamMiddleware)
```

Use team-scoped operations:

```python
# Assign role to user for team 5
await user.assign_role(db, "manager", team_id=5)
await user.has_role(db, "manager", team_id=5)  # True
await user.has_role(db, "manager", team_id=6)  # False

# Give direct permission scoped to a team
await user.give_permission_to(db, "invoices.approve", team_id=5)
```

---

## Wildcard Permissions

Enable in config:

```python
init_rbac(app, ..., config=PermissionConfig(wildcard_enabled=True))
```

Patterns supported:

```python
# * matches everything
await user.give_permission_to(db, "*")
await user.has_permission_to(db, "anything.at.all")  # True

# namespace.* matches all permissions in that namespace
await user.give_permission_to(db, "posts.*")
await user.has_permission_to(db, "posts.read")    # True
await user.has_permission_to(db, "posts.write")   # True
await user.has_permission_to(db, "articles.read") # False

# Deep matching
await user.give_permission_to(db, "posts.*")
await user.has_permission_to(db, "posts.comments.read")  # True
```

---

## Audit Logging

Enable structured audit logs via Python's standard `logging` module — no new dependencies:

```python
import logging
logging.basicConfig(level=logging.INFO)

init_rbac(app, ..., config=PermissionConfig(
    enable_audit_logging=True,
    audit_logger_name="fastapi_rbac.audit",  # default
))
```

Each role/permission mutation logs a JSON line:

```json
{"action": "assign_role",      "subject": "admin",      "model_type": "users", "model_id": 1}
{"action": "remove_role",      "subject": "editor",     "model_type": "users", "model_id": 1}
{"action": "give_permission",  "subject": "posts.read", "model_type": "users", "model_id": 1}
{"action": "revoke_permission","subject": "posts.read", "model_type": "users", "model_id": 1}
```

---

## Cache Management

```python
# Access the registrar
registrar = app.state.rbac

# Manually invalidate cache (e.g. after bulk operations)
await registrar.forget_cached_permissions()

# Reload from database
await registrar.reload_permissions(db)
```

Permissions are automatically re-cached after `forget_cached_permissions()` is called on the next request. Creating/updating/deleting permissions or roles automatically busts the cache.

---

## Exceptions

```python
from fastapi_role_permission import (
    PermissionDoesNotExist,  # raised by find_by_name / find_by_id
    PermissionAlreadyExists, # raised by create() if duplicate
    RoleDoesNotExist,
    RoleAlreadyExists,
    GuardDoesNotMatch,
    UnauthorizedException,
)
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT
