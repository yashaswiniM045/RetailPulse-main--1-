from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.dependencies.auth import get_current_user, require_roles
from src.dependencies.database import get_db
from src.models.user import User, UserRole
from src.schemas.workflow import ApprovalDecision, ApprovalRequestCreate, ApprovalRejection, WorkflowConfigurationUpdate
from src.services.workflow_service import (
    approve_workflow_request,
    cancel_workflow_request,
    create_workflow_request,
    get_pending_approval_count,
    get_workflow_request,
    list_workflow_configurations,
    list_workflow_requests,
    reject_workflow_request,
    submit_workflow_request,
    update_workflow_configuration,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])
admins = require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)


@router.get("/pending-count")
def pending_workflow_count_route(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_pending_approval_count(db, current_user)


@router.get("/config")
def list_workflow_configurations_route(
    current_user: User = Depends(admins),
    db: Session = Depends(get_db),
):
    return list_workflow_configurations(db, current_user.company_id)


@router.put("/config/{request_type}")
def update_workflow_configuration_route(
    request_type: str,
    payload: WorkflowConfigurationUpdate,
    request: Request,
    current_user: User = Depends(admins),
    db: Session = Depends(get_db),
):
    return update_workflow_configuration(db, current_user, request_type, payload, request)


@router.get("")
def list_workflow_requests_route(
    scope: Literal["all", "mine", "queue"] = "all",
    request_type: str | None = Query(default=None, alias="requestType"),
    request_status: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    sort_direction: Literal["asc", "desc"] = Query(default="desc", alias="sortDirection"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_workflow_requests(
        db,
        current_user,
        scope=scope,
        request_type=request_type,
        status_filter=request_status,
        search=search,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.post("", status_code=201)
def create_workflow_request_route(
    payload: ApprovalRequestCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_workflow_request(db, current_user, payload, request)


@router.get("/{request_id}/history")
def workflow_request_history_route(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_workflow_request(db, current_user, request_id)["history"]


@router.post("/{request_id}/submit")
def submit_workflow_request_route(
    request_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submit_workflow_request(db, current_user, request_id, request)


@router.post("/{request_id}/approve")
def approve_workflow_request_route(
    request_id: int,
    payload: ApprovalDecision,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return approve_workflow_request(db, current_user, request_id, payload.comment, request)


@router.post("/{request_id}/reject")
def reject_workflow_request_route(
    request_id: int,
    payload: ApprovalRejection,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reject_workflow_request(db, current_user, request_id, payload.comment, request)


@router.post("/{request_id}/cancel")
def cancel_workflow_request_route(
    request_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cancel_workflow_request(db, current_user, request_id, request)


@router.get("/{request_id}")
def get_workflow_request_route(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_workflow_request(db, current_user, request_id)
