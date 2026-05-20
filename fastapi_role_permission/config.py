from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TableNames:
    permissions: str = "permissions"
    roles: str = "roles"
    role_has_permissions: str = "role_has_permissions"
    model_has_roles: str = "model_has_roles"
    model_has_permissions: str = "model_has_permissions"


@dataclass
class PermissionConfig:
    table_names: TableNames = field(default_factory=TableNames)
    guard_name: str = "default"
    cache_expiration: int = 86400  # 24 hours in seconds
    cache_key: str = "fastapi_permission.cache"
    cache_key_prefix: str = ""
    teams_enabled: bool = False
    team_foreign_key: str = "team_id"
    wildcard_enabled: bool = False
    display_permission_in_exception: bool = False
    display_role_in_exception: bool = False

    def get_cache_key(self) -> str:
        if self.cache_key_prefix:
            return f"{self.cache_key_prefix}{self.cache_key}"
        return self.cache_key
