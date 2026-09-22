import AssessmentRoundedIcon from "@mui/icons-material/AssessmentRounded";
import HistoryRoundedIcon from "@mui/icons-material/HistoryRounded";
import CategoryRoundedIcon from "@mui/icons-material/CategoryRounded";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import Inventory2RoundedIcon from "@mui/icons-material/Inventory2Rounded";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import NotificationsNoneRoundedIcon from "@mui/icons-material/NotificationsNoneRounded";
import PersonRoundedIcon from "@mui/icons-material/PersonRounded";
import PointOfSaleRoundedIcon from "@mui/icons-material/PointOfSaleRounded";
import PublishRoundedIcon from "@mui/icons-material/PublishRounded";
import ShowChartRoundedIcon from "@mui/icons-material/ShowChartRounded";
import { AppBar, Avatar, Box, Button, Divider, Drawer, IconButton, List, ListItemButton, ListItemIcon, ListItemText, Stack, Toolbar, Tooltip, Typography, useMediaQuery, useTheme } from "@mui/material";
import { ReactNode, useState } from "react";
import { motion } from "framer-motion";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function DashboardLayout() {
	const [open, setOpen] = useState(false);
	const [collapsed, setCollapsed] = useState(false);
	const location = useLocation();
	const { logoutUser, user } = useAuth();
	const theme = useTheme();
	const mobile = useMediaQuery(theme.breakpoints.down("md"));
	const isAdmin = user?.role === "Company Admin" || user?.role === "Super Admin";
	const canUseSales = isAdmin || user?.role === "Analyst";
	const navigationItems: Array<{ label: string; to: string; icon: ReactNode }> = [
		{ label: "Dashboard", to: "/dashboard", icon: <DashboardRoundedIcon /> },
		{ label: "Profile", to: "/profile", icon: <PersonRoundedIcon /> },
		...(canUseSales ? [{ label: "Forecasting", to: "/inventory/forecast", icon: <ShowChartRoundedIcon /> }] : []),
		...(canUseSales ? [{ label: "Customers", to: "/customers", icon: <GroupsRoundedIcon /> }] : []),
		...(canUseSales ? [{ label: "Inventory", to: "/inventory", icon: <Inventory2RoundedIcon /> }] : []),
		...(canUseSales ? [{ label: "Sales", to: "/sales", icon: <PointOfSaleRoundedIcon /> }] : []),
		...(isAdmin ? [{ label: "Categories", to: "/categories", icon: <CategoryRoundedIcon /> }, { label: "Products", to: "/products", icon: <AssessmentRoundedIcon /> }, { label: "Data Import", to: "/data-import", icon: <PublishRoundedIcon /> }, { label: "Audit Logs", to: "/audit-logs", icon: <HistoryRoundedIcon /> }] : []),
	];
	const sidebar = (
		<Box sx={{ width: collapsed && !mobile ? 84 : 258, height: "100%", display: "flex", flexDirection: "column", p: 1.5, transition: "width 220ms ease" }}>
			<Stack direction="row" alignItems="center" spacing={1.5} sx={{ px: 1.5, py: 2.25, minHeight: 70 }}>
				<Box sx={{ width: 38, height: 38, borderRadius: 2.5, display: "grid", placeItems: "center", color: "white", background: "linear-gradient(135deg, #6366F1, #8B5CF6)", flexShrink: 0 }}><AssessmentRoundedIcon fontSize="small" /></Box>
				{(!collapsed || mobile) && <Box><Typography fontWeight={800} lineHeight={1.1}>RetailPulse</Typography><Typography variant="caption" color="text.secondary">Analytics suite</Typography></Box>}
			</Stack>
			<Divider sx={{ mb: 1.5, borderColor: "rgba(99,102,241,.10)" }} />
			{(!collapsed || mobile) && <Typography variant="overline" color="text.secondary" sx={{ px: 1.5, mb: 0.75, fontWeight: 800 }}>Workspace</Typography>}
			<List disablePadding sx={{ flex: 1 }}>
				{navigationItems.map((item) => {
					const selected = location.pathname === item.to || (item.to === "/inventory/forecast" && location.pathname.startsWith("/inventory/forecast"));
					return <Tooltip key={item.to} title={collapsed && !mobile ? item.label : ""} placement="right"><ListItemButton component={RouterLink} to={item.to} selected={selected} onClick={() => setOpen(false)} sx={{ minHeight: 46, mb: 0.5, borderRadius: 2.5, justifyContent: collapsed && !mobile ? "center" : "initial", px: collapsed && !mobile ? 1 : 1.5, color: selected ? "primary.main" : "text.secondary", "&.Mui-selected": { background: "linear-gradient(90deg, rgba(99,102,241,.14), rgba(139,92,246,.05))", color: "primary.main", "&:before": { content: '""', position: "absolute", left: 0, width: 3, height: 22, borderRadius: 2, background: "#6366F1" } } }}><ListItemIcon sx={{ minWidth: collapsed && !mobile ? 0 : 38, color: "inherit" }}>{item.icon}</ListItemIcon>{(!collapsed || mobile) && <ListItemText primary={item.label} primaryTypographyProps={{ fontWeight: selected ? 750 : 600 }} />}</ListItemButton></Tooltip>;
				})}
			</List>
			{(!collapsed || mobile) && <Box sx={{ p: 1.5, mb: 1, borderRadius: 3, background: "linear-gradient(135deg, rgba(99,102,241,.11), rgba(139,92,246,.12))" }}><Typography variant="caption" fontWeight={800}>Workspace health</Typography><Box sx={{ height: 6, bgcolor: "rgba(99,102,241,.14)", borderRadius: 4, mt: 1 }}><Box sx={{ width: "78%", height: "100%", bgcolor: "#6366F1", borderRadius: 4 }} /></Box><Typography variant="caption" color="text.secondary">78% optimized</Typography></Box>}
			{!mobile && <IconButton onClick={() => setCollapsed((value) => !value)} sx={{ alignSelf: collapsed ? "center" : "flex-end", color: "text.secondary" }}>{collapsed ? <ChevronRightRoundedIcon /> : <ChevronLeftRoundedIcon />}</IconButton>}
		</Box>
	);

	return (
		<Box minHeight="100vh" sx={{ display: "flex", bgcolor: "background.default" }}>
			{mobile ? <Drawer open={open} onClose={() => setOpen(false)} PaperProps={{ sx: { background: "rgba(255,255,255,.94)" } }}>{sidebar}</Drawer> : <Box component="aside" sx={{ width: collapsed ? 84 : 258, flexShrink: 0, transition: "width 220ms ease", borderRight: "1px solid rgba(99,102,241,.10)", background: "rgba(255,255,255,.66)" }}>{sidebar}</Box>}
			<Box sx={{ minWidth: 0, flex: 1 }}>
			<AppBar position="sticky" color="inherit" elevation={0} sx={{ background: "rgba(246,247,251,.76)", backdropFilter: "blur(18px)", borderBottom: "1px solid rgba(99,102,241,.10)" }}>
				<Toolbar sx={{ minHeight: 76 }}>
					{mobile && <IconButton onClick={() => setOpen(true)} sx={{ mr: 1 }}><MenuIcon /></IconButton>}
					<Box sx={{ flexGrow: 1 }}><Typography variant="h6" fontWeight={800}>{navigationItems.find((item) => location.pathname === item.to)?.label ?? "Overview"}</Typography><Typography variant="caption" color="text.secondary">Good to see you, {user?.name?.split(" ")[0] ?? "there"}</Typography></Box>
					<Stack direction="row" spacing={1.5} alignItems="center"><IconButton aria-label="Notifications" sx={{ color: "text.secondary", bgcolor: "rgba(99,102,241,.06)" }}><NotificationsNoneRoundedIcon /></IconButton><Divider orientation="vertical" flexItem sx={{ my: 1.5 }} /><Avatar sx={{ width: 36, height: 36, bgcolor: "primary.main", fontWeight: 800 }}>{user?.name?.charAt(0) ?? "U"}</Avatar><Box sx={{ display: { xs: "none", sm: "block" } }}><Typography variant="body2" fontWeight={750}>{user?.name}</Typography><Typography variant="caption" color="text.secondary">{user?.company.name}</Typography></Box><Button aria-label="Log out" onClick={() => void logoutUser()} color="inherit" sx={{ minWidth: 0, px: 1 }}><LogoutIcon fontSize="small" /></Button></Stack>
				</Toolbar>
			</AppBar>
			<Box component={motion.div} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: "easeOut" }} sx={{ maxWidth: 1480, mx: "auto", px: { xs: 2, md: 4 }, py: { xs: 3, md: 4 } }}>
				<Outlet />
			</Box>
			</Box>
		</Box>
	);
}
