"""Dashboard metrics of runs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONValue = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "run_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("metric_id", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("payload", JSONValue, nullable=False),
        sa.UniqueConstraint("run_id", "metric_id", name="uq_run_metrics_run_id_metric_id"),
    )
    op.create_index("ix_run_metrics_run_id", "run_metrics", ["run_id"])


def downgrade() -> None:
    op.drop_table("run_metrics")
