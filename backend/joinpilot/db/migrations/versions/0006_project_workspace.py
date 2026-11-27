"""The workspace each project belongs to (D-037).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing projects were made without workspaces, so they join the local one.
    op.add_column(
        "projects",
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="local"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_column("projects", "workspace_id")
