import NotificationsNoneRoundedIcon from "@mui/icons-material/NotificationsNoneRounded";
import DoneAllRoundedIcon from "@mui/icons-material/DoneAllRounded";
import Inventory2RoundedIcon from "@mui/icons-material/Inventory2Rounded";
import { Alert, Badge, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, IconButton, MenuItem, Popover, Stack, Tab, Tabs, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getUnreadNotificationCount, listNotifications, markAllNotificationsRead, markNotificationRead, NotificationItem, NotificationPriority, NotificationReadFilter } from "../api/notificationApi";
import { useNotification } from "../context/NotificationContext";

const priorities: NotificationPriority[] = ["low", "medium", "high", "critical"];
const priorityColor: Record<NotificationPriority, "default" | "info" | "warning" | "error"> = { low: "info", medium: "warning", high: "warning", critical: "error" };

function relativeTime(date: string) {
	const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60000));
	if (minutes < 1) return "Just now";
	if (minutes < 60) return `${minutes}m ago`;
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;
	return `${Math.floor(hours / 24)}d ago`;
}

function destination(item: NotificationItem) {
	if (item.resourceType === "Import") return "/data-import";
	if (item.resourceType === "Product") return "/inventory";
	if (item.resourceType === "Sale") return "/sales";
	return null;
}

