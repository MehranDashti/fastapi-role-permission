"""
Minimal FastAPI app demonstrating fastapi-role-permission.

Run:
    pip install fastapi-role-permission[dev] uvicorn
    uvicorn examples.basic_app.main:app --reload

Then:
    curl http://localhost:8000/seed        # seed roles/permissions
    curl http://localhost:8000/me          # get current user info
    curl http://localhost:8000/admin       # 403 (no admin role)
    curl http://localhost:8000/posts       # 200 (viewer has posts.read)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastapi_role_permission import (
    HasRoles,
    Permission,
    PermissionConfig,
    Role,
    init_rbac,
    require_permission,
    require_role,
    seed_roles,
)
from fastapi_role_permission.models.base import RBACBase

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

DATABASE_URL = "sqlite+aiosqlite:///./example.db"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class User(Base, HasRoles):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


# ---------------------------------------------------------------------------
# Auth stub — replace with your JWT / session logic
# ---------------------------------------------------------------------------

_DEMO_USER_ID = 1


async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, _DEMO_USER_ID)
    if user is None:
        user = User(id=_DEMO_USER_ID, name="demo")
        db.add(user)
        await db.flush()
        await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# App lifespan: create tables, seed roles
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(RBACBase.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="fastapi-role-permission example", lifespan=lifespan)

init_rbac(
    app,
    get_db=get_db,
    get_current_user=get_current_user,
    user_model=User,
    config=PermissionConfig(wildcard_enabled=True),
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)):
    """Bootstrap roles and permissions. Safe to call multiple times."""
    await seed_roles(db, {
        "admin":  ["*"],
        "editor": ["posts.read", "posts.write"],
        "viewer": ["posts.read"],
    })
    return {"seeded": True}


@app.post("/assign/{role_name}")
async def assign_role(
    role_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign a role to the demo user."""
    await user.assign_role(db, role_name)
    return {"assigned": role_name, "user": user.name}


@app.get("/me")
async def me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {
        "user": user.name,
        "roles": await user.get_role_names(db),
        "permissions": await user.get_permission_names(db),
    }


@app.get("/admin", dependencies=[require_role("admin")])
async def admin_only():
    return {"message": "Welcome, admin!"}


@app.get("/posts", dependencies=[require_permission("posts.read")])
async def list_posts():
    return {"posts": ["Hello World", "FastAPI RBAC"]}


@app.get("/posts/write", dependencies=[require_permission("posts.write")])
async def write_post():
    return {"message": "Post created."}
