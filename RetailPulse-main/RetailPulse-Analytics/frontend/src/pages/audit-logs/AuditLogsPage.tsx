import DownloadIcon from "@mui/icons-material/Download";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Grid, MenuItem, Pagination, Paper, Stack, TextField, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { exportAuditLogsCsv, exportAuditLogsPdf, getAuditLog, listAuditLogs, listAuditUsers, AuditLogFilters, AuditLogItem } from "../../api/auditLogApi";
import { useNotification } from "../../context/NotificationContext";

const initialFilters = { search: "", userId: "", action: "", resourceType: "", status: "", startDate: "", endDate: "", sortOrder: "desc" as const };

function formatDate(value: string) {
	return new Date(value).toLocaleString();
}

export default function AuditLogsPage() {
	const { notify } = useNotification();
	const [filters, setFilters] = useState(initialFilters);
	const [page, setPage] = useState(1);
	const [selectedId, setSelectedId] = useState<number | null>(null);
	const queryFilters: AuditLogFilters = { ...filters, userId: filters.userId ? Number(filters.userId) : undefined, page, pageSize: 25 };
	const query = useQuery({ queryKey: ["audit-logs", queryFilters], queryFn: () => listAuditLogs(queryFilters), refetchInterval: 15000 });
	const usersQuery = useQuery({ queryKey: ["audit-log-users"], queryFn: listAuditUsers });
	const detailQuery = useQuery({ queryKey: ["audit-log", selectedId], queryFn: () => getAuditLog(selectedId as number), enabled: selectedId !== null });
	const logs = query.data?.items ?? [];

	useEffect(() => setPage(1), [filters.search, filters.userId, filters.action, filters.resourceType, filters.status, filters.startDate, filters.endDate, filters.sortOrder]);

	const updateFilter = (key: keyof typeof initialFilters, value: string) => setFilters((current) => ({ ...current, [key]: value }));
	const handleExport = async (format: "csv" | "pdf") => {
		try {
			if (format === "csv") await exportAuditLogsCsv(queryFilters);
			else await exportAuditLogsPdf(queryFilters);
			notify(`Audit logs exported as ${format.toUpperCase()}`, "success");
		} catch {
			notify("Unable to export audit logs", "error");
		}
	};

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Audit Logs</Typography>
				<Typography color="text.secondary">Review company activity, changes, exports, and operational events.</Typography>
			</Box>
			<Paper sx={{ p: 2 }}>
				<Grid container spacing={2}>
					<Grid size={{ xs: 12, md: 4 }}><TextField fullWidth label="Search activity" value={filters.search} onChange={(event) => updateFilter("search", event.target.value)} slotProps={{ input: { startAdornment: <SearchIcon sx={{ mr: 1, color: "text.secondary" }} /> } }} /></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth select label="User" value={filters.userId} onChange={(event) => updateFilter("userId", event.target.value)}><MenuItem value="">All users</MenuItem>{(usersQuery.data ?? []).map((user) => <MenuItem key={user.id} value={user.id}>{user.name}</MenuItem>)}</TextField></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth select label="Action" value={filters.action} onChange={(event) => updateFilter("action", event.target.value)}><MenuItem value="">All actions</MenuItem><MenuItem value="Product Created">Product Created</MenuItem><MenuItem value="Product Updated">Product Updated</MenuItem><MenuItem value="Product Deleted">Product Deleted</MenuItem><MenuItem value="Product Deactivated">Product Deactivated</MenuItem><MenuItem value="Customer Created">Customer Created</MenuItem><MenuItem value="Sale Created">Sale Created</MenuItem><MenuItem value="Import">Import</MenuItem><MenuItem value="User Login">User Login</MenuItem><MenuItem value="User Logout">User Logout</MenuItem><MenuItem value="Stock Adjusted">Stock Adjusted</MenuItem><MenuItem value="Audit Logs Exported">Audit Logs Exported</MenuItem></TextField></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth select label="Resource" value={filters.resourceType} onChange={(event) => updateFilter("resourceType", event.target.value)}><MenuItem value="">All resources</MenuItem><MenuItem value="Product">Product</MenuItem><MenuItem value="Customer">Customer</MenuItem><MenuItem value="Sale">Sale</MenuItem><MenuItem value="Import">Import</MenuItem><MenuItem value="User">User</MenuItem></TextField></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth select label="Status" value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}><MenuItem value="">All statuses</MenuItem><MenuItem value="success">Success</MenuItem><MenuItem value="partial">Partial</MenuItem><MenuItem value="failed">Failed</MenuItem></TextField></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth select label="Sort" value={filters.sortOrder} onChange={(event) => updateFilter("sortOrder", event.target.value)}><MenuItem value="desc">Newest first</MenuItem><MenuItem value="asc">Oldest first</MenuItem></TextField></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 3 }}><TextField fullWidth type="date" label="From" value={filters.startDate} onChange={(event) => updateFilter("startDate", event.target.value)} slotProps={{ inputLabel: { shrink: true } }} /></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 3 }}><TextField fullWidth type="date" label="To" value={filters.endDate} onChange={(event) => updateFilter("endDate", event.target.value)} slotProps={{ inputLabel: { shrink: true } }} /></Grid>
					<Grid size={{ xs: 12, md: 6 }}><Stack direction="row" spacing={1} justifyContent={{ xs: "flex-start", md: "flex-end" }}><Button startIcon={<RefreshIcon />} onClick={() => void query.refetch()}>Refresh</Button><Button startIcon={<DownloadIcon />} onClick={() => void handleExport("csv")}>CSV</Button><Button startIcon={<PictureAsPdfIcon />} onClick={() => void handleExport("pdf")}>PDF</Button></Stack></Grid>
				</Grid>
			</Paper>
			{query.isLoading ? <Box display="grid" sx={{ placeItems: "center", minHeight: 220 }}><CircularProgress /></Box> : null}
			{query.isError ? <Alert severity="error">Unable to load audit activity. Try refreshing the page.</Alert> : null}
			{!query.isLoading && !query.isError && logs.length === 0 ? <Alert severity="info">No activity found for the selected filters.</Alert> : null}
			{logs.length > 0 ? <Paper sx={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr>{["User", "Action", "Resource", "Description", "IP Address", "Timestamp", "Status"].map((heading) => <th key={heading} style={{ textAlign: "left", padding: "14px 10px", borderBottom: "1px solid #e5ddd0", whiteSpace: "nowrap" }}>{heading}</th>)}</tr></thead><tbody>{logs.map((log) => <tr key={log.id} onClick={() => setSelectedId(log.id)} style={{ cursor: "pointer" }}><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de" }}>{log.userName ?? "System"}</td><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de" }}>{log.action}</td><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de" }}>{log.resourceType ?? "-"}{log.resourceId ? ` #${log.resourceId}` : ""}</td><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de", minWidth: 240 }}>{log.description ?? log.resourceName ?? "-"}</td><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de" }}>{log.ipAddress ?? "-"}</td><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de", whiteSpace: "nowrap" }}>{formatDate(log.timestamp)}</td><td style={{ padding: "14px 10px", borderBottom: "1px solid #f0e9de" }}><Chip size="small" label={log.status} color={log.status === "success" ? "success" : log.status === "failed" ? "error" : "warning"} /></td></tr>)}</tbody></table></Paper> : null}
			{query.data && query.data.totalPages > 1 ? <Stack alignItems="center"><Pagination count={query.data.totalPages} page={page} onChange={(_, value) => setPage(value)} color="primary" /></Stack> : null}
			<Dialog open={selectedId !== null} onClose={() => setSelectedId(null)} fullWidth maxWidth="md"><DialogTitle>Audit activity details</DialogTitle><DialogContent>{detailQuery.isLoading ? <CircularProgress /> : detailQuery.data ? <AuditDetails log={detailQuery.data} /> : <Alert severity="error">Unable to load this activity.</Alert>}</DialogContent><DialogActions><Button onClick={() => setSelectedId(null)}>Close</Button></DialogActions></Dialog>
		</Stack>
	);
}

