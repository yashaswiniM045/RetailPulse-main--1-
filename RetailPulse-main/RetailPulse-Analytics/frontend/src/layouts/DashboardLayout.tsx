import MenuIcon from "@mui/icons-material/Menu";
import LogoutIcon from "@mui/icons-material/Logout";
import { AppBar, Box, Button, Drawer, IconButton, List, ListItemButton, ListItemText, Stack, Toolbar, Typography } from "@mui/material";
import { useState } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function DashboardLayout() {
	const [open, setOpen] = useState(false);
	const location = useLocation();
	const { logoutUser, user } = useAuth();
	const isAdmin = user?.role === "Company Admin" || user?.role === "Super Admin";
	const canUseSales = isAdmin || user?.role === "Analyst";
	const navigationItems = [
		{ label: "Dashboard", to: "/dashboard" },
		{ label: "Profile", to: "/profile" },
		...(canUseSales ? [{ label: "Forecasting", to: "/forecasting" }] : []),
		...(canUseSales ? [{ label: "Customers", to: "/customers" }] : []),
		...(canUseSales ? [{ label: "Inventory", to: "/inventory" }] : []),
		...(canUseSales ? [{ label: "Sales", to: "/sales" }] : []),
		...(isAdmin ? [{ label: "Categories", to: "/categories" }, { label: "Products", to: "/products" }] : []),
	];

	return (
		<Box minHeight="100vh" sx={{ bgcolor: "background.default" }}>
			<AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: "1px solid #e5ddd0" }}>
				<Toolbar>
					<IconButton edge="start" onClick={() => setOpen(true)} sx={{ mr: 2 }}>
						<MenuIcon />
					</IconButton>
					<Typography variant="h6" fontWeight={700} sx={{ flexGrow: 1 }}>
						RetailPulse Analytics
					</Typography>
					<Stack direction="row" spacing={2} alignItems="center">
						<Typography color="text.secondary">{user?.company.name}</Typography>
						<Button startIcon={<LogoutIcon />} color="inherit" onClick={() => void logoutUser()}>
							Logout
						</Button>
					</Stack>
				</Toolbar>
			</AppBar>

			<Drawer open={open} onClose={() => setOpen(false)}>
				<Box sx={{ width: 260, p: 2 }}>
					<Typography variant="h6" fontWeight={700} sx={{ px: 2, py: 1 }}>
						Workspace
					</Typography>
					<List>
						{navigationItems.map((item) => (
							<ListItemButton
								key={item.to}
								component={RouterLink}
								to={item.to}
								selected={location.pathname === item.to}
								onClick={() => setOpen(false)}
							>
								<ListItemText primary={item.label} />
							</ListItemButton>
						))}
					</List>
				</Box>
			</Drawer>

			<Box sx={{ maxWidth: 1200, mx: "auto", px: 3, py: 4 }}>
				<Outlet />
			</Box>
		</Box>
	);
}
