from sqlalchemy.orm import DeclarativeBase


class RBACBase(DeclarativeBase):
    """
    Separate DeclarativeBase for all RBAC library models.
    Independent of the host application's Base class.

    Usage in host app:
        from fastapi_role_permission.models.base import RBACBase
        # Include in create_all:
        async with engine.begin() as conn:
            await conn.run_sync(RBACBase.metadata.create_all)
        # Or in Alembic env.py:
        target_metadata = [AppBase.metadata, RBACBase.metadata]
    """
    pass
