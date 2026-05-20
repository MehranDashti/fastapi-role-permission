from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RoleMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces role requirements on all routes.
    Prefer FastAPI Depends(require_role(...)) for route-level control.
    Use this middleware for app-wide or prefix-wide enforcement.

    Usage:
        app.add_middleware(RoleMiddleware, roles="admin")
        app.add_middleware(RoleMiddleware, roles="admin|editor", require_all=False)
    """

    def __init__(
        self,
        app,
        roles: str,
        require_all: bool = False,
        exclude_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.roles = [r.strip() for r in roles.split("|")]
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
                    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
                check = user.has_all_roles if self.require_all else user.has_any_role
                if not await check(db, *self.roles):
                    return JSONResponse({"detail": "Insufficient role."}, status_code=403)
                break
        except Exception:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
