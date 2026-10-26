from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ReconciliationRun(Base):
	__tablename__ = "reconciliation_runs"
	__table_args__ = (Index("ix_reconciliation_runs_company_started", "company_id", "started_at"),)

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
	triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
	triggered_by_name: Mapped[str] = mapped_column(String(255), nullable=False)
	started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
	completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	records_checked: Mapped[int] = mapped_column(nullable=False, default=0)
	valid_records: Mapped[int] = mapped_column(nullable=False, default=0)
	warning_count: Mapped[int] = mapped_column(nullable=False, default=0)
	error_count: Mapped[int] = mapped_column(nullable=False, default=0)
	issues_detected: Mapped[int] = mapped_column(nullable=False, default=0)
	issues_resolved: Mapped[int] = mapped_column(nullable=False, default=0)
	failed_checks: Mapped[int] = mapped_column(nullable=False, default=0)
	status: Mapped[str] = mapped_column(String(30), nullable=False, default="Running", index=True)
	check_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
	error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataQualityIssue(Base):
	__tablename__ = "data_quality_issues"
	__table_args__ = (
		UniqueConstraint("company_id", "fingerprint", name="uq_data_quality_company_fingerprint"),
		Index("ix_data_quality_company_status", "company_id", "status"),
		Index("ix_data_quality_company_severity", "company_id", "severity"),
		Index("ix_data_quality_company_detected", "company_id", "detected_at"),
	)

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
	fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
	check_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
	issue_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
	severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
	module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
	record_type: Mapped[str] = mapped_column(String(40), nullable=False)
	record_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
	record_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	description: Mapped[str] = mapped_column(Text, nullable=False)
	details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
	status: Mapped[str] = mapped_column(String(20), nullable=False, default="Open", index=True)
	detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
	last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
	last_seen_run_id: Mapped[int | None] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
	resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
	resolved_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
	resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataQualityIssueEvent(Base):
	__tablename__ = "data_quality_issue_events"
	__table_args__ = (Index("ix_data_quality_issue_events_company_issue", "company_id", "issue_id"),)

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
	issue_id: Mapped[int] = mapped_column(ForeignKey("data_quality_issues.id", ondelete="CASCADE"), nullable=False, index=True)
	changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
	changed_by_name: Mapped[str] = mapped_column(String(255), nullable=False)
	previous_status: Mapped[str] = mapped_column(String(20), nullable=False)
	new_status: Mapped[str] = mapped_column(String(20), nullable=False)
	note: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())