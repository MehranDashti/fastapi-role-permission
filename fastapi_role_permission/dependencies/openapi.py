"""
OpenAPI annotation helpers.

Usage:
    @router.get(
        "/posts",
        **rbac_summary(permissions=["posts.read"]),
        dependencies=[require_permission("posts.read")],
    )
    async def list_posts(): ...

    @router.delete(
        "/posts/{id}",
        **rbac_summary(roles=["admin"], permissions=["posts.delete"]),
        dependencies=[require_role_or_permission("admin", "posts.delete")],
    )
    async def delete_post(id: int): ...
"""
from __future__ import annotations


def rbac_summary(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> dict:
    """
    Return FastAPI route kwargs that annotate the Swagger UI with RBAC
    requirements. The returned dict is spread into the route decorator.

    Adds a Markdown block to the route description and a ``rbac`` tag.

    Args:
        roles:       Role names required for this route.
        permissions: Permission names required for this route.
    """
    parts: list[str] = []
    if roles:
        parts.append("**Required roles:** " + ", ".join(f"`{r}`" for r in roles))
    if permissions:
        parts.append("**Required permissions:** " + ", ".join(f"`{p}`" for p in permissions))

    description = "\n\n".join(parts) if parts else None
    return {"description": description, "tags": ["rbac"] if parts else []}
