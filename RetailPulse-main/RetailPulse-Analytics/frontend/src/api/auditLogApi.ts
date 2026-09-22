import { apiClient } from "./axios";

export interface AuditLogItem {
	id: number;
	userName: string | null;
	userEmail: string | null;
	action: string;
	resourceType: string | null;
	resourceId: string | null;
	resourceName: string | null;
	description: string | null;
	ipAddress: string | null;
	userAgent: string | null;
	timestamp: string;
	status: string;
	beforeValues: Record<string, unknown> | null;
	afterValues: Record<string, unknown> | null;
}

export interface AuditLogPage {
	items: AuditLogItem[];
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
}

export interface AuditLogFilters {
	page?: number;
	pageSize?: number;
	userId?: number;
	action?: string;
	resourceType?: string;
	status?: string;
	startDate?: string;
	endDate?: string;
	search?: string;
	sortOrder?: "asc" | "desc";
}

export interface AuditUserOption {
	id: number;
	name: string;
	email: string;
}

function params(filters: AuditLogFilters) {
	return {
		page: filters.page,
		page_size: filters.pageSize,
		user_id: filters.userId,
		action: filters.action || undefined,
		resource_type: filters.resourceType || undefined,
		status: filters.status || undefined,
		start_date: filters.startDate ? `${filters.startDate}T00:00:00` : undefined,
		end_date: filters.endDate ? `${filters.endDate}T23:59:59` : undefined,
		search: filters.search || undefined,
		sort_order: filters.sortOrder,
	};
}

export async function listAuditLogs(filters: AuditLogFilters = {}) {
	const response = await apiClient.get<AuditLogPage>("/audit-logs", { params: params(filters) });
	return response.data;
}

export async function listAuditUsers() {
	const response = await apiClient.get<AuditUserOption[]>("/users");
	return response.data;
}

export async function getAuditLog(id: number) {
	const response = await apiClient.get<AuditLogItem>(`/audit-logs/${id}`);
	return response.data;
}

async function downloadAuditLogs(format: "csv" | "pdf", filters: AuditLogFilters) {
	const response = await apiClient.get(`/audit-logs/export.${format}`, { params: params(filters), responseType: "blob" });
	const url = URL.createObjectURL(response.data);
	const link = document.createElement("a");
	link.href = url;
	link.download = `audit-logs.${format}`;
	link.click();
	URL.revokeObjectURL(url);
}

export const exportAuditLogsCsv = (filters: AuditLogFilters) => downloadAuditLogs("csv", filters);
export const exportAuditLogsPdf = (filters: AuditLogFilters) => downloadAuditLogs("pdf", filters);
