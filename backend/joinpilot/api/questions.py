"""Question answering endpoint (docs/contract.md, "Dashboard and questions")."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from joinpilot.api.deps import get_question_service, guard_project_access
from joinpilot.api.schemas import Answer, AskRequest
from joinpilot.services.questions import QuestionService

router = APIRouter(tags=["questions"], dependencies=[Depends(guard_project_access)])
Questions = Annotated[QuestionService, Depends(get_question_service)]


@router.post("/projects/{project_id}/ask", response_model=Answer)
async def ask(project_id: UUID, body: AskRequest, questions: Questions) -> Answer:
    """Answer a question with guarded, read-only SQL over the newest tested model."""
    return await run_in_threadpool(questions.ask, str(project_id), body.question)
