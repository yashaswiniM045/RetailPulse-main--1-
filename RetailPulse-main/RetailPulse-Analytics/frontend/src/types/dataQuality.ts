export type DataQualityStatus = "Open" | "Investigating" | "Resolved" | "Ignored";
export type ReconciliationStatus = "Running" | "Completed" | "Completed with Issues" | "Failed";

export interface DataQualityOverview {
	recordsChecked: number;
	validRecords: number;
	warningRecords: number;
	errorRecords: number;
	unresolvedIssues: number;
	lastReconciliationAt: string | null;
	lastRunStatus: ReconciliationStatus | null;
}

export interface DataQualityIssue {
	id: number;
	issueType: string;
	severity: "warning" | "error";
	module: string;
	recordType: string;
	recordId: string;
	recordName: string | null;
	description: string;
	details: Record<string, unknown>;
	status: DataQualityStatus;
	detectedAt: string;
	lastSeenAt: string;
	resolvedAt: string | null;
	resolvedBy: string | null;
	resolutionNote: string | null;
}

export interface IssueEvent {
	id: number;
	changedBy: string;
	previousStatus: DataQualityStatus;
	newStatus: DataQualityStatus;
	note: string | null;
	createdAt: string;
}

export interface IssueDetail {
	issue: DataQualityIssue;
	context: {
		product?: Record<string, unknown> | null;
		inventory?: Record<string, unknown> | null;
		stockMovements?: Array<Record<string, unknown>>;
		relatedSales?: Array<Record<string, unknown>>;
		customer?: Record<string, unknown> | null;
		sale?: Record<string, unknown> | null;
	};
	events: IssueEvent[];
}

export interface DataQualityIssueFilters {
	search?: string;
	issueType?: string;
	severity?: string;
	module?: string;
	status?: DataQualityStatus | "";
	startDate?: string;
	endDate?: string;
}

export interface DataQualityPage<T> {
	items: T[];
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
}

export interface ReconciliationCheckResult {
	key: string;
	name: string;
	status: "Completed" | "Failed";
	issuesFound: number;
	error?: string;
}

export interface ReconciliationRun {
	id: number;
	triggeredBy: string;
	startedAt: string;
	completedAt: string | null;
	recordsChecked: number;
	validRecords: number;
	warningCount: number;
	errorCount: number;
	issuesDetected: number;
	issuesResolved: number;
	failedChecks: number;
	status: ReconciliationStatus;
	checkResults: ReconciliationCheckResult[];
	errorMessage: string | null;
}

export interface ReconciliationResult {
	run: ReconciliationRun;
	newIssues: number;
	updatedIssues: number;
}

export interface DataQualityFilterOptions {
	issueTypes: string[];
	severities: string[];
	modules: string[];
	statuses: DataQualityStatus[];
}