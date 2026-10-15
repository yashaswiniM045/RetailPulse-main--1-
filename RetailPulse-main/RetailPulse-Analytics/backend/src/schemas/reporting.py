from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

ReportType = Literal["sales", "inventory", "customers", "product-performance", "stock-movement"]
ReportFormat = Literal["csv", "pdf"]
ReportFrequency = Literal["daily", "weekly", "monthly"]


class ReportFilters(BaseModel):
	start_date: datetime | None = Field(default=None, alias="startDate")
	end_date: datetime | None = Field(default=None, alias="endDate")
	product_id: int | None = Field(default=None, alias="productId", gt=0)
	category_id: int | None = Field(default=None, alias="categoryId", gt=0)
	brand: str | None = None
	customer_id: int | None = Field(default=None, alias="customerId", gt=0)
	sales_status: Literal["pending", "paid", "failed", "refunded", "active", "inactive"] | None = Field(default=None, alias="salesStatus")
	stock_status: Literal["in-stock", "low-stock", "out-of-stock"] | None = Field(default=None, alias="stockStatus")
	user_id: int | None = Field(default=None, alias="userId", gt=0)

	model_config = ConfigDict(populate_by_name=True)

	@model_validator(mode="after")
	def validate_date_range(self):
		if self.start_date and self.end_date and self.start_date > self.end_date:
			raise ValueError("startDate must be earlier than or equal to endDate")
		return self


class ReportGenerateRequest(BaseModel):
	report_type: ReportType = Field(alias="reportType")
	filters: ReportFilters = Field(default_factory=ReportFilters)

	model_config = ConfigDict(populate_by_name=True)


class ScheduleCreate(BaseModel):
	name: str = Field(min_length=1, max_length=255)
	report_type: ReportType = Field(alias="reportType")
	filters: ReportFilters = Field(default_factory=ReportFilters)
	frequency: ReportFrequency
	execution_time: str = Field(alias="executionTime", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
	recipients: list[EmailStr] = Field(min_length=1, max_length=20)
	export_format: ReportFormat = Field(alias="exportFormat")
	is_active: bool = Field(default=True, alias="isActive")

	model_config = ConfigDict(populate_by_name=True)

	@model_validator(mode="after")
	def validate_values(self):
		if not self.name.strip():
			raise ValueError("Schedule name is required")
		if self.frequency not in {"daily", "weekly", "monthly"}:
			raise ValueError("Unsupported schedule frequency")
		self.recipients = list(dict.fromkeys(str(email).lower() for email in self.recipients))
		return self


class ScheduleUpdate(ScheduleCreate):
	pass


class ReportHistoryRead(BaseModel):
	model_config = ConfigDict(from_attributes=True, populate_by_name=True)

	id: int
	company_id: int = Field(alias="companyId")
	generated_by_id: int | None = Field(alias="generatedById")
	generated_by_name: str = Field(alias="generatedBy")
	schedule_id: int | None = Field(alias="scheduleId")
	report_type: str = Field(alias="reportType")
	filters: dict
	total_rows: int = Field(alias="totalRows")
	export_format: str = Field(alias="format")
	status: str
	error_message: str | None = Field(alias="errorMessage")
	created_at: datetime = Field(alias="createdAt")


class ScheduledReportRead(BaseModel):
	model_config = ConfigDict(from_attributes=True, populate_by_name=True)

	id: int
	name: str
	report_type: str = Field(alias="reportType")
	filters: dict
	frequency: str
	execution_time: str = Field(alias="executionTime")
	recipients: list[str]
	export_format: str = Field(alias="exportFormat")
	is_active: bool = Field(alias="isActive")
	next_run_at: datetime = Field(alias="nextRunAt")
	last_run_at: datetime | None = Field(alias="lastRunAt")
	last_status: str | None = Field(alias="lastStatus")
	last_error: str | None = Field(alias="lastError")
	last_history_id: int | None = Field(alias="lastHistoryId")
	created_at: datetime = Field(alias="createdAt")


class ReportPageRead(BaseModel):
	items: list[dict]
	total: int
	page: int
	page_size: int = Field(alias="pageSize")
	total_pages: int = Field(alias="totalPages")


class ReportResultRead(BaseModel):
	history: ReportHistoryRead
	page: ReportPageRead