from __future__ import annotations

from typing import Any, Callable, Type

from sqlalchemy import and_
from sqlalchemy.orm import relationship


def setup_relationships(user_model: Type, config: "Any") -> None:
    """
    Dynamically inject .roles and .direct_permissions relationships onto the
    host app's User model. Called once inside init_rbac().

    The relationships are viewonly=True because all writes go through explicit
    INSERT/DELETE SQL in the mixin methods (polymorphic junction tables).
    """
    from .models.role import Role
    from .models.permission import Permission, model_has_roles_table, model_has_permissions_table

    t_roles = model_has_roles_table
    t_perms = model_has_permissions_table
    tablename = user_model.__tablename__

    # Avoid double-injection if init_rbac is called multiple times
    if hasattr(user_model, "roles") and hasattr(user_model.roles, "property"):
        return

    user_model.roles = relationship(
        Role,
        primaryjoin=lambda: and_(
            t_roles.c.model_type == tablename,
            t_roles.c.model_id == user_model.id,
        ),
        secondaryjoin=lambda: t_roles.c.role_id == Role.id,
        secondary=t_roles,
        viewonly=True,
        lazy="selectin",
        overlaps="direct_permissions",
        foreign_keys=[t_roles.c.model_id, t_roles.c.role_id],
    )

    user_model.direct_permissions = relationship(
        Permission,
        primaryjoin=lambda: and_(
            t_perms.c.model_type == tablename,
            t_perms.c.model_id == user_model.id,
        ),
        secondaryjoin=lambda: t_perms.c.permission_id == Permission.id,
        secondary=t_perms,
        viewonly=True,
        lazy="selectin",
        overlaps="roles",
        foreign_keys=[t_perms.c.model_id, t_perms.c.permission_id],
    )


def init_rbac(
    app: Any,
    get_db: Callable,
    get_current_user: Callable,
    *,
    user_model: Type,
    redis_url: str | None = None,
    config: "Any | None" = None,
) -> "Any":
    """
    Initialize fastapi-role-permission. Call once during app startup.

    Args:
        app:              FastAPI application instance.
        get_db:           Async generator dependency that yields AsyncSession.
        get_current_user: FastAPI dependency that returns the current user model instance.
        user_model:       The SQLAlchemy model class that inherits HasRoles.
        redis_url:        Redis connection URL. If None, uses in-memory cache.
        config:           Optional PermissionConfig for custom settings.

    Returns:
        PermissionRegistrar instance (also stored on app.state.rbac).

    Example:
        init_rbac(
            app,
            get_db=get_db,
            get_current_user=get_current_user,
            user_model=User,
            redis_url="redis://localhost:6379/0",
            config=PermissionConfig(teams_enabled=True),
        )
    """
    from .config import PermissionConfig
    from .cache.redis_cache import RedisCache
    from .cache.memory_cache import InMemoryCache
    from .registrar import PermissionRegistrar
    from . import _state

    cfg: PermissionConfig = config or PermissionConfig()

    cache = RedisCache(redis_url) if redis_url else InMemoryCache()
    registrar = PermissionRegistrar(config=cfg, cache=cache)

    # Store in module-level state for model methods and dependencies
    _state.set_config(cfg)
    _state.set_registrar(registrar)
    _state.set_get_current_user(get_current_user)
    _state.set_get_db(get_db)

    # Inject relationships onto the user model
    setup_relationships(user_model, cfg)

    # Store on FastAPI app state for middleware access
    app.state.rbac = registrar
    app.state.rbac_config = cfg
    app.state.rbac_get_db = get_db
    app.state.rbac_get_current_user = get_current_user

    return registrar
