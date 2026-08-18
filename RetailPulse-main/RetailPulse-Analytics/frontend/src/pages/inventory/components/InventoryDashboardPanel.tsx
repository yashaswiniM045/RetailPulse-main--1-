import { Alert, Button, Card, CardContent, Grid, Paper, Stack, Typography } from "@mui/material";
import {
	Bar,
	BarChart,
	Cell,
	Legend,
	Pie,
	PieChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import { InventoryDashboardSummary } from "../../../types/catalog";
import { stockStatusLabel } from "../constants";

type Props = {
	dashboard: InventoryDashboardSummary | undefined;
	isError: boolean;
	errorMessage: string;
	onRetry: () => void;
	isRetrying: boolean;
};

const PIE_COLORS = ["#3f8f4f", "#f0a53a", "#d9534f"];

export default function InventoryDashboardPanel({
	dashboard,
	isError,
	errorMessage,
	onRetry,
	isRetrying,
}: Props) {
	const categoryData = dashboard?.inventoryByCategory ?? [];
	const statusData = (dashboard?.stockStatusDistribution ?? []).map((item) => ({
		name: stockStatusLabel[item.status],
		value: item.count,
	}));

	return (
		<Stack spacing={2}>
			{isError ? (
				<Alert
					severity="error"
					action={
						<Button color="inherit" size="small" onClick={onRetry} disabled={isRetrying}>
							Retry
						</Button>
					}
				>
					{errorMessage}
				</Alert>
			) : null}

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card>
						<CardContent>
							<Typography color="text.secondary">Total Products</Typography>
							<Typography variant="h4" fontWeight={700}>{dashboard?.totalProducts ?? 0}</Typography>
						</CardContent>
					</Card>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card>
						<CardContent>
							<Typography color="text.secondary">Total Inventory Qty</Typography>
							<Typography variant="h4" fontWeight={700}>{dashboard?.totalInventoryQuantity ?? 0}</Typography>
						</CardContent>
					</Card>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card>
						<CardContent>
							<Typography color="text.secondary">Low Stock Products</Typography>
							<Typography variant="h4" fontWeight={700}>{dashboard?.lowStockProducts ?? 0}</Typography>
						</CardContent>
					</Card>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card>
						<CardContent>
							<Typography color="text.secondary">Out of Stock Products</Typography>
							<Typography variant="h4" fontWeight={700}>{dashboard?.outOfStockProducts ?? 0}</Typography>
						</CardContent>
					</Card>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 7 }}>
					<Paper sx={{ p: 2, height: 360 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Inventory By Category</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={categoryData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
								<XAxis dataKey="category" tickLine={false} axisLine={false} />
								<YAxis allowDecimals={false} tickLine={false} axisLine={false} />
								<Tooltip />
								<Legend />
								<Bar dataKey="totalQuantity" fill="#0f4c5c" name="Total Qty" radius={[6, 6, 0, 0]} />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 5 }}>
					<Paper sx={{ p: 2, height: 360 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Stock Status Distribution</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<PieChart>
								<Tooltip />
								<Legend />
								<Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={110}>
									{statusData.map((_, index) => (
										<Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
									))}
								</Pie>
							</PieChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>
		</Stack>
	);
}