export default function NotificationCenter() {
	const queryClient = useQueryClient();
	const navigate = useNavigate();
	const { notify } = useNotification();
	const [anchor, setAnchor] = useState<HTMLElement | null>(null);
	const [readFilter, setReadFilter] = useState<NotificationReadFilter>("all");
	const [type, setType] = useState("");
	const [priority, setPriority] = useState<NotificationPriority | "">("");
	const [selected, setSelected] = useState<NotificationItem | null>(null);
	const open = Boolean(anchor);
	const filters = { page: 1, pageSize: 30, read: readFilter, type, priority: priority || undefined };
	const countQuery = useQuery({ queryKey: ["notification-unread-count"], queryFn: getUnreadNotificationCount, refetchInterval: 20000 });
	const listQuery = useQuery({ queryKey: ["notification-list", filters], queryFn: () => listNotifications(filters), enabled: open, refetchInterval: open ? 20000 : false });
	const refresh = async () => {
		await Promise.all([
			queryClient.invalidateQueries({ queryKey: ["notification-unread-count"] }),
			queryClient.invalidateQueries({ queryKey: ["notification-list"] }),
		]);
	};
	const readMutation = useMutation({ mutationFn: markNotificationRead, onSuccess: async () => refresh(), onError: () => notify("Unable to update notification", "error") });
	const readAllMutation = useMutation({ mutationFn: markAllNotificationsRead, onSuccess: async () => refresh(), onError: () => notify("Unable to mark notifications as read", "error") });
	const items = listQuery.data?.items ?? [];

	const openDetails = (item: NotificationItem) => {
		if (!item.isRead) readMutation.mutate(item.id);
		setSelected(item);
	};
	const goToResource = () => {
		if (!selected) return;
		const path = destination(selected);
		setSelected(null);
		setAnchor(null);
		if (path) navigate(path);
	};

	return <>
		<IconButton aria-label="Open notifications" onClick={(event) => setAnchor(event.currentTarget)} sx={{ color: "text.secondary", bgcolor: "rgba(99,102,241,.06)" }}>
			<Badge color="error" badgeContent={countQuery.data ?? 0} max={99}><NotificationsNoneRoundedIcon /></Badge>
		</IconButton>
		<Popover open={open} anchorEl={anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: "bottom", horizontal: "right" }} transformOrigin={{ vertical: "top", horizontal: "right" }} PaperProps={{ sx: { width: { xs: "calc(100vw - 24px)", sm: 460 }, maxHeight: "min(680px, calc(100vh - 100px))", p: 2, borderRadius: 3 } }}>
			<Stack spacing={1.5}>
				<Stack direction="row" alignItems="center" justifyContent="space-between"><Box><Typography variant="h6" fontWeight={800}>Notifications</Typography><Typography variant="caption" color="text.secondary">{countQuery.data ?? 0} unread</Typography></Box><Button size="small" startIcon={<DoneAllRoundedIcon />} disabled={!countQuery.data || readAllMutation.isPending} onClick={() => readAllMutation.mutate()}>Mark all read</Button></Stack>
				<Tabs value={readFilter} onChange={(_, value: NotificationReadFilter) => setReadFilter(value)} variant="fullWidth"><Tab value="all" label="All" /><Tab value="unread" label="Unread" /><Tab value="read" label="Read" /></Tabs>
				<Stack direction="row" spacing={1}><TextField select fullWidth size="small" label="Type" value={type} onChange={(event) => setType(event.target.value)}><MenuItem value="">All types</MenuItem>{["stockout", "stockout-risk", "low-stock", "overstock", "import-completed", "import-failed", "sales-alert", "system-alert"].map((value) => <MenuItem key={value} value={value}>{value.replace(/-/g, " ")}</MenuItem>)}</TextField><TextField select fullWidth size="small" label="Priority" value={priority} onChange={(event) => setPriority(event.target.value as NotificationPriority | "")}><MenuItem value="">All priorities</MenuItem>{priorities.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField></Stack>
				<Divider />
				<Box sx={{ overflowY: "auto", maxHeight: 430 }}>
					{listQuery.isLoading ? <Box sx={{ minHeight: 160, display: "grid", placeItems: "center" }}><CircularProgress size={28} /></Box> : null}
					{listQuery.isError ? <Alert severity="error">Notifications could not be loaded. Please try again.</Alert> : null}
					{!listQuery.isLoading && !listQuery.isError && items.length === 0 ? <Typography color="text.secondary" textAlign="center" sx={{ py: 5 }}>You’re all caught up. No notifications match these filters.</Typography> : null}
					<Stack spacing={1}>{items.map((item) => <Box key={item.id} onClick={() => openDetails(item)} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") openDetails(item); }} sx={{ p: 1.5, borderRadius: 2, cursor: "pointer", bgcolor: item.isRead ? "transparent" : "rgba(99,102,241,.07)", border: "1px solid", borderColor: item.isRead ? "divider" : "rgba(99,102,241,.18)", "&:hover": { bgcolor: "rgba(99,102,241,.10)" } }}><Stack direction="row" alignItems="flex-start" spacing={1}><Inventory2RoundedIcon fontSize="small" color="action" sx={{ mt: .4 }} /><Box sx={{ minWidth: 0, flex: 1 }}><Stack direction="row" spacing={.5} alignItems="center" flexWrap="wrap"><Typography fontWeight={item.isRead ? 600 : 800}>{item.title}</Typography><Chip size="small" label={item.priority} color={priorityColor[item.priority]} /><Typography variant="caption" color="text.secondary" sx={{ ml: "auto !important" }}>{relativeTime(item.createdAt)}</Typography></Stack><Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>{item.message}</Typography>{item.resolvedAt ? <Typography variant="caption" color="success.main">Condition resolved · {new Date(item.resolvedAt).toLocaleString()}</Typography> : null}</Box></Stack></Box>)}</Stack>
				</Box>
			</Stack>
		</Popover>
		<Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="sm"><DialogTitle>{selected?.title}</DialogTitle><DialogContent><Stack spacing={1.5} sx={{ pt: 1 }}><Stack direction="row" spacing={1}><Chip label={selected?.type.replace(/-/g, " ")} /><Chip label={selected?.priority} color={selected ? priorityColor[selected.priority] : "default"} /></Stack><Typography>{selected?.message}</Typography><Typography variant="body2" color="text.secondary">Created {selected ? new Date(selected.createdAt).toLocaleString() : ""}</Typography>{selected?.resolvedAt ? <Alert severity="success">This condition was resolved at {new Date(selected.resolvedAt).toLocaleString()}.</Alert> : null}{selected?.details ? <Box component="pre" sx={{ p: 1.5, borderRadius: 2, bgcolor: "grey.100", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(selected.details, null, 2)}</Box> : null}</Stack></DialogContent><DialogActions><Button onClick={() => setSelected(null)}>Close</Button>{selected && destination(selected) ? <Button variant="contained" onClick={goToResource}>View {selected?.resourceType}</Button> : null}</DialogActions></Dialog>
	</>;
}
