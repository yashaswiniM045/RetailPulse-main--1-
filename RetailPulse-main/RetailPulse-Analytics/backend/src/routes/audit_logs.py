import csv
import io
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.user import User, UserRole
from src.schemas.audit_log import AuditLogPage, AuditLogRead
from src.services.audit_log_service import get_audit_log, list_audit_logs
from src.services.audit_service import AuditAction, create_audit_log

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])
ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)


def _filters(
    user_id: int | None,
    action: str | None,
    resource_type: str | None,
    status_filter: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    search: str | None,
    sort_order: str,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "status_filter": status_filter,
        "start_date": start_date,
        "end_date": end_date,
        "search": search,
        "sort_order": sort_order,
    }


@router.get("", response_model=AuditLogPage)
def list_audit_logs_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    return list_audit_logs(db, current_user.company_id, page=page, page_size=page_size, **_filters(user_id, action, resource_type, status_filter, start_date, end_date, search, sort_order))


def _export_rows(db: Session, current_user: User, **filters: Any) -> list[dict[str, Any]]:
    first_page = list_audit_logs(db, current_user.company_id, page=1, page_size=100, **filters)
    rows = list(first_page["items"])
    for page in range(2, first_page["totalPages"] + 1):
        rows.extend(list_audit_logs(db, current_user.company_id, page=page, page_size=100, **filters)["items"])
    return rows


@router.get("/export.csv")
def export_audit_logs_csv_route(
    request: Request,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    filters = _filters(user_id, action, resource_type, status_filter, start_date, end_date, search, sort_order)
    rows = _export_rows(db, current_user, **filters)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "user", "action", "resource", "resource_id", "description", "ip_address", "timestamp", "status", "before_values", "after_values"], extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({"id": row["id"], "user": row["userName"], "action": row["action"], "resource": row["resourceName"] or row["resourceType"], "resource_id": row["resourceId"], "description": row["description"], "ip_address": row["ipAddress"], "timestamp": row["timestamp"], "status": row["status"], "before_values": json.dumps(row["beforeValues"]), "after_values": json.dumps(row["afterValues"])})
    create_audit_log(db, company_id=current_user.company_id, user_id=current_user.id, performed_by=current_user.name, entity_type="AuditLog", action=AuditAction.AUDIT_LOGS_EXPORTED, request=request, export_type="csv", description="Exported audit logs as CSV")
    db.commit()
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'})


@router.get("/export.pdf")
def export_audit_logs_pdf_route(
    request: Request,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    rows = _export_rows(db, current_user, **_filters(user_id, action, resource_type, status_filter, start_date, end_date, search, sort_order))
    lines = ["RetailPulse Audit Logs", ""]
    lines.extend(f"{row['timestamp']} | {row['userName'] or '-'} | {row['action']} | {row['resourceType'] or '-'} {row['resourceId'] or ''} | {row['status']}" for row in rows)
    content = "\n".join(lines)
    pdf = _minimal_pdf(content)
    create_audit_log(db, company_id=current_user.company_id, user_id=current_user.id, performed_by=current_user.name, entity_type="AuditLog", action=AuditAction.AUDIT_LOGS_EXPORTED, request=request, export_type="pdf", description="Exported audit logs as PDF")
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="audit-logs.pdf"'})


def _minimal_pdf(content: str) -> bytes:
    text = content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 8 Tf 40 760 Td 10 TL ({text[:5000]}) Tj ET".encode("latin-1", "replace")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    output = io.BytesIO(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.write(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return output.getvalue()


@router.get("/{audit_id}", response_model=AuditLogRead)
def audit_log_detail_route(
    audit_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    return get_audit_log(db, current_user.company_id, audit_id)
