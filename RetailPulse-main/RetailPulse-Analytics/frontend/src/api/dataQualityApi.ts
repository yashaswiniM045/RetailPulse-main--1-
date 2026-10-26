import { apiClient } from "./axios";
import {
	DataQualityIssue,
	DataQualityIssueFilters,
	DataQualityFilterOptions,
	DataQualityOverview,
	DataQualityPage,
	DataQualityStatus,
	IssueDetail,
	ReconciliationResult,
	ReconciliationRun,
} from "../types/dataQuality";

export async function getDataQualityOverview() {
	const response = await apiClient.get<DataQualityOverview>("/data-quality/overview");
	return response.data;
}

export async function getDataQualityFilterOptions() {
	const response = await apiClient.get<DataQualityFilterOptions>("/data-quality/issues/options");
	return response.data;
}

export async function getDataQualityIssues(filters: DataQualityIssueFilters, page: number, pageSize = 25) {
	const response = await apiClient.get<DataQualityPage<DataQualityIssue>>("/data-quality/issues", {
		params: {
			...filters,
			page,
			pageSize,
			search: filters.search || undefined,
			issueType: filters.issueType || undefined,
			severity: filters.severity || undefined,
			module: filters.module || undefined,
			status: filters.status || undefined,
		},
	});
	return response.data;
}

export async function getDataQualityIssueDetail(issueId: number) {
	const response = await apiClient.get<IssueDetail>(`/data-quality/issues/${issueId}`);
	return response.data;
}

export async function updateDataQualityIssueStatus(issueId: number, status: DataQualityStatus, resolutionNote?: string) {
	const response = await apiClient.patch<DataQualityIssue>(`/data-quality/issues/${issueId}/status`, { status, resolutionNote });
	return response.data;
}

export async function runDataQualityReconciliation() {
	const response = await apiClient.post<ReconciliationResult>("/data-quality/reconcile");
	return response.data;
}

export async function getReconciliationHistory(page = 1, pageSize = 25) {
	const response = await apiClient.get<DataQualityPage<ReconciliationRun>>("/data-quality/history", { params: { page, pageSize } });
	return response.data;
}