from __future__ import annotations

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RoleOrPermissionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that allows access if the user has any of the specified
    roles OR any of the specified permissions.

    Usage:
        app.add_middleware(
            RoleOrPermissionMiddleware,
            roles_or_permissions="admin|posts.delete"
        )
    """

    def __init__(
        self,
        app,
        roles_or_permissions: str,
        exclude_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.values = [v.strip() for v in roles_or_permissions.split("|")]
        self.exclude_paths = exclude_paths or []

    async def dispatch(self, request: Request, call_next) -> Response:
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        get_db = request.app.state.rbac_get_db
        get_current_user = request.app.state.rbac_get_current_user

        try:
            async for db in get_db():
                user = await get_current_user(db=db)
                if user is None:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

                if await user.has_any_role(db, *self.values):
                    break
                for val in self.values:
                    if await user.check_permission_to(db, val):
                        break
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient roles or permissions.",
                    )
                break
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        return await call_next(request)
