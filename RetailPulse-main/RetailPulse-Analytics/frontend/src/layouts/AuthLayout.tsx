import AutoGraphRoundedIcon from "@mui/icons-material/AutoGraphRounded";
import LockRoundedIcon from "@mui/icons-material/LockRounded";
import InsightsRoundedIcon from "@mui/icons-material/InsightsRounded";
import { Box, Chip, Container, Paper, Stack, Typography } from "@mui/material";
import { Outlet } from "react-router-dom";

export default function AuthLayout() {
	return (
		<Box
			minHeight="100vh"
			sx={{
				background: "radial-gradient(circle at 85% 15%, rgba(139,92,246,.45), transparent 34%), linear-gradient(135deg, #312E81 0%, #6366F1 48%, #EEF0FF 100%)",
				display: "flex",
				alignItems: "center",
				py: { xs: 3, md: 6 },
			}}
		>
			<Container maxWidth="lg">
				<Paper elevation={6} sx={{ overflow: "hidden", borderRadius: 5, boxShadow: "0 28px 80px rgba(31, 27, 91, .26)" }}>
					<Stack direction={{ xs: "column", md: "row" }}>
						<Box sx={{ flex: 1, color: "white", p: { xs: 3, md: 5 }, background: "linear-gradient(150deg, #4338CA 0%, #6366F1 58%, #8B5CF6 100%)", position: "relative", overflow: "hidden", "&:after": { content: '""', position: "absolute", width: 300, height: 300, borderRadius: "50%", right: -120, bottom: -140, border: "1px solid rgba(255,255,255,.22)" } }}>
							<Stack direction="row" spacing={1} alignItems="center"><AutoGraphRoundedIcon /><Typography variant="overline" sx={{ letterSpacing: ".12em", fontWeight: 800 }}>RetailPulse Analytics</Typography></Stack>
							<Typography variant="h3" fontWeight={800} sx={{ mt: 2 }}>
								Clarity for every business decision.
							</Typography>
							<Typography sx={{ mt: 2, color: "rgba(255,255,255,0.8)", maxWidth: 420 }}>
								Bring sales, inventory, customers, and forecasts together in one calm, powerful workspace.
							</Typography>
							<Stack direction="row" spacing={1} sx={{ mt: 4, position: "relative", zIndex: 1 }}><Chip icon={<InsightsRoundedIcon />} label="Real-time insight" sx={{ color: "white", bgcolor: "rgba(255,255,255,.14)" }} /><Chip icon={<LockRoundedIcon />} label="Secure by design" sx={{ color: "white", bgcolor: "rgba(255,255,255,.14)" }} /></Stack>
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
