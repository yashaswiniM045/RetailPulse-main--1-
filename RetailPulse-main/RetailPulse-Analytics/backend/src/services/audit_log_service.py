from datetime import datetime
from math import ceil
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.user import User


def _filters(
    company_id: int,
    *,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    status_filter: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
):
    conditions = [AuditLog.company_id == company_id]
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.entity_type == resource_type)
    if status_filter:
        conditions.append(AuditLog.status == status_filter)
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)
    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(or_(
            func.lower(func.coalesce(User.name, "")).like(pattern),
            func.lower(AuditLog.action).like(pattern),
            func.lower(func.coalesce(AuditLog.entity_type, "")).like(pattern),
            func.lower(func.coalesce(AuditLog.entity_name, "")).like(pattern),
            func.lower(func.coalesce(AuditLog.description, "")).like(pattern),
            func.lower(func.coalesce(cast(AuditLog.resource_id, String), "")).like(pattern),
        ))
    return conditions


def _query(company_id: int, **kwargs: Any):
    return (
        select(AuditLog, User.name, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(*_filters(company_id, **kwargs))
    )


def _serialize(log: AuditLog, user_name: str | None, user_email: str | None) -> dict[str, Any]:
    return {
        "id": log.id,
        "userName": user_name or log.performed_by,
        "userEmail": user_email,
        "action": log.action,
        "resourceType": log.entity_type,
        "resourceId": log.resource_id,
        "resourceName": log.entity_name,
        "description": log.description,
        "ipAddress": log.ip_address,
        "userAgent": log.browser,
        "timestamp": log.created_at,
        "status": log.status,
        "beforeValues": log.before_values,
        "afterValues": log.after_values,
    }


def list_audit_logs(
    db: Session,
    company_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    status_filter: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
    sort_order: str = "desc",
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    kwargs = {
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "status_filter": status_filter,
        "start_date": start_date,
        "end_date": end_date,
        "search": search,
    }
    conditions = _filters(company_id, **kwargs)
    total = db.scalar(
        select(func.count(AuditLog.id)).select_from(AuditLog).outerjoin(User, AuditLog.user_id == User.id).where(*conditions)
    ) or 0
    ordering = AuditLog.created_at.asc() if sort_order == "asc" else AuditLog.created_at.desc()
    rows = db.execute(_query(company_id, **kwargs).order_by(ordering, AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = ceil(total / page_size) if total else 0
    return {
        "items": [_serialize(log, user_name, user_email) for log, user_name, user_email in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def get_audit_log(db: Session, company_id: int, audit_id: int) -> dict[str, Any]:
    row = db.execute(_query(company_id).where(AuditLog.id == audit_id)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return _serialize(*row)
