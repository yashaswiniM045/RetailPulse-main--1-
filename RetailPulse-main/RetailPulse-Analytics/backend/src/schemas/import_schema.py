from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ImportTypeSelection(BaseModel):
    importType: str


class ImportUploadRequest(BaseModel):
    importType: str


class ImportValidationRequest(BaseModel):
    importType: str
    rows: list[dict[str, str]]


class ImportProcessRequest(BaseModel):
    importType: str
    rows: list[dict[str, str]]
    filename: str = "import.csv"


class ImportIssue(BaseModel):
    rowNumber: int | None = None
    row: dict[str, str]
    message: str
    errorType: str = "invalid"


class ImportValidationSummary(BaseModel):
    totalRecords: int
    validCount: int
    invalidCount: int
    duplicateCount: int
    missingColumns: list[str] = Field(default_factory=list)
    issues: list[ImportIssue] = Field(default_factory=list)
    preview: list[dict[str, str]] = Field(default_factory=list)


class ImportHistoryRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    importType: str = Field(alias="import_type")
    filename: str
    uploadedBy: str = Field(alias="uploaded_by")
    totalRecords: int = Field(alias="total_records")
    successfulRecords: int = Field(alias="successful_records")
    failedRecords: int = Field(alias="failed_records")
    duplicateRecords: int = Field(alias="duplicate_records")
    status: str
    createdAt: datetime = Field(alias="created_at")
    completedAt: datetime | None = Field(alias="completed_at")


class ImportResultSummary(BaseModel):
    importId: int
    totalRecords: int
    successfullyAdded: int
    failedRecords: int
    duplicateRecords: int
    validationFailures: int
    status: str
    errors: list[dict[str, object]] = Field(default_factory=list)


class ImportDetailResponse(BaseModel):
    importId: int
    importType: str
    filename: str
    uploadedBy: str
    totalRecords: int
    successfulRecords: int
    failedRecords: int
    duplicateRecords: int
    status: str
    createdAt: datetime
    completedAt: datetime | None
    errors: list[dict[str, object]] = Field(default_factory=list)
