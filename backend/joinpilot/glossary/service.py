"""Build a project's glossary from its profile and search it by business words."""

from __future__ import annotations

import re

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
from sqlalchemy import Float, cast, delete, func, literal, select

from joinpilot.config import Settings
from joinpilot.db.models import EMBEDDING_DIMENSIONS, GlossaryRow
from joinpilot.db.session import ensure_migrated, session_scope
from joinpilot.glossary.embed import cosine, embed
from joinpilot.glossary.hints import FIELD_HINTS, TABLE_HINTS
from joinpilot.profiling.models import ProjectProfile
from joinpilot.services.projects import ProjectService


class GlossaryMatch(BaseModel):
    """A column that matches a search, with how closely (cosine similarity, -1 to 1)."""

    column: str
    description: str
    score: float


def words(name: str) -> str:
    """`product_group` or `ProductGroup` as plain words."""
    return " ".join(
        re.split(r"[^a-z0-9]+", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower())
    ).strip()


def describe(table: str, column: str) -> str:
    """Business words for one column: known SAP-style meanings, otherwise its name."""
    table_words = TABLE_HINTS.get(table.upper(), words(table))
    column_words = FIELD_HINTS.get(column.upper(), words(column))
    return f"{column_words} of {table_words} ({table}.{column})"


class GlossaryService:
    """Glossary rows live in the app database; Postgres searches them with pgvector."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.projects = ProjectService(settings)
        ensure_migrated(settings.db_url)

    def rebuild(self, project_id: str, profile: ProjectProfile) -> int:
        """Replace the project's glossary with one entry per column; returns the count."""
        rows = [
            GlossaryRow(
                project_id=project_id,
                column_ref=f"{t.name}.{c.name}",
                description=(text := describe(t.name, c.name)),
                embedding=embed(text),
            )
            for t in profile.tables
            for c in t.columns
        ]
        with session_scope(self.settings.db_url) as session:
            session.execute(delete(GlossaryRow).where(GlossaryRow.project_id == project_id))
            session.add_all(rows)
        return len(rows)

    def search(self, project_id: str, query: str, k: int) -> list[GlossaryMatch]:
        """The `k` columns whose descriptions are most similar to `query`."""
        project = self.projects.get(project_id)
        if not self._count(project.id):
            self.rebuild(project.id, self.projects.profile(project.id))
        vector = embed(query)
        if self.settings.db_url.startswith("postgresql"):
            return self._search_pgvector(project.id, vector, k)
        with session_scope(self.settings.db_url) as session:
            rows = session.scalars(select(GlossaryRow).where(GlossaryRow.project_id == project.id))
            scored = [
                GlossaryMatch(
                    column=r.column_ref,
                    description=r.description,
                    score=round(cosine(vector, list(r.embedding)), 4),
                )
                for r in rows
            ]
        return sorted(scored, key=lambda m: (-m.score, m.column))[:k]

    def _search_pgvector(self, project_id: str, vector: list[float], k: int) -> list[GlossaryMatch]:
        query_vector = cast(
            literal(vector, Vector(EMBEDDING_DIMENSIONS)), Vector(EMBEDDING_DIMENSIONS)
        )
        distance = GlossaryRow.embedding.op("<=>", return_type=Float)(query_vector)
        statement = (
            select(GlossaryRow.column_ref, GlossaryRow.description, distance)
            .where(GlossaryRow.project_id == project_id)
            .order_by(distance, GlossaryRow.column_ref)
            .limit(k)
        )
        with session_scope(self.settings.db_url) as session:
            return [
                GlossaryMatch(column=ref, description=text, score=round(1 - float(d), 4))
                for ref, text, d in session.execute(statement)
            ]

    def _count(self, project_id: str) -> int:
        with session_scope(self.settings.db_url) as session:
            statement = select(func.count()).where(GlossaryRow.project_id == project_id)
            return int(session.scalar(statement) or 0)
