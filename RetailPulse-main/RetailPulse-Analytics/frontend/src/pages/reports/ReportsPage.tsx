import AddRoundedIcon from "@mui/icons-material/AddRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import StopRoundedIcon from "@mui/icons-material/StopRounded";
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
import { useEffect, useMemo, useState } from "react";
import {
	createScheduledReport,
	deleteScheduledReport,
	exportReport,
	generateReport,
	getReportFilters,
	getReportHistory,
	getReportHistoryDetail,
	listScheduledReports,
	setScheduledReportActive,
	updateScheduledReport,
} from "../../api/reportsApi";
import { useAuth } from "../../context/AuthContext";
import { ReportFilters, ReportFormat, ReportHistory, ReportResult, ReportType, SchedulePayload, ScheduledReport } from "../../types/reporting";

const reportOptions: Array<{ value: ReportType; label: string }> = [
	{ value: "sales", label: "Sales Report" },
	{ value: "inventory", label: "Inventory Report" },
	{ value: "customers", label: "Customer Report" },
	{ value: "product-performance", label: "Product Performance Report" },
	{ value: "stock-movement", label: "Stock Movement Report" },
];

const columns: Record<ReportType, Array<{ key: string; label: string }>> = {
	sales: [
		{ key: "date", label: "Date" }, { key: "invoice", label: "Invoice" }, { key: "customer", label: "Customer" },
		{ key: "product", label: "Product" }, { key: "sku", label: "SKU" }, { key: "category", label: "Category" },
		{ key: "brand", label: "Brand" }, { key: "quantity", label: "Qty" }, { key: "total", label: "Line total" }, { key: "status", label: "Status" },
	],
	inventory: [
		{ key: "product", label: "Product" }, { key: "sku", label: "SKU" }, { key: "category", label: "Category" },
		{ key: "brand", label: "Brand" }, { key: "currentStock", label: "On hand" }, { key: "reservedStock", label: "Reserved" },
		{ key: "availableStock", label: "Available" }, { key: "reorderLevel", label: "Reorder at" }, { key: "status", label: "Stock status" },
	],
	customers: [
		{ key: "customer", label: "Customer" }, { key: "customerCode", label: "Code" }, { key: "email", label: "Email" },
		{ key: "type", label: "Type" }, { key: "segment", label: "Segment" }, { key: "status", label: "Status" },
		{ key: "orders", label: "Orders" }, { key: "revenue", label: "Revenue" }, { key: "lastPurchase", label: "Last purchase" },
	],
	"product-performance": [
		{ key: "product", label: "Product" }, { key: "sku", label: "SKU" }, { key: "category", label: "Category" },
		{ key: "brand", label: "Brand" }, { key: "quantitySold", label: "Qty sold" }, { key: "revenue", label: "Revenue" },
		{ key: "currentStock", label: "On hand" }, { key: "stockStatus", label: "Stock status" },
	],
	"stock-movement": [
		{ key: "date", label: "Date" }, { key: "product", label: "Product" }, { key: "sku", label: "SKU" },
		{ key: "category", label: "Category" }, { key: "movement", label: "Movement" }, { key: "previous", label: "Previous" },
		{ key: "change", label: "Change" }, { key: "updated", label: "Updated" }, { key: "reason", label: "Reason" }, { key: "user", label: "User" },
	],
};

type FilterProps = {
	reportType: ReportType;
	filters: ReportFilters;
	setFilters: (update: (current: ReportFilters) => ReportFilters) => void;
	options?: Awaited<ReturnType<typeof getReportFilters>>;
};

function setValue(filters: ReportFilters, key: keyof ReportFilters, value: string | number) {
	const updated = { ...filters };
	if (value === "") delete updated[key];
	else if (key === "startDate") updated.startDate = `${value}T00:00:00`;
	else if (key === "endDate") updated.endDate = `${value}T23:59:59`;
	else if (key === "productId") updated.productId = Number(value);
	else if (key === "categoryId") updated.categoryId = Number(value);
	else if (key === "customerId") updated.customerId = Number(value);
	else if (key === "userId") updated.userId = Number(value);
	else if (key === "brand") updated.brand = String(value);
	else if (key === "salesStatus") updated.salesStatus = String(value);
	else if (key === "stockStatus") updated.stockStatus = String(value);
	return updated;
}

