"""Views and check results of runs.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONValue = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "run_views",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("payload", JSONValue, nullable=False),
        sa.UniqueConstraint("run_id", "name", name="uq_run_views_run_id_name"),
    )
    op.create_index("ix_run_views_run_id", "run_views", ["run_id"])
    op.create_table(
        "check_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("check_id", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("payload", JSONValue, nullable=False),
        sa.UniqueConstraint("run_id", "check_id", name="uq_check_results_run_id_check_id"),
    )
    op.create_index("ix_check_results_run_id", "check_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("check_results")
    op.drop_table("run_views")
