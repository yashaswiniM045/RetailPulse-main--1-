from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ReportHistory(Base):
	__tablename__ = "report_history"

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
	generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
	generated_by_name: Mapped[str] = mapped_column(String(255), nullable=False)
	schedule_id: Mapped[int | None] = mapped_column(ForeignKey("scheduled_reports.id", ondelete="SET NULL"), nullable=True)
	report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
	filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
	total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	export_format: Mapped[str] = mapped_column(String(20), nullable=False, default="view")
	status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", index=True)
	error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class ScheduledReport(Base):
	__tablename__ = "scheduled_reports"

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
	created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	report_type: Mapped[str] = mapped_column(String(50), nullable=False)
	filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
	frequency: Mapped[str] = mapped_column(String(20), nullable=False)
	execution_time: Mapped[str] = mapped_column(String(5), nullable=False)
	recipients: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
	export_format: Mapped[str] = mapped_column(String(10), nullable=False)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
	last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
	last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
	last_history_id: Mapped[int | None] = mapped_column(ForeignKey("report_history.id", ondelete="SET NULL"), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)