from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.user import User, UserRole
from src.schemas.data_quality import (
	DataQualityIssueDetail,
	DataQualityIssuePage,
	DataQualityIssueRead,
	DataQualityOverview,
	IssueStatusUpdate,
	ReconciliationResult,
	ReconciliationRunPage,
)
from src.services.data_quality_service import (
	get_issue_detail,
	get_issue_filter_options,
	get_overview,
	list_issues,
	list_reconciliation_runs,
	run_reconciliation,
	update_issue_status,
)

router = APIRouter(prefix="/data-quality", tags=["data-quality"])
DATA_QUALITY_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)


@router.get("/overview", response_model=DataQualityOverview)
def data_quality_overview_route(
	current_user: User = Depends(require_roles(*DATA_QUALITY_ROLES)),
	db: Session = Depends(get_db),
):
	return get_overview(db, current_user.company_id)


@router.get("/issues/options")
def data_quality_issue_options_route(
	current_user: User = Depends(require_roles(*DATA_QUALITY_ROLES)),
	db: Session = Depends(get_db),
):
	return get_issue_filter_options(db, current_user.company_id)


@router.get("/issues", response_model=DataQualityIssuePage)
def list_data_quality_issues_route(
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
	search: str | None = None,
	issue_type: str | None = Query(default=None, alias="issueType"),
	severity: str | None = None,
	module: str | None = None,
	status_filter: str | None = Query(default=None, alias="status"),
	start_date: datetime | None = Query(default=None, alias="startDate"),
	end_date: datetime | None = Query(default=None, alias="endDate"),
	sort_by: str = Query(default="detectedAt", alias="sortBy"),
	sort_direction: str = Query(default="desc", alias="sortDirection", pattern="^(asc|desc)$"),
	current_user: User = Depends(require_roles(*DATA_QUALITY_ROLES)),
	db: Session = Depends(get_db),
):
	return list_issues(
		db,
		current_user.company_id,
		page=page,
		page_size=page_size,
		search=search,
		issue_type=issue_type,
		severity=severity,
		module=module,
		status_filter=status_filter,
		start_date=start_date,
		end_date=end_date,
		sort_by=sort_by,
		sort_direction=sort_direction,
	)


@router.get("/issues/{issue_id}", response_model=DataQualityIssueDetail)
def data_quality_issue_detail_route(
	issue_id: int,
	current_user: User = Depends(require_roles(*DATA_QUALITY_ROLES)),
	db: Session = Depends(get_db),
):
	return get_issue_detail(db, current_user.company_id, issue_id)


@router.patch("/issues/{issue_id}/status", response_model=DataQualityIssueRead)
def update_data_quality_issue_status_route(
	issue_id: int,
	payload: IssueStatusUpdate,
	request: Request,
	current_user: User = Depends(require_roles(*DATA_QUALITY_ROLES)),
	db: Session = Depends(get_db),
):
	return update_issue_status(db, current_user, issue_id, payload, request)


@router.post("/reconcile", response_model=ReconciliationResult)
def run_data_quality_reconciliation_route(
	request: Request,
	current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
	db: Session = Depends(get_db),
):
	return run_reconciliation(db, current_user, request)


@router.get("/history", response_model=ReconciliationRunPage)
def reconciliation_history_route(
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
	current_user: User = Depends(require_roles(*DATA_QUALITY_ROLES)),
	db: Session = Depends(get_db),
):
	return list_reconciliation_runs(db, current_user.company_id, page, page_size)