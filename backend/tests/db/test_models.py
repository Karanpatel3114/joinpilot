from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from joinpilot.db.models import LLMCallRow, ProjectRow, ProposalRow, RunRow, TableRow
from joinpilot.db.session import migrate, session_scope


@pytest.fixture
def url(tmp_path: Path) -> str:
    database = f"sqlite:///{tmp_path / 'app.db'}"
    migrate(database)
    return database


def test_projects_runs_and_proposals_round_trip(url: str) -> None:
    with session_scope(url) as session:
        project = ProjectRow(
            id="p1",
            name="Demo",
            tables=[TableRow(id="t1", name="KNA1", row_count=10, column_count=3)],
        )
        run = RunRow(id="r1", project_id="p1", requirement="Aging", status="queued")
        run.proposals = [ProposalRow(edge_id="e1", position=0, payload={"from": "A.k"})]
        session.add_all([project, run])
    with session_scope(url) as session:
        stored = session.get(RunRow, "r1")
        assert stored is not None
        assert stored.warnings == [] and stored.timings_ms == {}
        assert stored.proposals[0].payload == {"from": "A.k"}
        assert stored.proposals[0].status == "proposed"
        assert stored.created_at is not None


def test_table_names_are_unique_per_project(url: str) -> None:
    with pytest.raises(IntegrityError), session_scope(url) as session:
        session.add(
            ProjectRow(
                id="p1",
                name="Demo",
                tables=[
                    TableRow(id="t1", name="KNA1", row_count=1, column_count=1),
                    TableRow(id="t2", name="KNA1", row_count=1, column_count=1),
                ],
            )
        )


def test_deleting_a_project_deletes_its_runs_and_keeps_usage(url: str) -> None:
    with session_scope(url) as session:
        session.add(ProjectRow(id="p1", name="Demo"))
        session.add(RunRow(id="r1", project_id="p1", requirement="x", status="queued"))
    with session_scope(url) as session:
        session.add(LLMCallRow(run_id="r1", purpose="rank_joins", provider="fake", model="m"))
    with session_scope(url) as session:
        session.delete(session.get(ProjectRow, "p1"))
    with session_scope(url) as session:
        assert session.scalars(select(RunRow)).all() == []
        [call] = session.scalars(select(LLMCallRow)).all()
        assert call.run_id is None
