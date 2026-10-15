from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.user import User, UserRole
from src.schemas.reporting import ReportGenerateRequest, ReportHistoryRead, ReportPageRead, ReportResultRead, ScheduleCreate, ScheduleUpdate, ScheduledReportRead
from src.services.reporting_service import (
	create_scheduled_report,
	delete_scheduled_report,
	export_history,
	generate_report,
	get_report_filters,
	get_report_history,
	get_report_result,
	list_report_history,
	list_scheduled_reports,
	set_schedule_active,
	update_scheduled_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])
REPORT_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)
SCHEDULE_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)


@router.get("/filters")
def report_filters_route(current_user: User = Depends(require_roles(*REPORT_ROLES)), db: Session = Depends(get_db)):
	return get_report_filters(db, current_user.company_id)


@router.post("/generate", response_model=ReportResultRead)
def generate_report_route(payload: ReportGenerateRequest, current_user: User = Depends(require_roles(*REPORT_ROLES)), db: Session = Depends(get_db)):
	return generate_report(db, current_user, payload.report_type, payload.filters)


@router.get("/history")
def report_history_route(
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
	current_user: User = Depends(require_roles(*REPORT_ROLES)),
	db: Session = Depends(get_db),
):
	return list_report_history(db, current_user.company_id, page, page_size)


@router.get("/history/{history_id}", response_model=ReportResultRead)
def report_history_detail_route(
	history_id: int,
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
	sort_by: str | None = Query(default=None, alias="sortBy"),
	sort_direction: str = Query(default="asc", alias="sortDirection", pattern="^(asc|desc)$"),
	current_user: User = Depends(require_roles(*REPORT_ROLES)),
	db: Session = Depends(get_db),
):
	return get_report_result(
		db,
		current_user.company_id,
		history_id,
		page=page,
		page_size=page_size,
		sort_by=sort_by,
		sort_direction=sort_direction,
	)


@router.get("/history/{history_id}/export")
def export_report_route(
	history_id: int,
	format: str = Query(pattern="^(csv|pdf)$"),
	current_user: User = Depends(require_roles(*REPORT_ROLES)),
	db: Session = Depends(get_db),
):
	content, media_type, file_name = export_history(db, current_user.company_id, history_id, format)
	return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{file_name}"'})


@router.get("/schedules", response_model=list[ScheduledReportRead])
def scheduled_reports_route(current_user: User = Depends(require_roles(*REPORT_ROLES)), db: Session = Depends(get_db)):
	return list_scheduled_reports(db, current_user.company_id)


@router.post("/schedules", response_model=ScheduledReportRead, status_code=201)
def create_schedule_route(payload: ScheduleCreate, current_user: User = Depends(require_roles(*SCHEDULE_ROLES)), db: Session = Depends(get_db)):
	return create_scheduled_report(db, current_user, payload)


@router.put("/schedules/{schedule_id}", response_model=ScheduledReportRead)
def update_schedule_route(schedule_id: int, payload: ScheduleUpdate, current_user: User = Depends(require_roles(*SCHEDULE_ROLES)), db: Session = Depends(get_db)):
	return update_scheduled_report(db, current_user, schedule_id, payload)


@router.patch("/schedules/{schedule_id}/status", response_model=ScheduledReportRead)
def schedule_status_route(
	schedule_id: int,
	is_active: bool = Query(alias="isActive"),
	current_user: User = Depends(require_roles(*SCHEDULE_ROLES)),
	db: Session = Depends(get_db),
):
	return set_schedule_active(db, current_user, schedule_id, is_active)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule_route(schedule_id: int, current_user: User = Depends(require_roles(*SCHEDULE_ROLES)), db: Session = Depends(get_db)):
	delete_scheduled_report(db, current_user, schedule_id)
	return None