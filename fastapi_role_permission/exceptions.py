from __future__ import annotations


class PermissionDoesNotExist(ValueError):
    @classmethod
    def create(cls, permission: str, guard_name: str) -> "PermissionDoesNotExist":
        return cls(f"Permission `{permission}` does not exist for guard `{guard_name}`.")

    @classmethod
    def with_id(cls, id: int, guard_name: str) -> "PermissionDoesNotExist":
        return cls(f"Permission with id `{id}` does not exist for guard `{guard_name}`.")


class PermissionAlreadyExists(ValueError):
    @classmethod
    def create(cls, permission: str, guard_name: str) -> "PermissionAlreadyExists":
        return cls(f"Permission `{permission}` already exists for guard `{guard_name}`.")


class RoleDoesNotExist(ValueError):
    @classmethod
    def create(cls, role: str, guard_name: str) -> "RoleDoesNotExist":
        return cls(f"Role `{role}` does not exist for guard `{guard_name}`.")

    @classmethod
    def with_id(cls, id: int, guard_name: str) -> "RoleDoesNotExist":
        return cls(f"Role with id `{id}` does not exist for guard `{guard_name}`.")


class RoleAlreadyExists(ValueError):
    @classmethod
    def create(cls, role: str, guard_name: str) -> "RoleAlreadyExists":
        return cls(f"Role `{role}` already exists for guard `{guard_name}`.")


class GuardDoesNotMatch(ValueError):
    @classmethod
    def create(cls, expected: str, given: str) -> "GuardDoesNotMatch":
        return cls(f"Guard `{given}` does not match expected guard `{expected}`.")


class UnauthorizedException(Exception):
    def __init__(
        self,
        message: str,
        required_roles: list[str] | None = None,
        required_permissions: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.required_roles = required_roles or []
        self.required_permissions = required_permissions or []

    @classmethod
    def for_roles(cls, roles: list[str]) -> "UnauthorizedException":
        return cls(
            f"User does not have the right roles. Necessary roles are: {', '.join(roles)}",
            required_roles=roles,
        )

    @classmethod
    def for_permissions(cls, permissions: list[str]) -> "UnauthorizedException":
        return cls(
            f"User does not have the right permissions. Necessary permissions are: {', '.join(permissions)}",
            required_permissions=permissions,
        )

    @classmethod
    def for_roles_or_permissions(cls, values: list[str]) -> "UnauthorizedException":
        return cls(
            f"User does not have any of the required roles or permissions: {', '.join(values)}",
            required_roles=values,
            required_permissions=values,
        )

    @classmethod
    def not_logged_in(cls) -> "UnauthorizedException":
        return cls("User is not logged in.")