function dateValue(value?: string) {
	return value?.slice(0, 10) ?? "";
}

function ReportFiltersForm({ reportType, filters, setFilters, options }: FilterProps) {
	const salesLike = reportType === "sales" || reportType === "product-performance";
	const customerLike = reportType === "customers";
	const movementLike = reportType === "stock-movement";
	const inventoryLike = reportType === "inventory" || movementLike || reportType === "product-performance";
	const showDates = reportType !== "inventory";
	const filterText = (key: keyof ReportFilters, label: string) => ({
		value: String(filters[key] ?? ""),
		onChange: (event: React.ChangeEvent<HTMLInputElement>) => setFilters((current) => setValue(current, key, event.target.value)),
		label,
	});
	const select = (key: keyof ReportFilters, label: string, values: Array<{ value: string | number; label: string }>) => (
		<TextField {...filterText(key, label)} select size="small" fullWidth>
			<MenuItem value="">All</MenuItem>
			{values.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}
		</TextField>
	);
	return <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" }, gap: 1.5 }}>
		{showDates && <>
			<TextField label="Start date" type="date" size="small" value={dateValue(filters.startDate)} onChange={(event) => setFilters((current) => setValue(current, "startDate", event.target.value))} InputLabelProps={{ shrink: true }} />
			<TextField label="End date" type="date" size="small" value={dateValue(filters.endDate)} onChange={(event) => setFilters((current) => setValue(current, "endDate", event.target.value))} InputLabelProps={{ shrink: true }} />
		</>}
		{select("productId", "Product", options?.products.map((item) => ({ value: item.id, label: item.name })) ?? [])}
		{select("categoryId", "Category", options?.categories.map((item) => ({ value: item.id, label: item.name })) ?? [])}
		{select("brand", "Brand", options?.brands.map((item) => ({ value: item, label: item })) ?? [])}
		{(salesLike || customerLike) && select("customerId", "Customer", options?.customers.map((item) => ({ value: item.id, label: item.name })) ?? [])}
		{salesLike && select("salesStatus", "Sales status", ["pending", "paid", "failed", "refunded"].map((value) => ({ value, label: value })))}
		{customerLike && select("salesStatus", "Customer status", ["active", "inactive"].map((value) => ({ value, label: value })))}
		{inventoryLike && select("stockStatus", "Stock status", ["in-stock", "low-stock", "out-of-stock"].map((value) => ({ value, label: value })))}
		{(salesLike || customerLike || movementLike) && select("userId", "User", options?.users.map((item) => ({ value: item.id, label: item.name })) ?? [])}
	</Box>;
}

function download(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const anchor = document.createElement("a");
	anchor.href = url;
	anchor.download = filename;
	anchor.click();
	URL.revokeObjectURL(url);
}

function reportLabel(type: ReportType) {
	return reportOptions.find((option) => option.value === type)?.label ?? type;
}

function filterSummary(filters: ReportFilters) {
	const entries = Object.entries(filters).filter(([, value]) => value !== undefined && value !== "");
	return entries.length ? entries.map(([key, value]) => `${key}: ${String(value).slice(0, 10)}`).join(" · ") : "No filters applied";
}

