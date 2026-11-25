"""Glossary terms with pgvector embeddings.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("column_ref", sa.String(130), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("embedding", sa.JSON().with_variant(Vector(256), "postgresql"), nullable=False),
    )
    op.create_index("ix_glossary_terms_project_id", "glossary_terms", ["project_id"])


def downgrade() -> None:
    op.drop_table("glossary_terms")
