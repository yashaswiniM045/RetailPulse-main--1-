import {
	Alert,
	Box,
	Card,
	CardContent,
	Chip,
	CircularProgress,
	FormControlLabel,
	Grid,
	MenuItem,
	Paper,
	Select,
	Stack,
	Switch,
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableRow,
	TextField,
	Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getInventoryForecast, getInventoryRecommendation } from "../../api/catalogApi";
import { InventoryForecastRisk, InventoryForecastSort } from "../../types/catalog";

const riskLabels: Record<InventoryForecastRisk, string> = {
	"out-of-stock": "Out of stock",
	"stockout-risk": "Stockout risk",
	"low-stock": "Low stock",
	healthy: "Healthy",
	overstock: "Overstock",
};

const riskColors: Record<InventoryForecastRisk, "error" | "warning" | "success" | "info"> = {
	"out-of-stock": "error",
	"stockout-risk": "error",
	"low-stock": "warning",
	healthy: "success",
	overstock: "info",
};

export default function InventoryForecastPage() {
	const [search, setSearch] = useState("");
	const [risk, setRisk] = useState<InventoryForecastRisk | "all">("all");
	const [supplier, setSupplier] = useState("");
	const [reorderOnly, setReorderOnly] = useState(false);
	const [sortBy, setSortBy] = useState<InventoryForecastSort>("risk");
	const [selectedId, setSelectedId] = useState<number | null>(null);
	const query = useQuery({
		queryKey: ["inventory-forecast", search, risk, supplier, reorderOnly, sortBy],
		queryFn: () => getInventoryForecast({ search: search || undefined, stockRisk: risk === "all" ? undefined : risk, supplier: supplier || undefined, reorderRequired: reorderOnly ? true : undefined, sortBy, sortDirection: "desc", pageSize: 100 }),
		staleTime: 60_000,
	});
	const selectedFromList = query.data?.items.find((item) => item.productId === selectedId);
	const detailQuery = useQuery({
		queryKey: ["inventory-recommendation", selectedId],
		queryFn: () => getInventoryRecommendation(selectedId as number),
		enabled: selectedId !== null,
	});
	const selected = detailQuery.data ?? selectedFromList;

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Inventory Forecast & Replenishment</Typography>
				<Typography color="text.secondary">Live demand signals from the last {query.data?.historicalWindowDays ?? 90} days, projected across the next {query.data?.forecastHorizonDays ?? 30} days.</Typography>
			</Box>

			{query.isError ? <Alert severity="error">Unable to load inventory forecasts. Check the API connection and try again.</Alert> : null}
			<Grid container spacing={2}>
				{[
					["Products requiring reorder", query.data?.summary.productsRequiringReorder ?? 0, "warning"],
					["Stockout risk", query.data?.summary.productsAtStockoutRisk ?? 0, "error"],
					["Overstocked", query.data?.summary.overstockedProducts ?? 0, "info"],
					["Healthy", query.data?.summary.healthyProducts ?? 0, "success"],
				].map(([label, value, color]) => (
					<Grid key={String(label)} size={{ xs: 12, sm: 6, md: 3 }}>
						<Card><CardContent><Typography color="text.secondary">{label}</Typography><Typography variant="h4" fontWeight={700} color={`${color}.main`}>{value}</Typography></CardContent></Card>
					</Grid>
				))}
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Grid container spacing={2} alignItems="center">
					<Grid size={{ xs: 12, md: 3 }}><TextField fullWidth label="Product or SKU" value={search} onChange={(event) => setSearch(event.target.value)} /></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth label="Stock risk" select value={risk} onChange={(event) => setRisk(event.target.value as InventoryForecastRisk | "all")}><MenuItem value="all">All risks</MenuItem>{Object.entries(riskLabels).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth label="Supplier" value={supplier} onChange={(event) => setSupplier(event.target.value)} /></Grid>
					<Grid size={{ xs: 12, sm: 6, md: 2 }}><TextField fullWidth label="Sort by" select value={sortBy} onChange={(event) => setSortBy(event.target.value as InventoryForecastSort)}><MenuItem value="risk">Risk level</MenuItem><MenuItem value="currentStock">Current stock</MenuItem><MenuItem value="forecastedDemand">Forecasted demand</MenuItem><MenuItem value="daysRemaining">Days remaining</MenuItem><MenuItem value="recommendedQuantity">Recommended quantity</MenuItem></TextField></Grid>
					<Grid size={{ xs: 12, md: 3 }}><FormControlLabel control={<Switch checked={reorderOnly} onChange={(event) => setReorderOnly(event.target.checked)} />} label="Reorder required only" /></Grid>
				</Grid>
			</Paper>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 8 }}>
					<Paper sx={{ p: 2, overflowX: "auto" }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Replenishment decisions</Typography>
						{query.isLoading ? <Box sx={{ display: "grid", placeItems: "center", minHeight: 260 }}><CircularProgress /></Box> : query.data?.items.length === 0 ? <Alert severity="info">No products match these filters. Products with no sales history are included with zero demand.</Alert> : <Table size="small"><TableHead><TableRow>{["Product", "Stock", "Daily sales", "Forecast", "Days left", "Reorder point", "Qty", "Risk", "Recommendation"].map((heading) => <TableCell key={heading}>{heading}</TableCell>)}</TableRow></TableHead><TableBody>{query.data?.items.map((item) => <TableRow hover selected={item.productId === selectedId} key={item.productId} onClick={() => setSelectedId(item.productId)} sx={{ cursor: "pointer" }}><TableCell><Typography fontWeight={600}>{item.productName}</Typography><Typography variant="caption" color="text.secondary">{item.sku} · {item.categoryName}</Typography></TableCell><TableCell>{item.currentStock}</TableCell><TableCell>{item.averageDailySales.toFixed(2)}</TableCell><TableCell>{item.forecastedDemand.toFixed(1)}</TableCell><TableCell>{item.daysOfStockRemaining === null ? "N/A" : `${item.daysOfStockRemaining}d`}</TableCell><TableCell>{item.reorderPoint}</TableCell><TableCell sx={{ fontWeight: 700 }}>{item.recommendedReorderQuantity}</TableCell><TableCell><Chip size="small" color={riskColors[item.stockRisk]} label={riskLabels[item.stockRisk]} /></TableCell><TableCell>{item.recommendation}</TableCell></TableRow>)}</TableBody></Table>}
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2, height: "100%" }}>
						<Typography variant="h6" fontWeight={700}>Recommendation comparison</Typography>
						{!selected ? <Typography color="text.secondary" sx={{ mt: 2 }}>Select a product to inspect its current and recommended inventory position.</Typography> : <Stack spacing={2} sx={{ mt: 2 }}><Box><Typography variant="h6">{selected.productName}</Typography><Typography color="text.secondary">{selected.sku} · {selected.supplier ?? "Supplier not recorded"}</Typography></Box><Chip color={riskColors[selected.stockRisk]} label={`${riskLabels[selected.stockRisk]} · ${selected.recommendation}`} /><Table size="small"><TableBody>{[["Stock", selected.currentStock, selected.currentStock + selected.recommendedReorderQuantity], ["Daily demand", selected.averageDailySales, selected.averageDailySales], ["Reorder point", selected.reorderPoint, selected.reorderPoint], ["Safety stock", selected.safetyStock, selected.safetyStock]].map(([metric, current, recommended]) => <TableRow key={String(metric)}><TableCell>{metric}</TableCell><TableCell align="right">{current}</TableCell><TableCell align="right" sx={{ fontWeight: 700, color: current !== recommended ? "warning.main" : "inherit" }}>{recommended}</TableCell></TableRow>)}</TableBody></Table><Box sx={{ height: 190 }}><ResponsiveContainer width="100%" height="100%"><LineChart data={selected.historicalDemand.slice(-30)}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" hide /><YAxis /><Tooltip /><Line type="monotone" dataKey="demand" stroke="#007f8b" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></Box><Typography variant="caption" color="text.secondary">Historical daily demand, last 30 days</Typography></Stack>}
					</Paper>
				</Grid>
			</Grid>
		</Stack>
	);
}
