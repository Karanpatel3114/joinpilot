"""Project, upload and profile endpoints (docs/contract.md, "Projects and tables")."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from joinpilot.api.deps import get_glossary_service, get_project_service
from joinpilot.api.schemas import (
    CreateProjectRequest,
    Project,
    ProjectProfile,
    SampleRequest,
    TableSummary,
)
from joinpilot.errors import InvalidInputError
from joinpilot.glossary.service import GlossaryMatch, GlossaryService
from joinpilot.services.projects import ProjectService
from joinpilot.services.store import ProjectRecord, TableRecord

router = APIRouter(tags=["projects"])
Service = Annotated[ProjectService, Depends(get_project_service)]

UPLOAD_DOC = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
                    },
                }
            },
            "application/json": {"schema": SampleRequest.model_json_schema()},
        }
    }
}


def to_project(record: ProjectRecord) -> Project:
    """Map a stored record to the contract's Project shape."""
    return Project(
        id=record.id,
        name=record.name,
        created_at=record.created_at,
        table_count=len(record.tables),
    )


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(body: CreateProjectRequest, service: Service) -> Project:
    """Create an empty project."""
    return to_project(await run_in_threadpool(service.create, body.name))


@router.get("/projects", response_model=list[Project])
async def list_projects(service: Service) -> list[Project]:
    """List projects, newest first."""
    return [to_project(r) for r in await run_in_threadpool(service.list_projects)]


@router.post(
    "/projects/{project_id}/tables",
    response_model=list[TableSummary],
    status_code=status.HTTP_201_CREATED,
    openapi_extra=UPLOAD_DOC,
)
async def add_tables(project_id: UUID, request: Request, service: Service) -> list[TableSummary]:
    """Upload CSV or Parquet files (multipart field `files`), or load `{"sample": "erp_s1_sap"}`.

    File types are checked for the whole batch first; files then load in order.
    """
    pid = str(project_id)
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        async with request.form() as form:
            uploads = [f for f in form.getlist("files") if isinstance(f, UploadFile)]
            if not uploads:
                raise InvalidInputError("Attach at least one file in the `files` field.")
            names = [upload.filename or "upload.csv" for upload in uploads]
            service.check_upload_names(names)
            added: list[TableRecord] = []
            for name, upload in zip(names, uploads, strict=True):
                added += await run_in_threadpool(service.add_upload, pid, name, upload.file)
    else:
        try:
            body = SampleRequest.model_validate_json(await request.body())
        except ValidationError as error:
            raise InvalidInputError("Send files as multipart or a JSON sample request.") from error
        added = await run_in_threadpool(service.add_sample, pid, body.sample)
    return [TableSummary.model_validate(t.model_dump()) for t in added]


@router.get("/projects/{project_id}/glossary", response_model=list[GlossaryMatch])
async def search_glossary(
    project_id: UUID,
    glossary: Annotated[GlossaryService, Depends(get_glossary_service)],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    k: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[GlossaryMatch]:
    """Columns whose business description best matches the words in `q`."""
    return await run_in_threadpool(glossary.search, str(project_id), q, k)


@router.get("/projects/{project_id}/profile", response_model=ProjectProfile)
async def get_profile(project_id: UUID, service: Service) -> ProjectProfile:
    """Column statistics, candidate keys, uniqueness and overlap evidence for every table."""
    return await run_in_threadpool(service.profile, str(project_id))
