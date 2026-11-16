import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
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
	FormControlLabel,
	Grid,
	MenuItem,
	Pagination,
	Paper,
	Stack,
	Switch,
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableRow,
	Tabs,
	Tab,
	TextField,
	Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
	approveWorkflowRequest,
	cancelWorkflowRequest,
	createWorkflowRequest,
	getWorkflowRequest,
	listWorkflowConfigurations,
	listWorkflowRequests,
	rejectWorkflowRequest,
	submitWorkflowRequest,
	updateWorkflowConfiguration,
	WorkflowConfiguration,
	WorkflowRequest,
	WorkflowRequestType,
} from "../../api/workflowApi";
import { useAuth } from "../../context/AuthContext";
import { useNotification } from "../../context/NotificationContext";

const requestTypes: Array<{ value: WorkflowRequestType; label: string; changes: string }> = [
	{ value: "stock-adjustment", label: "Stock Adjustment", changes: '{"targetQuantity": 150}' },
	{ value: "product-deactivation", label: "Product Deactivation", changes: '{"status": "inactive"}' },
	{ value: "product-price-change", label: "Product Price Change", changes: '{"unitPrice": 29.99}' },
	{ value: "customer-information-change", label: "Customer Information Change", changes: '{"email": "new@example.com"}' },
	{ value: "inventory-import-approval", label: "Inventory Import Approval", changes: '{"action": "start-import"}' },
];

const statusColor = (status: string): "default" | "success" | "warning" | "error" | "info" => {
	if (status === "approved") return "success";
	if (status === "rejected") return "error";
	if (status === "pending-approval") return "warning";
	if (status === "cancelled") return "default";
	return "info";
};

function messageFromError(error: unknown, fallback: string) {
	if (isAxiosError(error)) {
		const detail = error.response?.data?.detail;
		if (typeof detail === "string") return detail;
	}
	return fallback;
}

function formatValue(value: unknown) {
	if (value === null || value === undefined || value === "") return "—";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
}

