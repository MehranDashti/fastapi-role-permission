# fastapi-role-permission

RBAC (Role-Based Access Control) for FastAPI, inspired by Laravel's [Spatie Permission](https://github.com/spatie/laravel-permission) package.

- Roles and permissions stored in the database
- Direct permissions **and** role-based permissions
- Redis cache (24h TTL) with in-memory fallback
- Teams / multi-tenancy support
- Wildcard permission patterns (`posts.*`, `*`)
- FastAPI `Depends`-based guards + Starlette middleware
- SQLAlchemy 2.x async

---

## Installation

```bash
pip install fastapi-role-permission
```

**Optional: Redis support** (included by default via the `redis` package).

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

### 4. Protect routes

```python
from fastapi import Depends
from fastapi_role_permission import require_permission, require_role, require_any_role

@app.get("/posts", dependencies=[Depends(require_permission("posts.read"))])
async def list_posts():
    return {"posts": [...]}

@app.post("/posts", dependencies=[Depends(require_permission("posts.write"))])
async def create_post():
    ...

@app.get("/admin", dependencies=[Depends(require_role("admin"))])
async def admin_panel():
    ...

@app.get("/content", dependencies=[Depends(require_any_role("admin", "editor"))])
async def content_area():
    ...
```

---

## Managing Permissions and Roles

```python
from fastapi_role_permission import Permission, Role

# Create permissions
read_posts  = await Permission.find_or_create(db, "posts.read")
write_posts = await Permission.find_or_create(db, "posts.write")
del_posts   = await Permission.find_or_create(db, "posts.delete")

# Create roles
editor = await Role.find_or_create(db, "editor")
admin  = await Role.find_or_create(db, "admin")

# Assign permissions to roles
await editor.give_permission_to(db, "posts.read", "posts.write")
await admin.give_permission_to(db, "posts.read", "posts.write", "posts.delete")

# Assign roles to users
await user.assign_role(db, "editor")

# Assign direct permissions to a user
await user.give_permission_to(db, "posts.delete")

# Check permissions
await user.has_permission_to(db, "posts.read")   # True (via role)
await user.has_permission_to(db, "posts.delete") # True (direct)
await user.has_direct_permission(db, "posts.delete")  # True
await user.has_permission_via_role(db, "posts.read")  # True

# Check roles
await user.has_role(db, "editor")                # True
await user.has_any_role(db, "admin", "editor")   # True
await user.has_all_roles(db, "admin", "editor")  # False
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
)
```

### `Permission` model

```python
# Create
perm = await Permission.create(db, "posts.read", guard_name="default")

# Find
perm = await Permission.find_by_name(db, "posts.read")
perm = await Permission.find_by_id(db, 1)
perm = await Permission.find_or_create(db, "posts.read")
```

### `Role` model

```python
# Create
role = await Role.create(db, "admin", guard_name="default", team_id=None)

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
await user.has_any_direct_permission(db, "posts.read")
await user.has_all_direct_permissions(db, "posts.read", "posts.write")

await user.get_direct_permissions(db)       # [Permission, ...]
await user.get_permissions_via_roles(db)    # [Permission, ...]
await user.get_all_permissions(db)          # combined, deduped
await user.get_permission_names(db)         # ["posts.read", ...]
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

@router.get("/", dependencies=[Depends(require_permission("posts.read"))])
@router.get("/", dependencies=[Depends(require_any_permission("posts.read", "articles.read"))])
@router.get("/", dependencies=[Depends(require_role("admin"))])
@router.get("/", dependencies=[Depends(require_any_role("admin", "editor"))])
@router.get("/", dependencies=[Depends(require_role_or_permission("admin", "posts.delete"))])
```

### Middleware

```python
from fastapi_role_permission import RoleMiddleware, PermissionMiddleware

app.add_middleware(RoleMiddleware, roles="admin")
app.add_middleware(RoleMiddleware, roles="admin|editor", require_all=False)
app.add_middleware(PermissionMiddleware, permissions="posts.read")
app.add_middleware(PermissionMiddleware, permissions="posts.read|posts.write", require_all=False)
app.add_middleware(RoleOrPermissionMiddleware, roles_or_permissions="admin|posts.delete")

# Exclude paths from middleware enforcement
app.add_middleware(RoleMiddleware, roles="admin", exclude_paths=["/health", "/auth"])
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
        # Extract team ID from JWT, header, path, etc.
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

## License

MIT
