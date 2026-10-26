import FactCheckRoundedIcon from "@mui/icons-material/FactCheckRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";
import {
	Alert,
	Box,
	Button,
	Chip,
	CircularProgress,
	Dialog,
	DialogActions,
	DialogContent,
	DialogTitle,
	IconButton,
	MenuItem,
	Paper,
	Stack,
	Tab,
	Table,
	TableBody,
	TableCell,
	TableHead,
	TablePagination,
	TableRow,
	Tabs,
	TextField,
	Tooltip,
	Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
	getDataQualityFilterOptions,
	getDataQualityIssueDetail,
	getDataQualityIssues,
	getDataQualityOverview,
	getReconciliationHistory,
	runDataQualityReconciliation,
	updateDataQualityIssueStatus,
} from "../../api/dataQualityApi";
import { useAuth } from "../../context/AuthContext";
import { DataQualityIssue, DataQualityIssueFilters, DataQualityStatus } from "../../types/dataQuality";

const statusOptions: DataQualityStatus[] = ["Open", "Investigating", "Resolved", "Ignored"];

function formatDate(value?: string | null) {
	return value ? new Date(value).toLocaleString() : "Not run yet";
}

function displayValue(value: unknown): string {
	if (value === null || value === undefined || value === "") return "-";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
}

function humanizeIssueType(value: string) {
	return value.replace(/_/g, " ");
}

function ContextBlock({ title, value }: { title: string; value: unknown }) {
	if (value === null || value === undefined) return null;
	const rows = Array.isArray(value) ? value : [value];
	return <Box>
		<Typography variant="subtitle2" fontWeight={800} sx={{ mb: 0.75 }}>{title}</Typography>
		{rows.length === 0 ? <Typography variant="body2" color="text.secondary">No related records.</Typography> : rows.map((row, index) => (
			<Paper key={index} variant="outlined" sx={{ p: 1.25, mb: 1, borderRadius: 1 }}>
				{typeof row === "object" && row !== null ? Object.entries(row).map(([key, entry]) => <Typography key={key} variant="body2" sx={{ overflowWrap: "anywhere" }}><Box component="span" sx={{ color: "text.secondary", mr: 0.75 }}>{key}:</Box>{displayValue(entry)}</Typography>) : <Typography variant="body2">{displayValue(row)}</Typography>}
			</Paper>
		))}
	</Box>;
}