export default function WorkflowsPage() {
	const { user } = useAuth();
	const { notify } = useNotification();
	const queryClient = useQueryClient();
	const [searchParams] = useSearchParams();
	const isAdmin = user?.role === "Company Admin" || user?.role === "Super Admin";
	const [scope, setScope] = useState<"queue" | "mine" | "all">(searchParams.get("scope") === "mine" ? "mine" : isAdmin ? "queue" : "mine");
	const [requestType, setRequestType] = useState("");
	const [requestStatus, setRequestStatus] = useState("");
	const [search, setSearch] = useState("");
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
	const [page, setPage] = useState(1);
	const [selectedId, setSelectedId] = useState<number | null>(() => {
		const requestId = Number(searchParams.get("requestId"));
		return Number.isInteger(requestId) && requestId > 0 ? requestId : null;
	});
	const [createOpen, setCreateOpen] = useState(false);
	const [createType, setCreateType] = useState<WorkflowRequestType>("stock-adjustment");
	const [recordId, setRecordId] = useState("");
	const [changes, setChanges] = useState(requestTypes[0].changes);
	const [reason, setReason] = useState("");
	const [priority, setPriority] = useState<WorkflowRequest["priority"]>("medium");
	const [createAsDraft, setCreateAsDraft] = useState(false);
	const [comment, setComment] = useState("");
	const [formError, setFormError] = useState("");
	const [configError, setConfigError] = useState("");
	const filters = useMemo(
		() => ({ scope: scope === "queue" ? "queue" as const : scope, requestType, status: requestStatus, search, page, pageSize: 20, sortDirection }),
		[page, requestStatus, requestType, scope, search, sortDirection],
	);
	const requestsQuery = useQuery({ queryKey: ["workflows", filters], queryFn: () => listWorkflowRequests(filters), refetchInterval: 15000 });
	const detailQuery = useQuery({ queryKey: ["workflow", selectedId], queryFn: () => getWorkflowRequest(selectedId as number), enabled: selectedId !== null });
	const configQuery = useQuery({ queryKey: ["workflow-config"], queryFn: listWorkflowConfigurations, enabled: isAdmin });
	const requests = requestsQuery.data?.items ?? [];
	const detail = detailQuery.data;

	useEffect(() => setPage(1), [scope, requestType, requestStatus, search, sortDirection]);
	useEffect(() => {
		const next = requestTypes.find((item) => item.value === createType);
		if (next) setChanges(next.changes);
	}, [createType]);

	const refreshRequests = async () => {
		await Promise.all([
			queryClient.invalidateQueries({ queryKey: ["workflows"] }),
			queryClient.invalidateQueries({ queryKey: ["workflow"] }),
		]);
	};

	const createMutation = useMutation({
		mutationFn: createWorkflowRequest,
		onSuccess: async (created) => {
			setCreateOpen(false);
			setRecordId("");
			setReason("");
			setCreateAsDraft(false);
			setFormError("");
			await refreshRequests();
			setSelectedId(created.id);
			notify(
				created.status === "draft"
					? `Draft ${created.requestId} saved.`
					: created.status === "approved"
						? `Request ${created.requestId} was automatically approved.`
						: `Request ${created.requestId} submitted for approval.`,
				"success",
			);
		},
		onError: (error) => setFormError(messageFromError(error, "Unable to submit the workflow request.")),
	});
	const approveMutation = useMutation({
		mutationFn: () => approveWorkflowRequest(selectedId as number, comment.trim() || undefined),
		onSuccess: async () => {
			setComment("");
			await refreshRequests();
			await detailQuery.refetch();
			notify("Request approved and requested changes applied.", "success");
		},
		onError: (error) => notify(messageFromError(error, "Unable to approve this request."), "error"),
	});
	const rejectMutation = useMutation({
		mutationFn: () => rejectWorkflowRequest(selectedId as number, comment.trim()),
		onSuccess: async () => {
			setComment("");
			await refreshRequests();
			await detailQuery.refetch();
			notify("Request rejected. No business changes were applied.", "success");
		},
		onError: (error) => notify(messageFromError(error, "Unable to reject this request."), "error"),
	});
	const cancelMutation = useMutation({
		mutationFn: () => cancelWorkflowRequest(selectedId as number),
		onSuccess: async () => {
			await refreshRequests();
			await detailQuery.refetch();
			notify("Request cancelled.", "success");
		},
		onError: (error) => notify(messageFromError(error, "Unable to cancel this request."), "error"),
	});
	const submitDraftMutation = useMutation({
		mutationFn: () => submitWorkflowRequest(selectedId as number),
		onSuccess: async (submitted) => {
			await refreshRequests();
			await detailQuery.refetch();
			notify(submitted.status === "approved" ? "Draft automatically approved." : "Draft submitted for approval.", "success");
		},
		onError: (error) => notify(messageFromError(error, "Unable to submit this draft."), "error"),
	});

	const submitCreate = (event: FormEvent) => {
		event.preventDefault();
		setFormError("");
		let parsedChanges: Record<string, unknown>;
		try {
			const parsed: unknown = JSON.parse(changes);
			if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
			parsedChanges = parsed as Record<string, unknown>;
		} catch {
			setFormError("Requested changes must be a valid JSON object.");
			return;
		}
		const numericId = Number(recordId);
		if (!Number.isInteger(numericId) || numericId < 1) {
			setFormError("Enter a valid related record ID.");
			return;
		}
		if (!reason.trim()) {
			setFormError("A reason is required.");
			return;
		}
		createMutation.mutate({ requestType: createType, relatedRecordId: numericId, requestedChanges: parsedChanges, reason: reason.trim(), priority, draft: createAsDraft });
	};

	const updateConfig = async (config: WorkflowConfiguration, patch: Partial<WorkflowConfiguration>) => {
		setConfigError("");
		try {
			await updateWorkflowConfiguration(config.requestType, {
				approverRole: patch.approverRole ?? config.approverRole,
				approvalRequired: patch.approvalRequired ?? config.approvalRequired,
				allowSelfApproval: patch.allowSelfApproval ?? config.allowSelfApproval,
				isActive: patch.isActive ?? config.isActive,
			});
			await configQuery.refetch();
			notify(`${config.label} settings saved.`, "success");
		} catch (error) {
			setConfigError(messageFromError(error, "Unable to save workflow settings."));
		}
	};

	const canReview = Boolean(
		detail &&
		detail.status === "pending-approval" &&
		(detail.requestedBy.id !== user?.id || detail.allowSelfApproval) &&
		(isAdmin || detail.approverRole === user?.role),
	);
	const canCancel = Boolean(detail && detail.requestedBy.id === user?.id && ["draft", "pending-approval"].includes(detail.status));
	const canSubmitDraft = Boolean(detail && detail.requestedBy.id === user?.id && detail.status === "draft");

	return (
		<Stack spacing={3}>
			<Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2} alignItems={{ sm: "center" }}>
				<Box>
					<Typography variant="h4" fontWeight={800}>Workflows &amp; Approvals</Typography>
					<Typography color="text.secondary">Review business changes, follow request history, and manage approval routing.</Typography>
				</Box>
				<Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreateOpen(true)}>New request</Button>
			</Stack>

			<Paper sx={{ px: 2 }}>
				<Tabs value={scope} onChange={(_, value: "queue" | "mine" | "all") => setScope(value)} variant="scrollable">
					<Tab value="queue" label="Approval queue" />
					<Tab value="mine" label="My requests" />
					{isAdmin && <Tab value="all" label="All company requests" />}
				</Tabs>
			</Paper>

			<Paper sx={{ p: 2 }}>
				<Grid container spacing={2}>
					<Grid size={{ xs: 12, md: 5 }}>
						<TextField fullWidth label="Search requests" value={search} onChange={(event) => setSearch(event.target.value)} slotProps={{ input: { startAdornment: <SearchRoundedIcon sx={{ mr: 1, color: "text.secondary" }} /> } }} />
					</Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}>
						<TextField fullWidth select label="Request type" value={requestType} onChange={(event) => setRequestType(event.target.value)}>
							<MenuItem value="">All types</MenuItem>{requestTypes.map((type) => <MenuItem key={type.value} value={type.value}>{type.label}</MenuItem>)}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}>
						<TextField fullWidth select label="Status" value={requestStatus} onChange={(event) => setRequestStatus(event.target.value)}>
							<MenuItem value="">All statuses</MenuItem>{["draft", "pending-approval", "approved", "rejected", "cancelled"].map((item) => <MenuItem key={item} value={item}>{item.replace("-", " ")}</MenuItem>)}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}>
						<TextField fullWidth select label="Sort by date" value={sortDirection} onChange={(event) => setSortDirection(event.target.value as "asc" | "desc")}>
							<MenuItem value="desc">Newest first</MenuItem><MenuItem value="asc">Oldest first</MenuItem>
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 1 }}><Button fullWidth sx={{ height: 56 }} onClick={() => void requestsQuery.refetch()}>Refresh</Button></Grid>
				</Grid>
			</Paper>

			{requestsQuery.isLoading && <Box display="grid" sx={{ placeItems: "center", minHeight: 220 }}><CircularProgress /></Box>}
			{requestsQuery.isError && <Alert severity="error">Unable to load workflow requests. Check your access and try again.</Alert>}
			{!requestsQuery.isLoading && !requestsQuery.isError && requests.length === 0 && <Alert severity="info">{scope === "queue" ? "There are no requests awaiting your approval." : "No requests match the selected filters."}</Alert>}
			{requests.length > 0 && (
				<Paper sx={{ overflowX: "auto" }}>
					<Table size="medium">
						<TableHead><TableRow>{["Request ID", "Type", "Requested by", "Requested date", "Priority", "Status", "Related record", "Action"].map((title) => <TableCell key={title} sx={{ fontWeight: 800, whiteSpace: "nowrap" }}>{title}</TableCell>)}</TableRow></TableHead>
						<TableBody>{requests.map((item) => (
							<TableRow key={item.id} hover>
								<TableCell sx={{ fontWeight: 750 }}>{item.requestId}</TableCell>
								<TableCell>{item.requestTypeLabel}</TableCell>
								<TableCell>{item.requestedBy.name}</TableCell>
								<TableCell sx={{ whiteSpace: "nowrap" }}>{new Date(item.createdAt).toLocaleString()}</TableCell>
								<TableCell><Chip size="small" label={item.priority} color={item.priority === "critical" || item.priority === "high" ? "error" : "default"} /></TableCell>
								<TableCell><Chip size="small" label={item.status.replace("-", " ")} color={statusColor(item.status)} /></TableCell>
								<TableCell>{item.relatedRecord.name} · #{item.relatedRecordId}</TableCell>
								<TableCell><Button onClick={() => { setSelectedId(item.id); setComment(""); }}>Open</Button></TableCell>
							</TableRow>
						))}</TableBody>
					</Table>
				</Paper>
			)}
			{requestsQuery.data && requestsQuery.data.totalPages > 1 && <Stack alignItems="center"><Pagination count={requestsQuery.data.totalPages} page={page} onChange={(_, value) => setPage(value)} color="primary" /></Stack>}

			{isAdmin && (
				<Paper sx={{ p: 3 }}>
					<Typography variant="h5" fontWeight={800}>Workflow configuration</Typography>
					<Typography color="text.secondary" sx={{ mb: 2 }}>Set the approver role, approval requirement, and whether self-approval is allowed for each request type.</Typography>
					{configError && <Alert severity="error" sx={{ mb: 2 }}>{configError}</Alert>}
					{configQuery.isLoading && <CircularProgress size={24} />}
					{configQuery.isError && <Alert severity="error">Workflow settings could not be loaded.</Alert>}
					<Stack spacing={1.5}>
						{configQuery.data?.map((config) => (
							<Stack key={config.requestType} direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
								<Typography sx={{ flex: 1, fontWeight: 700 }}>{config.label}</Typography>
								<TextField select size="small" label="Approver role" value={config.approverRole} onChange={(event) => void updateConfig(config, { approverRole: event.target.value })} sx={{ minWidth: 180 }}>
									{["Company Admin", "Super Admin", "Analyst", "Viewer"].map((role) => <MenuItem key={role} value={role}>{role}</MenuItem>)}
								</TextField>
								<FormControlLabel control={<Switch checked={config.approvalRequired} onChange={(event) => void updateConfig(config, { approvalRequired: event.target.checked })} />} label="Approval required" />
								<FormControlLabel control={<Switch checked={config.allowSelfApproval} onChange={(event) => void updateConfig(config, { allowSelfApproval: event.target.checked })} />} label="Allow self-approval" />
								<FormControlLabel control={<Switch checked={config.isActive} onChange={(event) => void updateConfig(config, { isActive: event.target.checked })} />} label="Active" />
							</Stack>
						))}
					</Stack>
				</Paper>
			)}

			<Dialog open={createOpen} onClose={() => !createMutation.isPending && setCreateOpen(false)} fullWidth maxWidth="sm">
				<Box component="form" onSubmit={submitCreate}>
					<DialogTitle>Submit an approval request</DialogTitle>
					<DialogContent><Stack spacing={2} sx={{ pt: 1 }}>
						<TextField select label="Request type" value={createType} onChange={(event) => setCreateType(event.target.value as WorkflowRequestType)}>
							{requestTypes.map((type) => <MenuItem key={type.value} value={type.value}>{type.label}</MenuItem>)}
						</TextField>
						<TextField label="Related record ID" type="number" value={recordId} onChange={(event) => setRecordId(event.target.value)} inputProps={{ min: 1 }} required helperText="Use the record ID from the relevant business module." />
						<TextField label="Requested changes (JSON)" value={changes} onChange={(event) => setChanges(event.target.value)} multiline minRows={3} required />
						<TextField label="Reason for change" value={reason} onChange={(event) => setReason(event.target.value)} multiline minRows={2} required />
						<TextField select label="Priority" value={priority} onChange={(event) => setPriority(event.target.value as WorkflowRequest["priority"])}>{["low", "medium", "high", "critical"].map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
						<FormControlLabel control={<Switch checked={createAsDraft} onChange={(event) => setCreateAsDraft(event.target.checked)} />} label="Save as draft" />
						{formError && <Alert severity="error">{formError}</Alert>}
						<Alert severity="info">The original business record stays unchanged until this request is approved.</Alert>
					</Stack></DialogContent>
					<DialogActions><Button onClick={() => setCreateOpen(false)} disabled={createMutation.isPending}>Cancel</Button><Button type="submit" variant="contained" disabled={createMutation.isPending}>{createMutation.isPending ? "Saving…" : createAsDraft ? "Save draft" : "Submit for approval"}</Button></DialogActions>
				</Box>
			</Dialog>

			<Dialog open={selectedId !== null} onClose={() => setSelectedId(null)} fullWidth maxWidth="md">
				<DialogTitle>{detail ? `${detail.requestId} · ${detail.requestTypeLabel}` : "Approval request details"}</DialogTitle>
				<DialogContent dividers>
					{detailQuery.isLoading && <CircularProgress />}
					{detailQuery.isError && <Alert severity="error">Unable to load request details.</Alert>}
					{detail && <Stack spacing={2}>
						<Stack direction="row" spacing={1} flexWrap="wrap"><Chip label={detail.status.replace("-", " ")} color={statusColor(detail.status)} /><Chip label={`Priority: ${detail.priority}`} /><Chip label={`Approver: ${detail.approverRole}`} /></Stack>
						<Grid container spacing={2}>
							<Grid size={{ xs: 12, md: 6 }}><Typography variant="subtitle2" color="text.secondary">Requested by</Typography><Typography>{detail.requestedBy.name} · {detail.requestedBy.email}</Typography></Grid>
							<Grid size={{ xs: 12, md: 6 }}><Typography variant="subtitle2" color="text.secondary">Company</Typography><Typography>{detail.companyName}</Typography></Grid>
							<Grid size={{ xs: 12, md: 6 }}><Typography variant="subtitle2" color="text.secondary">Related record</Typography><Typography>{detail.relatedRecord.type} #{detail.relatedRecord.id} · {detail.relatedRecord.name}{detail.relatedRecord.status ? ` · ${detail.relatedRecord.status}` : ""}</Typography></Grid>
							<Grid size={{ xs: 12 }}><Typography variant="subtitle2" color="text.secondary">Reason</Typography><Typography>{detail.reason}</Typography></Grid>
						</Grid>
						<Typography variant="h6" fontWeight={750}>Requested changes</Typography>
						<Grid container spacing={1}>
							{detail.requestType === "stock-adjustment" && (
								<Grid size={{ xs: 12, sm: 6 }}>
									<Paper variant="outlined" sx={{ p: 1.5, bgcolor: "action.hover" }}>
										<Typography variant="caption" color="text.secondary">Current stock → requested stock</Typography>
										<Typography><strong>Current:</strong> {formatValue(detail.currentValues.currentQuantity)}</Typography>
										<Typography color="primary.main"><strong>Requested:</strong> {formatValue(detail.requestedChanges.targetQuantity)}</Typography>
										<Typography variant="caption">Difference: {Number(detail.requestedChanges.targetQuantity) - Number(detail.currentValues.currentQuantity) >= 0 ? "+" : ""}{Number(detail.requestedChanges.targetQuantity) - Number(detail.currentValues.currentQuantity)}</Typography>
									</Paper>
								</Grid>
							)}
							{Object.keys(detail.requestedChanges).filter((key) => key !== "action" && key !== "targetQuantity").map((key) => (
								<Grid key={key} size={{ xs: 12, sm: 6 }}>
									<Paper variant="outlined" sx={{ p: 1.5, bgcolor: "action.hover" }}>
										<Typography variant="caption" color="text.secondary">{key.replace(/([A-Z])/g, " $1")}</Typography>
										<Typography><strong>Current:</strong> {formatValue(detail.currentValues[key])}</Typography>
										<Typography color="primary.main"><strong>Requested:</strong> {formatValue(detail.requestedChanges[key] ?? detail.currentValues[key])}</Typography>
									</Paper>
								</Grid>
							))}
						</Grid>
						<Typography variant="h6" fontWeight={750}>Approval history</Typography>
						{detail.history.length === 0 ? <Typography color="text.secondary">No history recorded.</Typography> : detail.history.map((entry) => (
							<Paper key={entry.id} variant="outlined" sx={{ p: 1.5 }}>
								<Typography fontWeight={700}>{new Date(entry.createdAt).toLocaleString()} · {entry.action.replace("-", " ")} by {entry.actorName}</Typography>
								{entry.comment && <Typography color="text.secondary">{entry.comment}</Typography>}
							</Paper>
						))}
						{canReview && <Stack spacing={1}><TextField label="Comment (required for rejection)" value={comment} onChange={(event) => setComment(event.target.value)} multiline minRows={2} /><Stack direction="row" spacing={1}><Button variant="contained" color="success" startIcon={<CheckCircleOutlineRoundedIcon />} onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending || rejectMutation.isPending}>Approve and apply</Button><Button variant="outlined" color="error" onClick={() => rejectMutation.mutate()} disabled={!comment.trim() || rejectMutation.isPending || approveMutation.isPending}>Reject</Button></Stack></Stack>}
						{canSubmitDraft && <Button variant="contained" onClick={() => submitDraftMutation.mutate()} disabled={submitDraftMutation.isPending}>Submit draft for approval</Button>}
						{canCancel && <Button color="inherit" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending} sx={{ alignSelf: "flex-start" }}>Cancel request</Button>}
						{(approveMutation.isPending || rejectMutation.isPending || cancelMutation.isPending || submitDraftMutation.isPending) && <CircularProgress size={22} />}
					</Stack>}
				</DialogContent>
				<DialogActions><Button onClick={() => setSelectedId(null)}>Close</Button></DialogActions>
			</Dialog>
		</Stack>
	);
}
