from __future__ import annotations

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class PermissionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces permission requirements on all routes.
    Prefer FastAPI Depends(require_permission(...)) for route-level control.

    Usage:
        app.add_middleware(PermissionMiddleware, permissions="posts.read")
        app.add_middleware(PermissionMiddleware, permissions="posts.read|posts.write", require_all=False)
    """

    def __init__(
        self,
        app,
        permissions: str,
        require_all: bool = True,
        exclude_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.permissions = [p.strip() for p in permissions.split("|")]
        self.require_all = require_all
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
                if self.require_all:
                    has_perm = await user.has_all_permissions(db, *self.permissions)
                else:
                    has_perm = await user.has_any_permission(db, *self.permissions)
                if not has_perm:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
                break
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        return await call_next(request)
