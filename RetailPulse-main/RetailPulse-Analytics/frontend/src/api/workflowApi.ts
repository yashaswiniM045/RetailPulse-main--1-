import { apiClient } from "./axios";

export type WorkflowRequestType =
	| "stock-adjustment"
	| "product-deactivation"
	| "product-price-change"
	| "customer-information-change"
	| "inventory-import-approval";

export type WorkflowStatus = "draft" | "submitted" | "pending-approval" | "approved" | "rejected" | "cancelled";

export interface ApprovalHistoryItem {
	id: number;
	action: string;
	actorId: number | null;
	actorName: string;
	comment: string | null;
	details: Record<string, unknown> | null;
	createdAt: string;
}

export interface WorkflowRequest {
	id: number;
	requestId: string;
	requestType: WorkflowRequestType;
	requestTypeLabel: string;
	requestedBy: { id: number; name: string; email: string };
	companyId: number;
	companyName: string;
	relatedRecordType: string;
	relatedRecordId: number;
	relatedRecord: { type: string; id: number; name: string; sku?: string; category?: string; email?: string; status?: string };
	currentValues: Record<string, unknown>;
	requestedChanges: Record<string, unknown>;
	reason: string;
	priority: "low" | "medium" | "high" | "critical";
	status: WorkflowStatus;
	approverRole: string;
	allowSelfApproval: boolean;
	createdAt: string;
	updatedAt: string;
	history: ApprovalHistoryItem[];
}

export interface WorkflowPage {
	items: WorkflowRequest[];
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
}

export interface WorkflowConfiguration {
	requestType: WorkflowRequestType;
	label: string;
	approverRole: string;
	approvalRequired: boolean;
	allowSelfApproval: boolean;
	isActive: boolean;
	updatedAt: string | null;
}

export async function listWorkflowRequests(filters: {
	scope: "all" | "mine" | "queue";
	requestType?: string;
	status?: string;
	search?: string;
	sortDirection?: "asc" | "desc";
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<WorkflowPage>("/workflows", {
		params: {
			scope: filters.scope,
			requestType: filters.requestType || undefined,
			status: filters.status || undefined,
			search: filters.search || undefined,
			sortDirection: filters.sortDirection,
			page: filters.page,
			pageSize: filters.pageSize,
		},
	});
	return response.data;
}

export async function createWorkflowRequest(payload: {
	requestType: WorkflowRequestType;
	relatedRecordId: number;
	requestedChanges: Record<string, unknown>;
	reason: string;
	priority: WorkflowRequest["priority"];
	draft?: boolean;
}) {
	const response = await apiClient.post<WorkflowRequest>("/workflows", payload);
	return response.data;
}

export async function submitWorkflowRequest(id: number) {
	const response = await apiClient.post<WorkflowRequest>(`/workflows/${id}/submit`);
	return response.data;
}

export async function getWorkflowRequest(id: number) {
	const response = await apiClient.get<WorkflowRequest>(`/workflows/${id}`);
	return response.data;
}

export async function approveWorkflowRequest(id: number, comment?: string) {
	const response = await apiClient.post<WorkflowRequest>(`/workflows/${id}/approve`, { comment });
	return response.data;
}

export async function rejectWorkflowRequest(id: number, comment: string) {
	const response = await apiClient.post<WorkflowRequest>(`/workflows/${id}/reject`, { comment });
	return response.data;
}

export async function cancelWorkflowRequest(id: number) {
	const response = await apiClient.post<WorkflowRequest>(`/workflows/${id}/cancel`);
	return response.data;
}

export async function listWorkflowConfigurations() {
	const response = await apiClient.get<WorkflowConfiguration[]>("/workflows/config");
	return response.data;
}

export async function updateWorkflowConfiguration(
	requestType: WorkflowRequestType,
	payload: Pick<WorkflowConfiguration, "approverRole" | "approvalRequired" | "allowSelfApproval" | "isActive">,
) {
	const response = await apiClient.put<WorkflowConfiguration>(`/workflows/config/${requestType}`, payload);
	return response.data;
}

export async function getPendingWorkflowCount() {
	const response = await apiClient.get<{ pendingApprovalCount: number; myOpenRequestCount: number }>("/workflows/pending-count");
	return response.data;
}
