import { apiClient } from "./axios";

export type ImportType = "products" | "inventory" | "customers" | "sales";

export interface ImportIssue {
	rowNumber: number | null;
	row: Record<string, string>;
	message: string;
	errorType: string;
}

export interface ImportValidationSummary {
	totalRecords: number;
	validCount: number;
	invalidCount: number;
	duplicateCount: number;
	missingColumns: string[];
	issues: ImportIssue[];
	preview: Record<string, string>[];
}

export interface ImportHistoryItem {
	id: number;
	importType: string;
	filename: string;
	uploadedBy: string;
	totalRecords: number;
	successfulRecords: number;
	failedRecords: number;
	duplicateRecords: number;
	skippedRecords?: number;
	durationSeconds?: number | null;
	status: string;
	createdAt: string;
	completedAt: string | null;
}

export interface ImportProcessResult {
	importId: number;
	importType: string;
	filename: string;
	uploadedBy: string;
	totalRecords: number;
	successfullyAdded: number;
	successfulRecords: number;
	failedRecords: number;
	duplicateRecords: number;
	skippedRecords: number;
	processedRecords: number;
	progressPercent: number;
	status: string;
	createdAt: string;
	startedAt: string | null;
	completedAt: string | null;
	durationSeconds: number | null;
}

export interface ImportUploadResult {
	importId: number;
	filename: string;
	importType: ImportType;
	columns: string[];
	preview: Record<string, string>[];
	summary: ImportValidationSummary;
	status: string;
}

export async function uploadImportFile(importType: ImportType, file: File) {
	const formData = new FormData();
	formData.append("import_type", importType);
	formData.append("file", file);
	const response = await apiClient.post<ImportUploadResult>("/imports/upload", formData);
	return response.data;
}

export async function downloadImportTemplate(importType: ImportType) {
	const response = await apiClient.get(`/imports/templates/${importType}`, { responseType: "blob" });
	return response.data as Blob;
}

export async function startImport(importId: number) {
	const response = await apiClient.post<ImportProcessResult>(`/imports/${importId}/start`);
	return response.data;
}

export async function getImportHistory() {
	const response = await apiClient.get<ImportHistoryItem[]>("/imports/history");
	return response.data;
}

export async function getImportById(importId: number) {
	const response = await apiClient.get<ImportProcessResult & {
		errors: ImportIssue[];
		validationSummary?: ImportValidationSummary | null;
	}>(`/imports/${importId}`);
	return response.data;
}

export async function getImportStatus(importId: number) {
	const response = await apiClient.get<ImportProcessResult>(`/imports/${importId}/status`);
	return response.data;
}

export async function cancelImport(importId: number) {
	const response = await apiClient.post<ImportProcessResult>(`/imports/${importId}/cancel`);
	return response.data;
}

export async function downloadImportErrorReport(importId: number) {
	const response = await apiClient.get(`/imports/${importId}/errors.csv`, { responseType: "blob" });
	return response.data as Blob;
}
