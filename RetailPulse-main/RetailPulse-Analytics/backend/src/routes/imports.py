from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.user import User, UserRole
from src.schemas.import_schema import ImportDetailResponse, ImportHistoryRecord, ImportResultSummary, ImportValidationSummary
from src.services.import_service import get_import_errors, get_import_history_record, list_import_history, parse_csv_upload, process_import_rows, validate_csv_rows

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload", response_model=dict)
def upload_import_route(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    rows, columns = parse_csv_upload(file)
    validation = validate_csv_rows(import_type, rows, db=db, company_id=current_user.company_id)
    return {
        "filename": file.filename,
        "importType": import_type,
        "columns": columns,
        "preview": validation["preview"],
        "summary": {
            "totalRecords": validation["total_records"],
            "validCount": validation["valid_count"],
            "invalidCount": validation["invalid_count"],
            "duplicateCount": validation["duplicate_count"],
            "missingColumns": validation["missing_columns"],
            "issues": validation["issues"],
        },
    }


@router.post("/validate", response_model=ImportValidationSummary)
def validate_import_route(
    payload: dict,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    import_type = str(payload.get("importType", "")).strip().lower()
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rows must be a list")
    result = validate_csv_rows(import_type, rows, db=db, company_id=current_user.company_id)
    return ImportValidationSummary(
        totalRecords=result["total_records"],
        validCount=result["valid_count"],
        invalidCount=result["invalid_count"],
        duplicateCount=result["duplicate_count"],
        missingColumns=result["missing_columns"],
        issues=result["issues"],
        preview=result["preview"],
    )


@router.post("/process", response_model=ImportResultSummary)
def process_import_route(
    payload: dict,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    import_type = str(payload.get("importType", "")).strip().lower()
    file_name = str(payload.get("filename", "import.csv"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rows must be a list")
    result = process_import_rows(db, current_user, import_type, rows, file_name, request)
    return ImportResultSummary(
        importId=result["importId"],
        totalRecords=result["totalRecords"],
        successfullyAdded=result["successfullyAdded"],
        failedRecords=result["failedRecords"],
        duplicateRecords=result["duplicateRecords"],
        validationFailures=result["validationFailures"],
        status=result["status"],
        errors=result["errors"],
    )


@router.get("/history", response_model=list[ImportHistoryRecord])
def import_history_route(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    history = list_import_history(db, current_user.company_id)
    return [ImportHistoryRecord.model_validate(item) for item in history]


@router.get("/{import_id}", response_model=ImportDetailResponse)
def get_import_detail_route(
    import_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    item = get_import_history_record(db, current_user.company_id, import_id)
    return ImportDetailResponse(
        importId=item.id,
        importType=item.import_type,
        filename=item.filename,
        uploadedBy=item.uploaded_by,
        totalRecords=item.total_records,
        successfulRecords=item.successful_records,
        failedRecords=item.failed_records,
        duplicateRecords=item.duplicate_records,
        status=item.status,
        createdAt=item.created_at,
        completedAt=item.completed_at,
        errors=[{"rowNumber": error.row_number, "message": error.message, "errorType": error.error_type} for error in item.errors],
    )


@router.get("/{import_id}/errors", response_model=list[dict])
def import_errors_route(
    import_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN)),
    db: Session = Depends(get_db),
):
    errors = get_import_errors(db, current_user.company_id, import_id)
    return [{"rowNumber": error.row_number, "errorType": error.error_type, "message": error.message, "rowData": error.row_data} for error in errors]