function ScheduleEditor({
	open,
	onClose,
	onSave,
	options,
	initial,
}: {
	open: boolean;
	onClose: () => void;
	onSave: (payload: SchedulePayload) => void;
	options?: Awaited<ReturnType<typeof getReportFilters>>;
	initial?: ScheduledReport;
}) {
	const [name, setName] = useState(initial?.name ?? "");
	const [reportType, setReportType] = useState<ReportType>(initial?.reportType ?? "sales");
	const [filters, setFilters] = useState<ReportFilters>(initial?.filters ?? {});
	const [frequency, setFrequency] = useState<SchedulePayload["frequency"]>(initial?.frequency ?? "weekly");
	const [executionTime, setExecutionTime] = useState(initial?.executionTime ?? "09:00");
	const [recipients, setRecipients] = useState(initial?.recipients.join(", ") ?? "");
	const [exportFormat, setExportFormat] = useState<ReportFormat>(initial?.exportFormat ?? "csv");
	const [isActive, setIsActive] = useState(initial?.isActive ?? true);
	const [formError, setFormError] = useState("");

	useEffect(() => {
		if (!open) return;
		setName(initial?.name ?? "");
		setReportType(initial?.reportType ?? "sales");
		setFilters(initial?.filters ?? {});
		setFrequency(initial?.frequency ?? "weekly");
		setExecutionTime(initial?.executionTime ?? "09:00");
		setRecipients(initial?.recipients.join(", ") ?? "");
		setExportFormat(initial?.exportFormat ?? "csv");
		setIsActive(initial?.isActive ?? true);
		setFormError("");
	}, [open, initial]);

	const submit = () => {
		const emailList = recipients.split(",").map((value) => value.trim()).filter(Boolean);
		if (!name.trim() || emailList.length === 0 || emailList.some((email) => !/^\S+@\S+\.\S+$/.test(email))) {
			setFormError("Add a schedule name and at least one valid recipient email.");
			return;
		}
		onSave({ name: name.trim(), reportType, filters, frequency, executionTime, recipients: emailList, exportFormat, isActive });
	};

	return <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
		<DialogTitle>{initial ? "Edit scheduled report" : "New scheduled report"}</DialogTitle>
		<DialogContent>
			<Stack spacing={2} sx={{ pt: 1 }}>
				{formError && <Alert severity="error">{formError}</Alert>}
				<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))" }, gap: 1.5 }}>
					<TextField label="Schedule name" size="small" value={name} onChange={(event) => setName(event.target.value)} />
					<TextField select label="Report type" size="small" value={reportType} onChange={(event) => setReportType(event.target.value as ReportType)}>{reportOptions.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}</TextField>
					<TextField select label="Frequency" size="small" value={frequency} onChange={(event) => setFrequency(event.target.value as SchedulePayload["frequency"])}><MenuItem value="daily">Daily</MenuItem><MenuItem value="weekly">Weekly</MenuItem><MenuItem value="monthly">Monthly</MenuItem></TextField>
					<TextField label="Execution time (UTC)" type="time" size="small" value={executionTime} onChange={(event) => setExecutionTime(event.target.value)} InputLabelProps={{ shrink: true }} />
					<TextField label="Recipient emails" size="small" value={recipients} onChange={(event) => setRecipients(event.target.value)} placeholder="ops@example.com, finance@example.com" />
					<TextField select label="Export format" size="small" value={exportFormat} onChange={(event) => setExportFormat(event.target.value as ReportFormat)}><MenuItem value="csv">CSV</MenuItem><MenuItem value="pdf">PDF</MenuItem></TextField>
					<TextField select label="Status" size="small" value={isActive ? "active" : "inactive"} onChange={(event) => setIsActive(event.target.value === "active")}><MenuItem value="active">Active</MenuItem><MenuItem value="inactive">Inactive</MenuItem></TextField>
				</Box>
				<Typography variant="subtitle2" fontWeight={750}>Report filters</Typography>
				<ReportFiltersForm reportType={reportType} filters={filters} setFilters={setFilters} options={options} />
			</Stack>
		</DialogContent>
		<DialogActions sx={{ px: 3, pb: 2 }}><Button onClick={onClose}>Cancel</Button><Button variant="contained" onClick={submit}>Save schedule</Button></DialogActions>
	</Dialog>;
}