export default function DataQualityPage() {
	const queryClient = useQueryClient();
	const { user } = useAuth();
	const canReconcile = user?.role === "Company Admin" || user?.role === "Super Admin" || user?.role === "Analyst";
	const [tab, setTab] = useState(0);
	const [page, setPage] = useState(0);
	const [historyPage, setHistoryPage] = useState(0);
	const [filters, setFilters] = useState<DataQualityIssueFilters>({});
	const [selectedIssue, setSelectedIssue] = useState<DataQualityIssue | null>(null);
	const [nextStatus, setNextStatus] = useState<DataQualityStatus>("Investigating");
	const [resolutionNote, setResolutionNote] = useState("");
	const [mutationError, setMutationError] = useState("");
	const [runMessage, setRunMessage] = useState("");
	const filterOptionsQuery = useQuery({ queryKey: ["data-quality-options"], queryFn: getDataQualityFilterOptions });
	const overviewQuery = useQuery({ queryKey: ["data-quality-overview"], queryFn: getDataQualityOverview });
	const issuesQuery = useQuery({
		queryKey: ["data-quality-issues", filters, page],
		queryFn: () => getDataQualityIssues(filters, page + 1, 25),
		enabled: tab === 0,
	});
	const historyQuery = useQuery({
		queryKey: ["data-quality-history", historyPage],
		queryFn: () => getReconciliationHistory(historyPage + 1, 25),
		enabled: tab === 1,
	});
	const detailQuery = useQuery({
		queryKey: ["data-quality-issue-detail", selectedIssue?.id],
		queryFn: () => getDataQualityIssueDetail(selectedIssue!.id),
		enabled: Boolean(selectedIssue),
	});

	const refreshQuality = async () => {
		await Promise.all([
			queryClient.invalidateQueries({ queryKey: ["data-quality-overview"] }),
			queryClient.invalidateQueries({ queryKey: ["data-quality-issues"] }),
			queryClient.invalidateQueries({ queryKey: ["data-quality-history"] }),
			queryClient.invalidateQueries({ queryKey: ["data-quality-issue-detail"] }),
		]);
	};

	const reconcileMutation = useMutation({
		mutationFn: runDataQualityReconciliation,
		onMutate: () => { setMutationError(""); setRunMessage(""); },
		onSuccess: async (result) => {
			setRunMessage(`Run ${result.run.id} ${result.run.status.toLowerCase()}: ${result.newIssues} new, ${result.updatedIssues} updated, ${result.run.issuesResolved} resolved, ${result.run.failedChecks} checks failed.`);
			await refreshQuality();
		},
		onError: (error) => setMutationError(error instanceof Error ? error.message : "Reconciliation failed."),
	});
	const statusMutation = useMutation({
		mutationFn: ({ id, status, note }: { id: number; status: DataQualityStatus; note?: string }) => updateDataQualityIssueStatus(id, status, note),
		onMutate: () => setMutationError(""),
		onSuccess: async () => { setSelectedIssue(null); setResolutionNote(""); await refreshQuality(); },
		onError: (error) => setMutationError(error instanceof Error ? error.message : "Unable to update issue status."),
	});

	const updateFilter = (key: keyof DataQualityIssueFilters, value: string) => {
		const normalized = key === "endDate" && value ? `${value}T23:59:59` : value;
		setFilters((current) => ({ ...current, [key]: normalized || undefined }));
		setPage(0);
	};
	const openIssue = (issue: DataQualityIssue) => {
		setSelectedIssue(issue);
		setNextStatus(issue.status === "Open" ? "Investigating" : issue.status);
		setResolutionNote(issue.resolutionNote ?? "");
		setMutationError("");
	};
	const applyStatus = () => {
		if (!selectedIssue) return;
		if (nextStatus === "Resolved" && !resolutionNote.trim()) {
			setMutationError("A resolution note is required to resolve an issue.");
			return;
		}
		statusMutation.mutate({ id: selectedIssue.id, status: nextStatus, note: resolutionNote.trim() || undefined });
	};
	const issues = issuesQuery.data?.items ?? [];
	const history = historyQuery.data?.items ?? [];
	const detail = detailQuery.data;
	const overview = overviewQuery.data;
	const filterOptions = filterOptionsQuery.data;

	return <Stack spacing={2.5}>
		<Box sx={{ display: "flex", justifyContent: "space-between", alignItems: { xs: "flex-start", sm: "center" }, gap: 2, flexWrap: "wrap" }}>
			<Box><Typography variant="h4" fontWeight={850}>Data Quality</Typography><Typography color="text.secondary" sx={{ mt: 0.5 }}>Reconcile business records, investigate mismatches, and track fixes.</Typography></Box>
			<Stack direction="row" spacing={1}>
				<Button startIcon={<RefreshRoundedIcon />} onClick={() => { void overviewQuery.refetch(); void issuesQuery.refetch(); void historyQuery.refetch(); }}>Refresh</Button>
				{canReconcile && <Button variant="contained" startIcon={reconcileMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <PlayArrowRoundedIcon />} disabled={reconcileMutation.isPending} onClick={() => reconcileMutation.mutate()}>{reconcileMutation.isPending ? "Reconciling…" : "Run reconciliation"}</Button>}
			</Stack>
		</Box>
		{mutationError && !selectedIssue && <Alert severity="error" onClose={() => setMutationError("")}>{mutationError}</Alert>}
		{runMessage && <Alert severity="success" onClose={() => setRunMessage("")}>{runMessage}</Alert>}
		{reconcileMutation.isPending && <Alert severity="info" icon={<CircularProgress size={18} />}>Reconciliation is running against company records. This view will refresh when checks complete.</Alert>}
		{overviewQuery.isError && <Alert severity="error">Data quality overview could not be loaded.</Alert>}
		{overviewQuery.isLoading ? <Box sx={{ py: 4, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box> : overview && <>
			<Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", md: "repeat(5, minmax(0, 1fr))" }, gap: 1.5 }}>
				{[
					{ label: "Records checked", value: overview.recordsChecked, color: "#245d72" },
					{ label: "Valid records", value: overview.validRecords, color: "#34735c" },
					{ label: "Warnings", value: overview.warningRecords, color: "#b1781d" },
					{ label: "Errors", value: overview.errorRecords, color: "#aa4c40" },
					{ label: "Unresolved", value: overview.unresolvedIssues, color: "#6b5d86" },
				].map((kpi) => <Paper key={kpi.label} variant="outlined" sx={{ px: 2, py: 1.75, borderRadius: 1.5, borderTop: `3px solid ${kpi.color}` }}>
					<Typography variant="caption" color="text.secondary" fontWeight={700}>{kpi.label}</Typography>
					<Typography variant="h5" fontWeight={850}>{kpi.value.toLocaleString()}</Typography>
				</Paper>)}
			</Box>
			<Stack direction="row" alignItems="center" spacing={1} sx={{ color: "text.secondary" }}><FactCheckRoundedIcon fontSize="small" /><Typography variant="body2">Last reconciliation: {formatDate(overview.lastReconciliationAt)}{overview.lastRunStatus ? ` · ${overview.lastRunStatus}` : ""}</Typography></Stack>
		</>}
		<Paper variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
			<Tabs value={tab} onChange={(_, value: number) => setTab(value)} sx={{ px: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
				<Tab label="Issues" />
				<Tab label="Reconciliation history" />
			</Tabs>
			{tab === 0 && <Stack spacing={2} sx={{ p: { xs: 2, md: 3 } }}>
				<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" }, gap: 1.25 }}>
					<TextField size="small" label="Search issues" value={filters.search ?? ""} onChange={(event) => updateFilter("search", event.target.value)} InputProps={{ startAdornment: <SearchRoundedIcon fontSize="small" sx={{ mr: 1, color: "text.secondary" }} /> }} />
					<TextField select size="small" label="Issue type" value={filters.issueType ?? ""} onChange={(event) => updateFilter("issueType", event.target.value)}><MenuItem value="">All types</MenuItem>{(filterOptions?.issueTypes ?? []).map((value) => <MenuItem key={value} value={value}>{humanizeIssueType(value)}</MenuItem>)}</TextField>
					<TextField select size="small" label="Severity" value={filters.severity ?? ""} onChange={(event) => updateFilter("severity", event.target.value)}><MenuItem value="">All severities</MenuItem>{(filterOptions?.severities ?? ["error", "warning"]).map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
					<TextField select size="small" label="Module" value={filters.module ?? ""} onChange={(event) => updateFilter("module", event.target.value)}><MenuItem value="">All modules</MenuItem>{(filterOptions?.modules ?? []).map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
					<TextField select size="small" label="Status" value={filters.status ?? ""} onChange={(event) => updateFilter("status", event.target.value)}><MenuItem value="">All statuses</MenuItem>{statusOptions.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
					<TextField label="Detected from" type="date" size="small" value={filters.startDate ?? ""} onChange={(event) => updateFilter("startDate", event.target.value)} InputLabelProps={{ shrink: true }} />
					<TextField label="Detected to" type="date" size="small" value={filters.endDate?.slice(0, 10) ?? ""} onChange={(event) => updateFilter("endDate", event.target.value)} InputLabelProps={{ shrink: true }} />
				</Box>
				{issuesQuery.isError && <Alert severity="error">Issues could not be loaded.</Alert>}
				{issuesQuery.isLoading ? <Box sx={{ py: 4, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box> : issues.length === 0 ? <Alert severity="info">No issues match the selected filters.</Alert> : <Box sx={{ overflowX: "auto" }}>
					<Table size="small"><TableHead><TableRow><TableCell>ID</TableCell><TableCell>Issue</TableCell><TableCell>Severity</TableCell><TableCell>Module</TableCell><TableCell>Affected record</TableCell><TableCell>Description</TableCell><TableCell>Detected</TableCell><TableCell>Status</TableCell><TableCell align="right">Details</TableCell></TableRow></TableHead>
						<TableBody>{issues.map((issue) => <TableRow key={issue.id} hover sx={{ cursor: "pointer" }} onClick={() => openIssue(issue)}>
							<TableCell>DQ-{issue.id}</TableCell><TableCell sx={{ whiteSpace: "nowrap" }}>{humanizeIssueType(issue.issueType)}</TableCell><TableCell><Chip size="small" label={issue.severity} color={issue.severity === "error" ? "error" : "warning"} /></TableCell><TableCell>{issue.module}</TableCell><TableCell sx={{ minWidth: 130 }}>{issue.recordName || issue.recordType} <Typography variant="caption" display="block" color="text.secondary">{issue.recordType} #{issue.recordId}</Typography></TableCell><TableCell sx={{ minWidth: 240, maxWidth: 360 }}>{issue.description}</TableCell><TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(issue.detectedAt)}</TableCell><TableCell><Chip size="small" variant="outlined" label={issue.status} /></TableCell><TableCell align="right"><Tooltip title="Investigate"><IconButton aria-label={`Open issue ${issue.id}`} onClick={(event) => { event.stopPropagation(); openIssue(issue); }}><VisibilityRoundedIcon /></IconButton></Tooltip></TableCell>
						</TableRow>)}</TableBody>
					</Table>
				</Box>}
				{issuesQuery.data && <TablePagination component="div" count={issuesQuery.data.total} page={page} onPageChange={(_, value) => setPage(value)} rowsPerPage={25} rowsPerPageOptions={[25]} />}
			</Stack>}
			{tab === 1 && <Stack spacing={2} sx={{ p: { xs: 2, md: 3 } }}>
				<Box><Typography variant="h6" fontWeight={800}>Reconciliation history</Typography><Typography variant="body2" color="text.secondary">Manual runs and their per-check results.</Typography></Box>
				{historyQuery.isError && <Alert severity="error">Reconciliation history could not be loaded.</Alert>}
				{historyQuery.isLoading ? <Box sx={{ py: 4, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box> : history.length === 0 ? <Alert severity="info">No reconciliation runs yet. Run a check to establish the baseline.</Alert> : <Box sx={{ overflowX: "auto" }}>
					<Table size="small"><TableHead><TableRow><TableCell>Execution</TableCell><TableCell>Started</TableCell><TableCell>Completed</TableCell><TableCell>Triggered by</TableCell><TableCell>Records</TableCell><TableCell>Issues found</TableCell><TableCell>Resolved</TableCell><TableCell>Failed checks</TableCell><TableCell>Status</TableCell></TableRow></TableHead><TableBody>
						{history.map((run) => <TableRow key={run.id} hover><TableCell>RC-{run.id}</TableCell><TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(run.startedAt)}</TableCell><TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(run.completedAt)}</TableCell><TableCell>{run.triggeredBy}</TableCell><TableCell>{run.recordsChecked}</TableCell><TableCell>{run.issuesDetected}</TableCell><TableCell>{run.issuesResolved}</TableCell><TableCell>{run.failedChecks}</TableCell><TableCell><Tooltip title={run.checkResults.map((check) => `${check.name}: ${check.status}${check.error ? ` (${check.error})` : ""}`).join("\n")}><Chip size="small" label={run.status} color={run.status === "Failed" ? "error" : run.status === "Completed with Issues" ? "warning" : "success"} /></Tooltip></TableCell></TableRow>)}
					</TableBody></Table>
				</Box>}
				{historyQuery.data && <TablePagination component="div" count={historyQuery.data.total} page={historyPage} onPageChange={(_, value) => setHistoryPage(value)} rowsPerPage={25} rowsPerPageOptions={[25]} />}
			</Stack>}
		</Paper>
		<Dialog open={Boolean(selectedIssue)} onClose={() => setSelectedIssue(null)} fullWidth maxWidth="md">
			<DialogTitle>{selectedIssue ? `DQ-${selectedIssue.id} · ${humanizeIssueType(selectedIssue.issueType)}` : "Issue details"}</DialogTitle>
			<DialogContent>
				{detailQuery.isLoading ? <Box sx={{ py: 5, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box> : detailQuery.isError ? <Alert severity="error">Issue details could not be loaded.</Alert> : detail && <Stack spacing={2} sx={{ pt: 0.5 }}>
					<Alert severity={detail.issue.severity === "error" ? "error" : "warning"}>{detail.issue.description}</Alert>
					<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))" }, gap: 1 }}>
						<Typography variant="body2"><b>Module:</b> {detail.issue.module}</Typography><Typography variant="body2"><b>Record:</b> {detail.issue.recordType} #{detail.issue.recordId} {detail.issue.recordName ?? ""}</Typography>
						<Typography variant="body2"><b>Detected:</b> {formatDate(detail.issue.detectedAt)}</Typography><Typography variant="body2"><b>Last seen:</b> {formatDate(detail.issue.lastSeenAt)}</Typography>
						{detail.issue.resolvedBy && <Typography variant="body2"><b>Resolved by:</b> {detail.issue.resolvedBy}</Typography>}{detail.issue.resolvedAt && <Typography variant="body2"><b>Resolved at:</b> {formatDate(detail.issue.resolvedAt)}</Typography>}
					</Box>
					<ContextBlock title="Affected record details" value={detail.issue.details} />
					<ContextBlock title="Product" value={detail.context.product} />
					<ContextBlock title="Inventory reconciliation" value={detail.context.inventory} />
					<ContextBlock title="Related stock movements" value={detail.context.stockMovements} />
					<ContextBlock title="Related sales" value={detail.context.relatedSales} />
					<ContextBlock title="Customer" value={detail.context.customer} />
					<ContextBlock title="Sale" value={detail.context.sale} />
					{detail.issue.resolutionNote && <Alert severity="success">Resolution: {detail.issue.resolutionNote}</Alert>}
					<Box><Typography variant="subtitle2" fontWeight={800} sx={{ mb: 0.75 }}>Status history</Typography>{detail.events.length === 0 ? <Typography variant="body2" color="text.secondary">No status changes recorded.</Typography> : detail.events.map((event) => <Typography key={event.id} variant="body2" sx={{ mb: 0.5 }}>{event.previousStatus} → {event.newStatus} · {event.changedBy} · {formatDate(event.createdAt)}{event.note ? ` · ${event.note}` : ""}</Typography>)}</Box>
					{canReconcile && <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "220px 1fr" }, gap: 1.25 }}>
						<TextField select size="small" label="Update status" value={nextStatus} onChange={(event) => setNextStatus(event.target.value as DataQualityStatus)}>{statusOptions.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
						<TextField size="small" label={nextStatus === "Resolved" ? "Resolution note (required)" : "Resolution / investigation note"} value={resolutionNote} onChange={(event) => setResolutionNote(event.target.value)} multiline maxRows={3} />
					</Box>}
					{mutationError && <Alert severity="error">{mutationError}</Alert>}
				</Stack>}
			</DialogContent>
			<DialogActions sx={{ px: 3, pb: 2 }}>
				<Button onClick={() => setSelectedIssue(null)}>Close</Button>
				{canReconcile && <Button variant="contained" disabled={!selectedIssue || statusMutation.isPending || (nextStatus === "Resolved" && !resolutionNote.trim())} onClick={applyStatus}>{statusMutation.isPending ? "Saving…" : "Save status"}</Button>}
			</DialogActions>
		</Dialog>
	</Stack>;
}