"""
Module-level mutable state for the package.
Set once during init_rbac(); read by models, mixins, and dependencies.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .config import PermissionConfig
    from .registrar import PermissionRegistrar

_config: "PermissionConfig | None" = None
_registrar: "PermissionRegistrar | None" = None
_get_current_user: Callable[..., Any] | None = None
_get_db: Callable[..., Any] | None = None


def set_config(c: "PermissionConfig") -> None:
    global _config
    _config = c


def get_config() -> "PermissionConfig":
    if _config is None:
        raise RuntimeError(
            "fastapi-role-permission is not initialized. Call init_rbac() first."
        )
    return _config


def set_registrar(r: "PermissionRegistrar") -> None:
    global _registrar
    _registrar = r


def get_registrar() -> "PermissionRegistrar":
    if _registrar is None:
        raise RuntimeError(
            "fastapi-role-permission is not initialized. Call init_rbac() first."
        )
    return _registrar


def set_get_current_user(fn: Callable[..., Any]) -> None:
    global _get_current_user
    _get_current_user = fn


def get_get_current_user() -> Callable[..., Any]:
    if _get_current_user is None:
        raise RuntimeError(
            "fastapi-role-permission is not initialized. Call init_rbac() first."
        )
    return _get_current_user


def set_get_db(fn: Callable[..., Any]) -> None:
    global _get_db
    _get_db = fn


def get_get_db() -> Callable[..., Any]:
    if _get_db is None:
        raise RuntimeError(
            "fastapi-role-permission is not initialized. Call init_rbac() first."
        )
    return _get_db


def reset() -> None:
    """Reset all state — useful for testing."""
    global _config, _registrar, _get_current_user, _get_db
    _config = None
    _registrar = None
    _get_current_user = None
    _get_db = None
