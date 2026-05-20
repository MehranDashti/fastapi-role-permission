from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status


def _get_db_dep() -> Callable:
    from .._state import get_get_db
    return get_get_db()


def _get_user_dep() -> Callable:
    from .._state import get_get_current_user
    return get_get_current_user()


def _forbidden(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _build_permission_detail(permissions: tuple[str, ...], missing: str | None = None) -> str:
    from .._state import get_config
    cfg = get_config()
    msg = "User does not have the required permissions."
    if cfg.display_permission_in_exception:
        listed = ", ".join(permissions)
        msg = f"User does not have the required permissions. Required: {listed}."
    return msg


def _build_role_detail(roles: tuple[str, ...]) -> str:
    from .._state import get_config
    cfg = get_config()
    msg = "User does not have the required roles."
    if cfg.display_role_in_exception:
        listed = ", ".join(roles)
        msg = f"User does not have the required roles. Required: {listed}."
    return msg


# ------------------------------------------------------------------ #
# Permission dependencies                                             #
# ------------------------------------------------------------------ #

def require_permission(*permissions: str) -> Any:
    """
    FastAPI dependency — user must have ALL of the specified permissions.

    Usage:
        @router.get("/posts", dependencies=[Depends(require_permission("posts.read"))])
        async def list_posts(): ...
    """
    async def dependency(
        db=Depends(_get_db_dep()),
        current_user=Depends(_get_user_dep()),
    ) -> Any:
        for perm in permissions:
            if not await current_user.check_permission_to(db, perm):
                _forbidden(_build_permission_detail(permissions, perm))
        return current_user

    dependency.__name__ = f"require_permission({'|'.join(permissions)})"
    return Depends(dependency)


def require_any_permission(*permissions: str) -> Any:
    """
    FastAPI dependency — user must have AT LEAST ONE of the specified permissions.
    """
    async def dependency(
        db=Depends(_get_db_dep()),
        current_user=Depends(_get_user_dep()),
    ) -> Any:
        for perm in permissions:
            if await current_user.check_permission_to(db, perm):
                return current_user
        _forbidden(_build_permission_detail(permissions))

    dependency.__name__ = f"require_any_permission({'|'.join(permissions)})"
    return Depends(dependency)


# ------------------------------------------------------------------ #
# Role dependencies                                                   #
# ------------------------------------------------------------------ #

def require_role(*roles: str) -> Any:
    """
    FastAPI dependency — user must have ALL of the specified roles.
    """
    async def dependency(
        db=Depends(_get_db_dep()),
        current_user=Depends(_get_user_dep()),
    ) -> Any:
        if not await current_user.has_all_roles(db, *roles):
            _forbidden(_build_role_detail(roles))
        return current_user

    dependency.__name__ = f"require_role({'|'.join(roles)})"
    return Depends(dependency)


def require_any_role(*roles: str) -> Any:
    """
    FastAPI dependency — user must have AT LEAST ONE of the specified roles.
    """
    async def dependency(
        db=Depends(_get_db_dep()),
        current_user=Depends(_get_user_dep()),
    ) -> Any:
        if not await current_user.has_any_role(db, *roles):
            _forbidden(_build_role_detail(roles))
        return current_user

    dependency.__name__ = f"require_any_role({'|'.join(roles)})"
    return Depends(dependency)


# ------------------------------------------------------------------ #
# Combined role OR permission dependency                              #
# ------------------------------------------------------------------ #

def require_role_or_permission(*roles_or_permissions: str) -> Any:
    """
    FastAPI dependency — user must have at least one of the specified
    roles OR at least one of the specified permissions.

    The same list is checked against both roles and permissions.

    Usage:
        @router.delete("/posts/{id}", dependencies=[
            Depends(require_role_or_permission("admin", "posts.delete"))
        ])
    """
    async def dependency(
        db=Depends(_get_db_dep()),
        current_user=Depends(_get_user_dep()),
    ) -> Any:
        has_role = await current_user.has_any_role(db, *roles_or_permissions)
        if has_role:
            return current_user
        for val in roles_or_permissions:
            if await current_user.check_permission_to(db, val):
                return current_user
        _forbidden(
            f"User does not have any of the required roles or permissions: "
            f"{', '.join(roles_or_permissions)}."
        )

    dependency.__name__ = f"require_role_or_permission({'|'.join(roles_or_permissions)})"
    return Depends(dependency)
