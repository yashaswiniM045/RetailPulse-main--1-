export type ReportType = "sales" | "inventory" | "customers" | "product-performance" | "stock-movement";
export type ReportFormat = "csv" | "pdf";
export type ReportFrequency = "daily" | "weekly" | "monthly";

export interface ReportFilters {
	startDate?: string;
	endDate?: string;
	productId?: number;
	categoryId?: number;
	brand?: string;
	customerId?: number;
	salesStatus?: string;
	stockStatus?: string;
	userId?: number;
}

export interface ReportFilterOptions {
	products: Array<{ id: number; name: string }>;
	categories: Array<{ id: number; name: string }>;
	brands: string[];
	customers: Array<{ id: number; name: string }>;
	users: Array<{ id: number; name: string }>;
}

export interface ReportHistory {
	id: number;
	companyId: number;
	generatedById: number | null;
	generatedBy: string;
	scheduleId: number | null;
	reportType: ReportType;
	filters: ReportFilters;
	totalRows: number;
	format: string;
	status: "success" | "failed";
	errorMessage: string | null;
	createdAt: string;
}

export interface ReportPage {
	items: Array<Record<string, string | number | null>>;
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
}

export interface ReportResult {
	history: ReportHistory;
	page: ReportPage;
}

export interface ScheduledReport {
	id: number;
	name: string;
	reportType: ReportType;
	filters: ReportFilters;
	frequency: ReportFrequency;
	executionTime: string;
	recipients: string[];
	exportFormat: ReportFormat;
	isActive: boolean;
	nextRunAt: string;
	lastRunAt: string | null;
	lastStatus: "success" | "failed" | null;
	lastError: string | null;
	lastHistoryId: number | null;
	createdAt: string;
}

export interface SchedulePayload {
	name: string;
	reportType: ReportType;
	filters: ReportFilters;
	frequency: ReportFrequency;
	executionTime: string;
	recipients: string[];
	exportFormat: ReportFormat;
	isActive: boolean;
}