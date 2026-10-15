import { apiClient } from "./axios";
import { ReportFilters, ReportFilterOptions, ReportFormat, ReportHistory, ReportPage, ReportResult, ReportType, SchedulePayload, ScheduledReport } from "../types/reporting";

function normalizeHistory(data: Record<string, unknown>): ReportHistory {
	return {
		id: Number(data.id),
		companyId: Number(data.companyId ?? data.company_id),
		generatedById: (data.generatedById ?? data.generated_by_id) as number | null,
		generatedBy: String(data.generatedBy ?? data.generated_by_name ?? ""),
		scheduleId: (data.scheduleId ?? data.schedule_id) as number | null,
		reportType: (data.reportType ?? data.report_type) as ReportType,
		filters: (data.filters ?? {}) as ReportFilters,
		totalRows: Number(data.totalRows ?? data.total_rows ?? 0),
		format: String(data.format ?? data.export_format ?? "view"),
		status: (data.status as ReportHistory["status"]) ?? "success",
		errorMessage: (data.errorMessage ?? data.error_message) as string | null,
		createdAt: String(data.createdAt ?? data.created_at ?? ""),
	};
}

function normalizePage(data: Record<string, unknown>): ReportPage {
	return {
		items: (data.items as ReportPage["items"]) ?? [],
		total: Number(data.total ?? 0),
		page: Number(data.page ?? 1),
		pageSize: Number(data.pageSize ?? data.page_size ?? 25),
		totalPages: Number(data.totalPages ?? data.total_pages ?? 0),
	};
}

function normalizeResult(data: Record<string, unknown>): ReportResult {
	return {
		history: normalizeHistory(data.history as Record<string, unknown>),
		page: normalizePage(data.page as Record<string, unknown>),
	};
}

function normalizeSchedule(data: Record<string, unknown>): ScheduledReport {
	return {
		id: Number(data.id),
		name: String(data.name ?? ""),
		reportType: (data.reportType ?? data.report_type) as ReportType,
		filters: (data.filters ?? {}) as ReportFilters,
		frequency: (data.frequency ?? "daily") as ScheduledReport["frequency"],
		executionTime: String(data.executionTime ?? data.execution_time ?? "09:00"),
		recipients: (data.recipients as string[]) ?? [],
		exportFormat: (data.exportFormat ?? data.export_format) as ReportFormat,
		isActive: Boolean(data.isActive ?? data.is_active),
		nextRunAt: String(data.nextRunAt ?? data.next_run_at ?? ""),
		lastRunAt: (data.lastRunAt ?? data.last_run_at) as string | null,
		lastStatus: (data.lastStatus ?? data.last_status) as ScheduledReport["lastStatus"],
		lastError: (data.lastError ?? data.last_error) as string | null,
		lastHistoryId: (data.lastHistoryId ?? data.last_history_id) as number | null,
		createdAt: String(data.createdAt ?? data.created_at ?? ""),
	};
}

export async function getReportFilters() {
	const response = await apiClient.get<ReportFilterOptions>("/reports/filters");
	return response.data;
}

export async function generateReport(reportType: ReportType, filters: ReportFilters) {
	const response = await apiClient.post<Record<string, unknown>>("/reports/generate", { reportType, filters });
	return normalizeResult(response.data);
}

export async function getReportHistory(page = 1, pageSize = 25) {
	const response = await apiClient.get<Record<string, unknown>>("/reports/history", { params: { page, pageSize } });
	return { ...normalizePage(response.data), items: (response.data.items as Record<string, unknown>[]).map(normalizeHistory) };
}

export async function getReportHistoryDetail(id: number, page: number, pageSize: number, sortBy?: string, sortDirection: "asc" | "desc" = "asc") {
	const response = await apiClient.get<Record<string, unknown>>(`/reports/history/${id}`, { params: { page, pageSize, sortBy, sortDirection } });
	return normalizeResult(response.data);
}

export async function exportReport(id: number, format: ReportFormat) {
	const response = await apiClient.get<Blob>(`/reports/history/${id}/export`, { params: { format }, responseType: "blob" });
	return response.data;
}

export async function listScheduledReports() {
	const response = await apiClient.get<Record<string, unknown>[]>("/reports/schedules");
	return response.data.map(normalizeSchedule);
}

export async function createScheduledReport(payload: SchedulePayload) {
	const response = await apiClient.post<Record<string, unknown>>("/reports/schedules", payload);
	return normalizeSchedule(response.data);
}

export async function updateScheduledReport(id: number, payload: SchedulePayload) {
	const response = await apiClient.put<Record<string, unknown>>(`/reports/schedules/${id}`, payload);
	return normalizeSchedule(response.data);
}

export async function setScheduledReportActive(id: number, isActive: boolean) {
	const response = await apiClient.patch<Record<string, unknown>>(`/reports/schedules/${id}/status`, null, { params: { isActive } });
	return normalizeSchedule(response.data);
}

export async function deleteScheduledReport(id: number) {
	await apiClient.delete(`/reports/schedules/${id}`);
}