import csv
import io
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.category import Category
from src.models.import_history import ImportErrorRecord, ImportHistory, ImportJob, ImportStatus
from src.models.user import User, UserRole
from src.schemas.import_schema import ImportDetailResponse, ImportHistoryRecord, ImportValidationSummary
from src.services.audit_service import AuditAction, create_audit_log
from src.services.import_service import (
    REQUIRED_COLUMNS,
    create_staged_import,
    get_import_errors,
    get_import_history_record,
    parse_csv_upload,
    start_staged_import,
    validate_csv_rows,
)

router = APIRouter(prefix="/imports", tags=["imports"])
authorized_importer = require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)


def _validation_response(summary: dict) -> dict:
    return {
        "totalRecords": summary["total_records"],
        "validCount": summary["valid_count"],
        "invalidCount": summary["invalid_count"],
        "duplicateCount": summary["duplicate_count"],
        "missingColumns": summary["missing_columns"],
        "issues": summary["issues"],
        "preview": summary["preview"],
    }


def _safe_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _summary(record: ImportHistory, job: ImportJob | None) -> dict:
    total = record.total_records or 0
    processed = min(job.processed_records, total) if job else 0
    progress = (
        100
        if record.status
        in {
            ImportStatus.COMPLETED.value,
            ImportStatus.COMPLETED_WITH_ERRORS.value,
            ImportStatus.FAILED.value,
        }
        else round(processed * 100 / total)
        if total
        else 0
    )
    return {
        "importId": record.id,
        "importType": record.import_type,
        "filename": record.filename,
        "uploadedBy": record.uploaded_by,
        "totalRecords": total,
        "successfullyAdded": record.successful_records,
        "successfulRecords": record.successful_records,
        "failedRecords": record.failed_records,
        "duplicateRecords": record.duplicate_records,
        "skippedRecords": job.skipped_records if job else 0,
        "processedRecords": processed,
        "progressPercent": progress,
        "status": record.status,
        "createdAt": record.created_at,
        "startedAt": job.started_at if job else None,
        "completedAt": record.completed_at,
        "durationSeconds": job.duration_seconds if job else None,
    }


@router.get("/templates/{import_type}")
def download_import_template(
    import_type: str,
    current_user: User = Depends(authorized_importer),
):
    del current_user
    import_key = import_type.strip().lower()
    columns = REQUIRED_COLUMNS.get(import_key)
    if columns is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import type not found")
    if import_key == "inventory":
        columns = ["SKU", "Quantity", "Reorder Level"]
    output = io.StringIO(newline="")
    csv.writer(output).writerow(columns)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{import_key}-import-template.csv"'},
    )


