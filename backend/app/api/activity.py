from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime

from app.api.auth_dependencies import Admin, Store
from app.repositories.account_activity import read_events
from app.schemas.activity import ActivityAction, ActivityKind, ActivityPage
from app.schemas.common import ErrorResponse
from app.services.activity_service import ActivityService, InvalidActivityCursor

router = APIRouter(tags=["project activity"])
service = ActivityService()


@router.get(
    "/activity",
    response_model=ActivityPage,
    summary="Read project change history (Admin only)",
    description=(
        "Records project, assignment and requirement changes made through the API "
        "after this feature was installed. History survives project deletion. "
        "Cursor pagination, newest first. No update/delete history endpoints."
    ),
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def list_activity(
    _admin: Admin,
    store: Store,
    source: Literal["graph", "accounts"] = "graph",
    project_id: Annotated[
        str | None, Query(pattern=r"^PROJ[0-9]{3,}$", max_length=100)
    ] = None,
    action: ActivityAction | None = None,
    resource_type: ActivityKind | None = None,
    actor: Annotated[str | None, Query(max_length=100)] = None,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    if since and until and since > until:
        raise HTTPException(422, "Start time must not be after end time.")
    try:
        if source == "accounts":
            if project_id or (resource_type and resource_type != "ACCOUNT"):
                raise HTTPException(
                    422, "Nhật ký tài khoản không lọc theo dự án hoặc loại nghiệp vụ."
                )

            def read(parameters):
                with store.connection() as db:
                    return read_events(db, parameters)

            return service.list(
                None, action, "ACCOUNT", actor, since, until, cursor, limit, reader=read
            )
        return service.list(
            project_id, action, resource_type, actor, since, until, cursor, limit
        )
    except InvalidActivityCursor as exc:
        raise HTTPException(422, str(exc)) from exc
