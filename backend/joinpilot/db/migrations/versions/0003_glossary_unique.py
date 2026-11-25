"""One glossary entry per project column.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM glossary_terms")  # rebuilt on the next search
    with op.batch_alter_table("glossary_terms") as batch:
        batch.create_unique_constraint(
            "uq_glossary_terms_project_id_column_ref", ["project_id", "column_ref"]
        )


def downgrade() -> None:
    with op.batch_alter_table("glossary_terms") as batch:
        batch.drop_constraint("uq_glossary_terms_project_id_column_ref", type_="unique")