@router.post("/upload")
def upload_import_route(
    request: Request,
    file: UploadFile = File(...),
    import_type: str = Form(...),
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    rows, columns = parse_csv_upload(file)
    if not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV contains no data rows")
    safe_filename = re.split(r"[/\\]", file.filename or "import.csv")[-1][:255]
    record, summary = create_staged_import(
        db, current_user, import_type, safe_filename, rows, request
    )
    return {
        "importId": record.id,
        "filename": record.filename,
        "importType": record.import_type,
        "columns": columns,
        "preview": summary["preview"],
        "summary": _validation_response(summary),
        "status": record.status,
    }


@router.post("/validate", response_model=ImportValidationSummary)
def validate_import_route(
    payload: dict,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    import_type = str(payload.get("importType", "")).strip().lower()
    rows = payload.get("rows", [])
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rows must be a list of records")
    if len(rows) > 10000:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Validate at most 10,000 rows at a time")
    result = validate_csv_rows(
        import_type, rows, db=db, company_id=current_user.company_id
    )
    return _validation_response(result)


@router.post("/{import_id}/start")
def start_import_route(
    import_id: int,
    request: Request,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    record = start_staged_import(db, current_user, import_id, request)
    return _summary(record, db.get(ImportJob, record.id))


@router.get("/history", response_model=list[ImportHistoryRecord])
def import_history_route(
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    history = db.execute(
        select(ImportHistory, ImportJob)
        .outerjoin(ImportJob, ImportJob.import_id == ImportHistory.id)
        .where(ImportHistory.company_id == current_user.company_id)
        .order_by(ImportHistory.created_at.desc(), ImportHistory.id.desc())
    ).all()
    return [
        ImportHistoryRecord.model_validate(
            {
                "id": item.id,
                "importType": item.import_type,
                "filename": item.filename,
                "uploadedBy": item.uploaded_by,
                "totalRecords": item.total_records,
                "successfulRecords": item.successful_records,
                "failedRecords": item.failed_records,
                "duplicateRecords": item.duplicate_records,
                "skippedRecords": job.skipped_records if job else 0,
                "durationSeconds": job.duration_seconds if job else None,
                "status": item.status,
                "createdAt": item.created_at,
                "completedAt": item.completed_at,
            }
        )
        for item, job in history
    ]


@router.get("/{import_id}/status")
def get_import_status_route(
    import_id: int,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    record = get_import_history_record(db, current_user.company_id, import_id)
    return _summary(record, db.get(ImportJob, record.id))


@router.post("/{import_id}/cancel")
def cancel_import_route(
    import_id: int,
    request: Request,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    record = get_import_history_record(db, current_user.company_id, import_id)
    if record.status not in {
        ImportStatus.UPLOADED.value,
        ImportStatus.VALIDATING.value,
        ImportStatus.PROCESSING.value,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This import cannot be cancelled")
    job = db.get(ImportJob, import_id)
    record.status = ImportStatus.CANCELLED.value
    record.completed_at = datetime.now(timezone.utc)
    if job:
        job.source_data = "[]"
        if job.started_at:
            started_at = job.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            job.duration_seconds = int((record.completed_at - started_at).total_seconds())
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Import",
        resource_id=record.id,
        entity_name=record.filename,
        action=AuditAction.IMPORT_CANCELLED,
        request=request,
        description="Import cancelled by user",
        status="cancelled",
    )
    db.commit()
    return _summary(record, job)


@router.get("/{import_id}", response_model=ImportDetailResponse)
def get_import_detail_route(
    import_id: int,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    record = get_import_history_record(db, current_user.company_id, import_id)
    job = db.get(ImportJob, record.id)
    validation_summary = None
    if job and record.status == ImportStatus.UPLOADED.value and job.source_data != "[]":
        rows = json.loads(job.source_data)
        categories = None
        if record.import_type == "products":
            categories = {
                category.name
                for category in db.scalars(
                    select(Category).where(Category.company_id == current_user.company_id)
                ).all()
            }
        validation_summary = _validation_response(
            validate_csv_rows(
                record.import_type,
                rows,
                db=db,
                company_id=current_user.company_id,
                category_names=categories,
            )
        )
    errors = db.scalars(
        select(ImportErrorRecord)
        .where(ImportErrorRecord.import_id == record.id)
        .order_by(ImportErrorRecord.row_number, ImportErrorRecord.id)
    ).all()
    return {
        **_summary(record, job),
        "validationSummary": validation_summary,
        "errors": [
            {
                "rowNumber": error.row_number,
                "message": error.message,
                "errorType": error.error_type,
                "row": json.loads(error.row_data) if error.row_data else {},
            }
            for error in errors
        ],
    }


@router.get("/{import_id}/errors")
def import_errors_route(
    import_id: int,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    errors = get_import_errors(db, current_user.company_id, import_id)
    return [
        {
            "rowNumber": error.row_number,
            "errorType": error.error_type,
            "message": error.message,
            "rowData": error.row_data,
        }
        for error in errors
    ]


@router.get("/{import_id}/errors.csv")
def download_import_errors_route(
    import_id: int,
    current_user: User = Depends(authorized_importer),
    db: Session = Depends(get_db),
):
    record = get_import_history_record(db, current_user.company_id, import_id)
    errors = get_import_errors(db, current_user.company_id, import_id)
    rows = [
        json.loads(error.row_data) if error.row_data else {}
        for error in errors
    ]
    columns = list(dict.fromkeys(column for row in rows for column in row))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["rowNumber", "errorType", "message", *(_safe_csv_cell(column) for column in columns)])
    for error, row in zip(errors, rows):
        writer.writerow(
            [
                error.row_number or "",
                _safe_csv_cell(error.error_type),
                _safe_csv_cell(error.message),
                *(_safe_csv_cell(row.get(column, "")) for column in columns),
            ]
        )
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", record.filename.rsplit(".", 1)[0])[:80]
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="import-{record.id}-{safe_name}-errors.csv"'},
    )
