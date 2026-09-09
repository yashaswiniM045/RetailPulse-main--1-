import { apiClient } from "./axios";

export type ImportType = "products" | "customers" | "sales";

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
	status: string;
	createdAt: string;
	completedAt: string | null;
}

export interface ImportProcessResult {
	importId: number;
	totalRecords: number;
	successfullyAdded: number;
	failedRecords: number;
	duplicateRecords: number;
	validationFailures: number;
	status: string;
	errors: ImportIssue[];
}

export async function uploadImportFile(importType: ImportType, file: File) {
	const formData = new FormData();
	formData.append("import_type", importType);
	formData.append("file", file);
	const response = await apiClient.post<{ filename: string; importType: string; columns: string[]; preview: Record<string, string>[]; summary: ImportValidationSummary }>(
		"/imports/upload",
		formData,
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
}

export async function validateImportRows(importType: ImportType, rows: Record<string, string>[]) {
	const response = await apiClient.post<ImportValidationSummary>("/imports/validate", {
		importType,
		rows,
	});
	return response.data;
}

export async function processImportRows(importType: ImportType, rows: Record<string, string>[], filename: string) {
	const response = await apiClient.post<ImportProcessResult>("/imports/process", {
		importType,
		rows,
		filename,
	});
	return response.data;
}

export async function getImportHistory() {
	const response = await apiClient.get<ImportHistoryItem[]>("/imports/history");
	return response.data;
}

export async function getImportById(importId: number) {
	const response = await apiClient.get<ImportHistoryItem & { errors: ImportIssue[] }>(`/imports/${importId}`);
	return response.data;
}

export async function getImportErrors(importId: number) {
	const response = await apiClient.get<Array<{ rowNumber: number | null; errorType: string; message: string; rowData: string | null }>>(`/imports/${importId}/errors`);
	return response.data;
}
