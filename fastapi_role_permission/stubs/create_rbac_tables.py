"""
Alembic migration: create RBAC tables for fastapi-role-permission.

HOW TO USE
----------
1. Copy this file into your project's migrations/versions/ directory:

       fastapi-rbac init-migrations --directory migrations/versions

2. If you use custom table names, edit the table name constants below.

3. Run the migration:

       alembic upgrade head

To undo:

       alembic downgrade <previous_revision>
"""

from alembic import op
import sqlalchemy as sa

# ------------------------------------------------------------------ #
# Revision identifiers — change if you need to chain this migration   #
# ------------------------------------------------------------------ #
revision = "fastapi_rbac_001"
down_revision = None  # set to your latest revision if adding to existing project
branch_labels = None
depends_on = None

# ------------------------------------------------------------------ #
# Table names — edit if you use PermissionConfig(table_names=...)     #
# ------------------------------------------------------------------ #
PERMISSIONS_TABLE = "permissions"
ROLES_TABLE = "roles"
ROLE_HAS_PERMISSIONS_TABLE = "role_has_permissions"
MODEL_HAS_PERMISSIONS_TABLE = "model_has_permissions"
MODEL_HAS_ROLES_TABLE = "model_has_roles"


def upgrade() -> None:
    # 1. permissions
    op.create_table(
        PERMISSIONS_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(125), nullable=False),
        sa.Column("guard_name", sa.String(125), nullable=False, server_default="default"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("name", "guard_name", name="uq_permissions_name_guard"),
    )

    # 2. roles
    op.create_table(
        ROLES_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(125), nullable=False),
        sa.Column("guard_name", sa.String(125), nullable=False, server_default="default"),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("name", "guard_name", name="uq_roles_name_guard"),
    )
    op.create_index("ix_roles_team_id", ROLES_TABLE, ["team_id"])

    # 3. role_has_permissions
    op.create_table(
        ROLE_HAS_PERMISSIONS_TABLE,
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey(f"{PERMISSIONS_TABLE}.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey(f"{ROLES_TABLE}.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )

    # 4. model_has_permissions
    op.create_table(
        MODEL_HAS_PERMISSIONS_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey(f"{PERMISSIONS_TABLE}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_type", sa.String(125), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_model_has_permissions_model",
        MODEL_HAS_PERMISSIONS_TABLE,
        ["model_type", "model_id"],
    )
    op.create_index(
        "ix_model_has_permissions_team",
        MODEL_HAS_PERMISSIONS_TABLE,
        ["team_id"],
    )

    # 5. model_has_roles
    op.create_table(
        MODEL_HAS_ROLES_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey(f"{ROLES_TABLE}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_type", sa.String(125), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_model_has_roles_model",
        MODEL_HAS_ROLES_TABLE,
        ["model_type", "model_id"],
    )
    op.create_index(
        "ix_model_has_roles_team",
        MODEL_HAS_ROLES_TABLE,
        ["team_id"],
    )


def downgrade() -> None:
    op.drop_table(MODEL_HAS_ROLES_TABLE)
    op.drop_table(MODEL_HAS_PERMISSIONS_TABLE)
    op.drop_table(ROLE_HAS_PERMISSIONS_TABLE)
    op.drop_table(ROLES_TABLE)
    op.drop_table(PERMISSIONS_TABLE)