function AuditDetails({ log }: { log: AuditLogItem }) {
	return <Stack spacing={2} sx={{ pt: 1 }}><Typography><strong>User:</strong> {log.userName ?? "System"} {log.userEmail ? `(${log.userEmail})` : ""}</Typography><Typography><strong>Action:</strong> {log.action}</Typography><Typography><strong>Resource:</strong> {log.resourceType ?? "-"} {log.resourceId ? `#${log.resourceId}` : ""} {log.resourceName ?? ""}</Typography><Typography><strong>Description:</strong> {log.description ?? "-"}</Typography><Typography><strong>Timestamp:</strong> {formatDate(log.timestamp)}</Typography><Typography><strong>IP address:</strong> {log.ipAddress ?? "-"}</Typography><Typography><strong>Browser:</strong> {log.userAgent ?? "-"}</Typography><Grid container spacing={2}><Grid size={{ xs: 12, md: 6 }}><Typography fontWeight={700}>Before</Typography><Box component="pre" sx={{ p: 1.5, bgcolor: "grey.100", overflow: "auto" }}>{JSON.stringify(log.beforeValues ?? {}, null, 2)}</Box></Grid><Grid size={{ xs: 12, md: 6 }}><Typography fontWeight={700}>After</Typography><Box component="pre" sx={{ p: 1.5, bgcolor: "grey.100", overflow: "auto" }}>{JSON.stringify(log.afterValues ?? {}, null, 2)}</Box></Grid></Grid></Stack>;
}
