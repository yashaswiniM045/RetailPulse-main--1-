import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { Outlet } from "react-router-dom";

export default function AuthLayout() {
	return (
		<Box
			minHeight="100vh"
			sx={{
				background: "linear-gradient(135deg, #0f4c5c 0%, #1f7a8c 45%, #f4f1ea 100%)",
				display: "flex",
				alignItems: "center",
				py: 6,
			}}
		>
			<Container maxWidth="lg">
				<Paper elevation={6} sx={{ overflow: "hidden", borderRadius: 4 }}>
					<Stack direction={{ xs: "column", md: "row" }}>
						<Box sx={{ flex: 1, bgcolor: "primary.main", color: "white", p: 5 }}>
							<Typography variant="overline">RetailPulse Analytics</Typography>
							<Typography variant="h3" fontWeight={800} sx={{ mt: 2 }}>
								Secure multi-company analytics, ready from day one.
							</Typography>
							<Typography sx={{ mt: 2, color: "rgba(255,255,255,0.8)" }}>
								Register your company, onboard the first admin, and access dashboards with strict company isolation.
							</Typography>
						</Box>
						<Box sx={{ flex: 1.1, p: { xs: 3, md: 5 } }}>
							<Outlet />
						</Box>
					</Stack>
				</Paper>
			</Container>
		</Box>
	);
}
