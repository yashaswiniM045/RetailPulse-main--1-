from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IssueStatus = Literal["Open", "Investigating", "Resolved", "Ignored"]


class IssueStatusUpdate(BaseModel):
	status: IssueStatus
	resolution_note: str | None = Field(default=None, alias="resolutionNote", max_length=2000)

	model_config = ConfigDict(populate_by_name=True)

	@model_validator(mode="after")
	def validate_resolution_note(self):
		if self.status == "Resolved" and not (self.resolution_note or "").strip():
			raise ValueError("A resolution note is required when resolving an issue")
		if self.resolution_note is not None:
			self.resolution_note = self.resolution_note.strip() or None
		return self


class DataQualityIssueRead(BaseModel):
	model_config = ConfigDict(from_attributes=True, populate_by_name=True)

	id: int
	issue_type: str = Field(alias="issueType")
	severity: str
	module: str
	record_type: str = Field(alias="recordType")
	record_id: str = Field(alias="recordId")
	record_name: str | None = Field(alias="recordName")
	description: str
	details: dict
	status: IssueStatus
	detected_at: datetime = Field(alias="detectedAt")
	last_seen_at: datetime = Field(alias="lastSeenAt")
	resolved_at: datetime | None = Field(alias="resolvedAt")
	resolved_by_name: str | None = Field(alias="resolvedBy")
	resolution_note: str | None = Field(alias="resolutionNote")


class DataQualityIssuePage(BaseModel):
	items: list[DataQualityIssueRead]
	total: int
	page: int
	page_size: int = Field(alias="pageSize")
	total_pages: int = Field(alias="totalPages")


class IssueEventRead(BaseModel):
	model_config = ConfigDict(from_attributes=True, populate_by_name=True)

	id: int
	changed_by_name: str = Field(alias="changedBy")
	previous_status: str = Field(alias="previousStatus")
	new_status: str = Field(alias="newStatus")
	note: str | None
	created_at: datetime = Field(alias="createdAt")


class DataQualityIssueDetail(BaseModel):
	issue: DataQualityIssueRead
	context: dict
	events: list[IssueEventRead]


class ReconciliationRunRead(BaseModel):
	model_config = ConfigDict(from_attributes=True, populate_by_name=True)

	id: int
	triggered_by_name: str = Field(alias="triggeredBy")
	started_at: datetime = Field(alias="startedAt")
	completed_at: datetime | None = Field(alias="completedAt")
	records_checked: int = Field(alias="recordsChecked")
	valid_records: int = Field(alias="validRecords")
	warning_count: int = Field(alias="warningCount")
	error_count: int = Field(alias="errorCount")
	issues_detected: int = Field(alias="issuesDetected")
	issues_resolved: int = Field(alias="issuesResolved")
	failed_checks: int = Field(alias="failedChecks")
	status: str
	check_results: list = Field(alias="checkResults")
	error_message: str | None = Field(alias="errorMessage")


class ReconciliationRunPage(BaseModel):
	items: list[ReconciliationRunRead]
	total: int
	page: int
	page_size: int = Field(alias="pageSize")
	total_pages: int = Field(alias="totalPages")


class DataQualityOverview(BaseModel):
	records_checked: int = Field(alias="recordsChecked")
	valid_records: int = Field(alias="validRecords")
	warning_records: int = Field(alias="warningRecords")
	error_records: int = Field(alias="errorRecords")
	unresolved_issues: int = Field(alias="unresolvedIssues")
	last_reconciliation_at: datetime | None = Field(alias="lastReconciliationAt")
	last_run_status: str | None = Field(alias="lastRunStatus")


class ReconciliationResult(BaseModel):
	run: ReconciliationRunRead
	new_issues: int = Field(alias="newIssues")
	updated_issues: int = Field(alias="updatedIssues")