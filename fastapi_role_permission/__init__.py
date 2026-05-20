"""
fastapi-role-permission
=======================
RBAC for FastAPI inspired by Laravel Spatie Permission.

Quick start:
    from fastapi_role_permission import init_rbac, HasRoles, Permission, Role, require_permission

    class User(Base, HasRoles):
        __tablename__ = "users"
        ...

    init_rbac(app, get_db=get_db, get_current_user=get_current_user, user_model=User)

    @router.get("/admin", dependencies=[Depends(require_permission("admin.access"))])
    async def admin(): ...
"""

from .setup import init_rbac
from .migrations import create_tables, drop_tables
from .seeders import seed_roles
from .config import PermissionConfig, TableNames
from .models.permission import Permission
from .models.role import Role
from .models.mixins import HasPermissions, HasRoles
from .models.base import RBACBase
from .registrar import PermissionRegistrar
from .wildcard import WildcardPermission
from .exceptions import (
    PermissionDoesNotExist,
    PermissionAlreadyExists,
    RoleDoesNotExist,
    RoleAlreadyExists,
    GuardDoesNotMatch,
    UnauthorizedException,
)
from .dependencies.checks import (
    require_permission,
    require_any_permission,
    require_role,
    require_any_role,
    require_role_or_permission,
)
from .dependencies.openapi import rbac_summary
from .middleware.role import RoleMiddleware
from .middleware.permission import PermissionMiddleware
from .middleware.role_or_permission import RoleOrPermissionMiddleware

__version__ = "0.1.0"

__all__ = [
    # Setup
    "init_rbac",
    "create_tables",
    "drop_tables",
    "seed_roles",
    "PermissionConfig",
    "TableNames",
    # Models
    "Permission",
    "Role",
    # Mixins
    "HasPermissions",
    "HasRoles",
    # Base
    "RBACBase",
    # Core
    "PermissionRegistrar",
    "WildcardPermission",
    # Depends-based guards
    "require_permission",
    "require_any_permission",
    "require_role",
    "require_any_role",
    "require_role_or_permission",
    "rbac_summary",
    # Middleware
    "RoleMiddleware",
    "PermissionMiddleware",
    "RoleOrPermissionMiddleware",
    # Exceptions
    "PermissionDoesNotExist",
    "PermissionAlreadyExists",
    "RoleDoesNotExist",
    "RoleAlreadyExists",
    "GuardDoesNotMatch",
    "UnauthorizedException",
]