export default function ReportsPage() {
	const queryClient = useQueryClient();
	const { user } = useAuth();
	const isAdmin = user?.role === "Company Admin" || user?.role === "Super Admin";
	const [tab, setTab] = useState(0);
	const [reportType, setReportType] = useState<ReportType>("sales");
	const [filters, setFilters] = useState<ReportFilters>({});
	const [activeHistory, setActiveHistory] = useState<ReportHistory | null>(null);
	const [page, setPage] = useState(0);
	const [historyPage, setHistoryPage] = useState(0);
	const [sortBy, setSortBy] = useState<string | undefined>();
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
	const [editorOpen, setEditorOpen] = useState(false);
	const [editingSchedule, setEditingSchedule] = useState<ScheduledReport | undefined>();
	const [pageError, setPageError] = useState("");
	const [busy, setBusy] = useState(false);
	const filterOptionsQuery = useQuery({ queryKey: ["report-filter-options"], queryFn: getReportFilters });
	const reportHistoryQuery = useQuery({ queryKey: ["report-history", historyPage], queryFn: () => getReportHistory(historyPage + 1, 50), enabled: tab === 2 });
	const schedulesQuery = useQuery({ queryKey: ["scheduled-reports"], queryFn: listScheduledReports, enabled: tab === 1 });
	const resultQuery = useQuery({
		queryKey: ["report-result", activeHistory?.id, page, sortBy, sortDirection],
		queryFn: () => getReportHistoryDetail(activeHistory!.id, page + 1, 25, sortBy, sortDirection),
		enabled: Boolean(activeHistory),
	});
	const reportResult: ReportResult | undefined = resultQuery.data;
	const visibleColumns = useMemo(() => activeHistory ? columns[activeHistory.reportType] : columns[reportType], [activeHistory, reportType]);

	const invalidateReports = async () => {
		await Promise.all([
			queryClient.invalidateQueries({ queryKey: ["report-history"] }),
			queryClient.invalidateQueries({ queryKey: ["scheduled-reports"] }),
		]);
	};

	const createMutation = useMutation({ mutationFn: createScheduledReport, onSuccess: async () => { setEditorOpen(false); await invalidateReports(); } });
	const updateMutation = useMutation({ mutationFn: ({ id, payload }: { id: number; payload: SchedulePayload }) => updateScheduledReport(id, payload), onSuccess: async () => { setEditorOpen(false); setEditingSchedule(undefined); await invalidateReports(); } });
	const statusMutation = useMutation({ mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) => setScheduledReportActive(id, isActive), onSuccess: invalidateReports });
	const deleteMutation = useMutation({ mutationFn: deleteScheduledReport, onSuccess: invalidateReports });

	const handleGenerate = async () => {
		setBusy(true);
		setPageError("");
		setPage(0);
		setSortBy(undefined);
		setActiveHistory(null);
		try {
			const result = await generateReport(reportType, filters);
			setActiveHistory(result.history);
			await invalidateReports();
			if (result.history.status === "failed") setPageError(result.history.errorMessage ?? "Report generation failed.");
		} catch (error) {
			setPageError(error instanceof Error ? error.message : "Unable to generate this report.");
		} finally {
			setBusy(false);
		}
	};

	const handleExport = async (history: ReportHistory, format: ReportFormat) => {
		setPageError("");
		try {
			const file = await exportReport(history.id, format);
			download(file, `${history.reportType}-report-${history.id}.${format}`);
			await invalidateReports();
		} catch (error) {
			setPageError(error instanceof Error ? error.message : "Unable to export this report.");
		}
	};

	const onScheduleSave = (payload: SchedulePayload) => {
		if (editingSchedule) updateMutation.mutate({ id: editingSchedule.id, payload });
		else createMutation.mutate(payload);
	};

	const openHistory = async (historyId: number) => {
		setPageError("");
		try {
			const result = await getReportHistoryDetail(historyId, 1, 25);
			setActiveHistory(result.history);
			setReportType(result.history.reportType);
			setPage(0);
			setSortBy(undefined);
			setTab(0);
		} catch (error) {
			setPageError(error instanceof Error ? error.message : "Unable to open the report history entry.");
		}
	};

	const onSort = (column: string) => {
		if (sortBy === column) setSortDirection((current) => current === "asc" ? "desc" : "asc");
		else { setSortBy(column); setSortDirection("asc"); }
		setPage(0);
	};

	const historyItems = reportHistoryQuery.data?.items ?? [];
	const schedules = schedulesQuery.data ?? [];
	const errorText = pageError || (filterOptionsQuery.isError ? "Report filters could not be loaded." : "");

	return <Stack spacing={2.5}>
		<Box sx={{ display: "flex", justifyContent: "space-between", alignItems: { xs: "flex-start", sm: "center" }, gap: 2, flexWrap: "wrap" }}>
			<Box><Typography variant="h4" fontWeight={850}>Reports</Typography><Typography color="text.secondary" sx={{ mt: 0.5 }}>Generate, schedule, and retrieve company reports.</Typography></Box>
			<Button startIcon={<RefreshRoundedIcon />} onClick={() => { void filterOptionsQuery.refetch(); void reportHistoryQuery.refetch(); void schedulesQuery.refetch(); }}>Refresh</Button>
		</Box>
		{errorText && <Alert severity="error" onClose={() => setPageError("")}>{errorText}</Alert>}
		<Paper variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
			<Tabs value={tab} onChange={(_, value: number) => setTab(value)} variant="scrollable" scrollButtons="auto" sx={{ px: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
				<Tab label="Report builder" />
				<Tab label="Scheduled reports" />
				<Tab label="Report history" />
			</Tabs>
			{tab === 0 && <Stack spacing={2.5} sx={{ p: { xs: 2, md: 3 } }}>
				<Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
					<TextField select label="Report type" size="small" value={reportType} onChange={(event) => { setReportType(event.target.value as ReportType); setActiveHistory(null); }} sx={{ minWidth: 260 }}>
						{reportOptions.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}
					</TextField>
					<Button variant="contained" onClick={() => void handleGenerate()} disabled={busy || filterOptionsQuery.isLoading} startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <PlayArrowRoundedIcon />}>Generate report</Button>
				</Box>
				<ReportFiltersForm reportType={reportType} filters={filters} setFilters={setFilters} options={filterOptionsQuery.data} />
				{activeHistory && <>
					<Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }} spacing={1.5} sx={{ pt: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
						<Box><Typography variant="h6" fontWeight={800}>{reportLabel(activeHistory.reportType)}</Typography><Typography variant="body2" color="text.secondary">Period: {activeHistory.filters.startDate?.slice(0, 10) ?? "All dates"} to {activeHistory.filters.endDate?.slice(0, 10) ?? "Present"} · {filterSummary(activeHistory.filters)}</Typography></Box>
						<Stack direction="row" spacing={1}><Button size="small" startIcon={<DownloadRoundedIcon />} disabled={activeHistory.status !== "success"} onClick={() => void handleExport(activeHistory, "csv")}>CSV</Button><Button size="small" startIcon={<DownloadRoundedIcon />} disabled={activeHistory.status !== "success"} onClick={() => void handleExport(activeHistory, "pdf")}>PDF</Button></Stack>
					</Stack>
					{activeHistory.status === "failed" && <Alert severity="error">{activeHistory.errorMessage ?? "The report could not be generated."}</Alert>}
					{resultQuery.isLoading && <Box sx={{ py: 5, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box>}
					{resultQuery.isError && <Alert severity="error">Report rows could not be loaded.</Alert>}
					{reportResult && activeHistory.status === "success" && <>
						{reportResult.page.total === 0 ? <Alert severity="info">No rows match the applied filters.</Alert> : <Box sx={{ overflowX: "auto" }}>
							<Table size="small" stickyHeader><TableHead><TableRow>{visibleColumns.map((column) => <TableCell key={column.key} sx={{ whiteSpace: "nowrap", bgcolor: "background.paper", fontWeight: 800 }}><Button size="small" color="inherit" onClick={() => onSort(column.key)} sx={{ p: 0, minWidth: 0, textTransform: "none", fontWeight: 800 }}>{column.label}{sortBy === column.key ? sortDirection === "asc" ? " ↑" : " ↓" : ""}</Button></TableCell>)}</TableRow></TableHead>
								<TableBody>{reportResult.page.items.map((row, index) => <TableRow hover key={String(row.id ?? row.saleId ?? row.productId ?? row.customerId ?? row.movementId ?? index)}>{visibleColumns.map((column) => <TableCell key={column.key} sx={{ whiteSpace: "nowrap", maxWidth: 300 }}>{column.key.toLowerCase().includes("date") || column.key === "lastPurchase" ? String(row[column.key] ?? "").replace("T", " ").slice(0, 16) : String(row[column.key] ?? "—")}</TableCell>)}</TableRow>)}</TableBody>
							</Table>
						</Box>}
						<TablePagination component="div" count={reportResult.page.total} page={page} onPageChange={(_, value) => setPage(value)} rowsPerPage={25} rowsPerPageOptions={[25]} />
					</>}
				</>}
				{!activeHistory && !busy && <Typography variant="body2" color="text.secondary">Choose a report and combine the filters, then generate a snapshot to review or export.</Typography>}
			</Stack>}
			{tab === 1 && <Stack spacing={2} sx={{ p: { xs: 2, md: 3 } }}>
				<Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}><Box><Typography variant="h6" fontWeight={800}>Scheduled reports</Typography><Typography variant="body2" color="text.secondary">Execution times use UTC. Email delivery requires SMTP configuration.</Typography></Box>{isAdmin && <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => { setEditingSchedule(undefined); setEditorOpen(true); }}>New schedule</Button>}</Stack>
				{schedulesQuery.isLoading && <Box sx={{ py: 4, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box>}
				{schedulesQuery.isError && <Alert severity="error">Scheduled reports could not be loaded.</Alert>}
				{!schedulesQuery.isLoading && schedules.length === 0 && <Alert severity="info">No scheduled reports yet.</Alert>}
				{schedules.map((schedule) => <Paper key={schedule.id} variant="outlined" sx={{ p: 2, borderRadius: 1.5 }}>
					<Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1.5}>
						<Box sx={{ minWidth: 0 }}><Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap"><Typography fontWeight={800}>{schedule.name}</Typography><Chip size="small" label={schedule.isActive ? "Active" : "Inactive"} color={schedule.isActive ? "success" : "default"} /><Chip size="small" variant="outlined" label={`${schedule.frequency} · ${schedule.executionTime} UTC`} /></Stack>
							<Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{reportLabel(schedule.reportType)} · {schedule.exportFormat.toUpperCase()} · {schedule.recipients.join(", ")}</Typography>
							<Typography variant="caption" color="text.secondary">Next: {new Date(schedule.nextRunAt).toLocaleString()} · Last: {schedule.lastRunAt ? `${new Date(schedule.lastRunAt).toLocaleString()} (${schedule.lastStatus ?? "unknown"})` : "Never run"}{schedule.lastError ? ` · ${schedule.lastError}` : ""}</Typography>
							{schedule.lastHistoryId && <Button size="small" sx={{ mt: 0.5, px: 0, minWidth: 0 }} onClick={() => void openHistory(schedule.lastHistoryId!)}>Open latest report</Button>}
						</Box>
						{isAdmin && <Stack direction="row" spacing={0.25} alignItems="center">
							<Tooltip title={schedule.isActive ? "Disable" : "Enable"}><IconButton aria-label={schedule.isActive ? "Disable schedule" : "Enable schedule"} onClick={() => statusMutation.mutate({ id: schedule.id, isActive: !schedule.isActive })}>{schedule.isActive ? <StopRoundedIcon /> : <PlayArrowRoundedIcon />}</IconButton></Tooltip>
							<Tooltip title="Edit"><IconButton aria-label="Edit schedule" onClick={() => { setEditingSchedule(schedule); setEditorOpen(true); }}><EditRoundedIcon /></IconButton></Tooltip>
							<Tooltip title="Delete"><IconButton aria-label="Delete schedule" color="error" onClick={() => deleteMutation.mutate(schedule.id)}><DeleteOutlineRoundedIcon /></IconButton></Tooltip>
						</Stack>}
					</Stack>
				</Paper>)}
			</Stack>}
			{tab === 2 && <Stack spacing={2} sx={{ p: { xs: 2, md: 3 } }}>
				<Box><Typography variant="h6" fontWeight={800}>Report history</Typography><Typography variant="body2" color="text.secondary">Generated snapshots and their saved filter context.</Typography></Box>
				{reportHistoryQuery.isLoading && <Box sx={{ py: 4, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box>}
				{reportHistoryQuery.isError && <Alert severity="error">Report history could not be loaded.</Alert>}
				{!reportHistoryQuery.isLoading && historyItems.length === 0 && <Alert severity="info">No reports have been generated yet.</Alert>}
				{historyItems.length > 0 && <Box sx={{ overflowX: "auto" }}><Table size="small"><TableHead><TableRow><TableCell>Report</TableCell><TableCell>Generated by</TableCell><TableCell>Date/time</TableCell><TableCell>Filters</TableCell><TableCell>Format</TableCell><TableCell>Status</TableCell><TableCell align="right">Actions</TableCell></TableRow></TableHead><TableBody>
					{historyItems.map((history) => <TableRow key={history.id} hover><TableCell>{reportLabel(history.reportType)}</TableCell><TableCell>{history.generatedBy}</TableCell><TableCell sx={{ whiteSpace: "nowrap" }}>{new Date(history.createdAt).toLocaleString()}</TableCell><TableCell sx={{ minWidth: 200, maxWidth: 380 }}>{filterSummary(history.filters)}</TableCell><TableCell>{history.format.toUpperCase()}</TableCell><TableCell><Stack spacing={0.5} alignItems="flex-start"><Chip size="small" label={history.status} color={history.status === "success" ? "success" : "error"} />{history.errorMessage && <Typography variant="caption" color="error.main" sx={{ maxWidth: 260, overflowWrap: "anywhere" }}>{history.errorMessage}</Typography>}</Stack></TableCell><TableCell align="right" sx={{ whiteSpace: "nowrap" }}><Tooltip title="View"><span><IconButton aria-label="View report" disabled={history.status !== "success"} onClick={() => void openHistory(history.id)}><VisibilityRoundedIcon /></IconButton></span></Tooltip><Tooltip title="Download CSV"><span><IconButton aria-label="Download CSV" disabled={history.status !== "success"} onClick={() => void handleExport(history, "csv")}><DownloadRoundedIcon /></IconButton></span></Tooltip><Tooltip title="Download PDF"><span><IconButton aria-label="Download PDF" disabled={history.status !== "success"} onClick={() => void handleExport(history, "pdf")}><Typography variant="caption" fontWeight={800}>PDF</Typography></IconButton></span></Tooltip></TableCell></TableRow>)}
				</TableBody></Table></Box>}
				{reportHistoryQuery.data && <TablePagination component="div" count={reportHistoryQuery.data.total} page={historyPage} rowsPerPage={50} rowsPerPageOptions={[50]} onPageChange={(_, value) => setHistoryPage(value)} />}
			</Stack>}
		</Paper>
		<ScheduleEditor open={editorOpen} onClose={() => setEditorOpen(false)} onSave={onScheduleSave} options={filterOptionsQuery.data} initial={editingSchedule} />
		{(createMutation.isPending || updateMutation.isPending || busy) && <Box sx={{ position: "fixed", bottom: 20, right: 24, zIndex: 10 }}><Chip icon={<CircularProgress size={14} />} label="Working" /></Box>}
	</Stack>;
}