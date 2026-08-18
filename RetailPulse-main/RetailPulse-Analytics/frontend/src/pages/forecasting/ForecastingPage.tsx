import DownloadIcon from "@mui/icons-material/Download";
import {
	Alert,
	Box,
	Button,
	Card,
	CardContent,
	Chip,
	Grid,
	MenuItem,
	Paper,
	Stack,
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableRow,
	TextField,
	Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
	Bar,
	BarChart,
	Cell,
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	Pie,
	PieChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	exportCategoryForecastCsv,
	exportDemandForecastCsv,
	exportProductForecastPdf,
	generateForecasts,
	getForecastDashboard,
	getForecastFilters,
	listForecastNotifications,
	listForecastProducts,
} from "../../api/catalogApi";
import { useNotification } from "../../context/NotificationContext";
import { ForecastPeriod, ForecastRecommendationType, ForecastSortBy, ForecastSortDirection } from "../../types/catalog";

const currencyFormatter = new Intl.NumberFormat("en-US", {
	style: "currency",
	currency: "USD",
	minimumFractionDigits: 2,
	maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("en-US");
const pieColors = ["#005f73", "#0a9396", "#94d2bd", "#ee9b00", "#bb3e03", "#9b2226"];

function triggerBlobDownload(blob: Blob, fileName: string) {
	const objectUrl = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = objectUrl;
	link.download = fileName;
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(objectUrl);
}

export default function ForecastingPage() {
	const queryClient = useQueryClient();
	const { notify } = useNotification();
	const [forecastPeriod, setForecastPeriod] = useState<ForecastPeriod>("next-30-days");
	const [customStartDate, setCustomStartDate] = useState("");
	const [customEndDate, setCustomEndDate] = useState("");
	const [productId, setProductId] = useState<number | "all">("all");
	const [categoryId, setCategoryId] = useState<number | "all">("all");
	const [brand, setBrand] = useState<string | "all">("all");
	const [search, setSearch] = useState("");
	const [sortBy, setSortBy] = useState<ForecastSortBy>("highestPredictedDemand");
	const [sortDirection, setSortDirection] = useState<ForecastSortDirection>("desc");
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState(10);

	const periodParams = useMemo(
		() => ({
			forecastPeriod,
			customStartDate: forecastPeriod === "custom" && customStartDate ? customStartDate : undefined,
			customEndDate: forecastPeriod === "custom" && customEndDate ? customEndDate : undefined,
		}),
		[forecastPeriod, customStartDate, customEndDate],
	);

	const { data: filters } = useQuery({
		queryKey: ["forecast-filters"],
		queryFn: getForecastFilters,
	});

	const dashboardQuery = useQuery({
		queryKey: ["forecast-dashboard", periodParams],
		queryFn: () => getForecastDashboard(periodParams),
		retry: false,
	});

	const productsQuery = useQuery({
		queryKey: ["forecast-products", periodParams, productId, categoryId, brand, search, sortBy, sortDirection, page, pageSize],
		queryFn: () =>
			listForecastProducts({
				...periodParams,
				productId: productId === "all" ? undefined : productId,
				categoryId: categoryId === "all" ? undefined : categoryId,
				brand: brand === "all" ? undefined : brand,
				search: search || undefined,
				sortBy,
				sortDirection,
				page,
				pageSize,
			}),
		enabled: dashboardQuery.isSuccess,
	});

	const notificationsQuery = useQuery({
		queryKey: ["forecast-notifications"],
		queryFn: () => listForecastNotifications(10),
	});

	const generateMutation = useMutation({
		mutationFn: (forceRefresh: boolean) =>
			generateForecasts({
				...periodParams,
				forceRefresh,
			}),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["forecast-dashboard"] });
			await queryClient.invalidateQueries({ queryKey: ["forecast-products"] });
			await queryClient.invalidateQueries({ queryKey: ["forecast-notifications"] });
			notify("Forecast generated successfully", "success");
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Failed to generate forecast", "error"),
	});

	const onExportDemandCsv = async () => {
		try {
			triggerBlobDownload(await exportDemandForecastCsv(periodParams), "demand-forecast-report.csv");
			notify("Demand forecast CSV downloaded", "success");
		} catch (error: any) {
			notify(error?.response?.data?.detail ?? "Unable to export demand report", "error");
		}
	};

	const onExportProductPdf = async () => {
		try {
			triggerBlobDownload(await exportProductForecastPdf(periodParams), "product-forecast-report.pdf");
			notify("Product forecast PDF downloaded", "success");
		} catch (error: any) {
			notify(error?.response?.data?.detail ?? "Unable to export product report", "error");
		}
	};

	const onExportCategoryCsv = async () => {
		try {
			triggerBlobDownload(await exportCategoryForecastCsv(periodParams), "category-forecast-report.csv");
			notify("Category forecast CSV downloaded", "success");
		} catch (error: any) {
			notify(error?.response?.data?.detail ?? "Unable to export category report", "error");
		}
	};

	const recommendationColor = (value: ForecastRecommendationType): "success" | "warning" | "error" | "default" => {
		if (value === "stock-level-healthy") return "success";
		if (value === "reorder-soon") return "warning";
		if (value === "immediate-restock-required") return "error";
		return "default";
	};

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Demand Forecasting</Typography>
				<Typography color="text.secondary">Predict demand, monitor risk, and optimize inventory for upcoming periods.</Typography>
			</Box>

			<Paper sx={{ p: 2.5 }}>
				<Grid container spacing={2}>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select fullWidth label="Forecast Period" value={forecastPeriod} onChange={(e) => setForecastPeriod(e.target.value as ForecastPeriod)}>
							<MenuItem value="next-7-days">Next 7 Days</MenuItem>
							<MenuItem value="next-30-days">Next 30 Days</MenuItem>
							<MenuItem value="next-90-days">Next 90 Days</MenuItem>
							<MenuItem value="custom">Custom</MenuItem>
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField type="date" fullWidth label="Custom Start" value={customStartDate} onChange={(e) => setCustomStartDate(e.target.value)} InputLabelProps={{ shrink: true }} disabled={forecastPeriod !== "custom"} />
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField type="date" fullWidth label="Custom End" value={customEndDate} onChange={(e) => setCustomEndDate(e.target.value)} InputLabelProps={{ shrink: true }} disabled={forecastPeriod !== "custom"} />
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select fullWidth label="Product" value={productId} onChange={(e) => setProductId(e.target.value === "all" ? "all" : Number(e.target.value))}>
							<MenuItem value="all">All</MenuItem>
							{filters?.products.map((item) => (
								<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select fullWidth label="Category" value={categoryId} onChange={(e) => setCategoryId(e.target.value === "all" ? "all" : Number(e.target.value))}>
							<MenuItem value="all">All</MenuItem>
							{filters?.categories.map((item) => (
								<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select fullWidth label="Brand" value={brand} onChange={(e) => setBrand(e.target.value)}>
							<MenuItem value="all">All</MenuItem>
							{filters?.brands.map((item) => (
								<MenuItem key={item} value={item}>{item}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 3 }}>
						<TextField fullWidth label="Search Product / Category" value={search} onChange={(e) => setSearch(e.target.value)} />
					</Grid>
					<Grid size={{ xs: 12, md: 3 }}>
						<TextField select fullWidth label="Sort By" value={sortBy} onChange={(e) => setSortBy(e.target.value as ForecastSortBy)}>
							<MenuItem value="highestPredictedDemand">Highest Predicted Demand</MenuItem>
							<MenuItem value="lowestStock">Lowest Stock</MenuItem>
							<MenuItem value="highestGrowth">Highest Growth</MenuItem>
							<MenuItem value="forecastAccuracy">Forecast Accuracy</MenuItem>
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select fullWidth label="Direction" value={sortDirection} onChange={(e) => setSortDirection(e.target.value as ForecastSortDirection)}>
							<MenuItem value="desc">Desc</MenuItem>
							<MenuItem value="asc">Asc</MenuItem>
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 4 }}>
						<Stack direction="row" spacing={1}>
							<Button variant="contained" onClick={() => generateMutation.mutate(false)} disabled={generateMutation.isPending}>Generate Forecast</Button>
							<Button variant="outlined" onClick={() => generateMutation.mutate(true)} disabled={generateMutation.isPending}>Refresh Forecast</Button>
						</Stack>
					</Grid>
					<Grid size={{ xs: 12, md: 5 }}>
						<Stack direction="row" spacing={1} justifyContent={{ md: "flex-end" }}>
							<Button variant="outlined" startIcon={<DownloadIcon />} onClick={() => void onExportDemandCsv()}>Demand CSV</Button>
							<Button variant="outlined" startIcon={<DownloadIcon />} onClick={() => void onExportCategoryCsv()}>Category CSV</Button>
							<Button variant="contained" startIcon={<DownloadIcon />} onClick={() => void onExportProductPdf()}>Product PDF</Button>
						</Stack>
					</Grid>
				</Grid>
			</Paper>

			{dashboardQuery.isError ? (
				<Alert severity="info">No forecast data available for selected period. Generate a forecast to start analytics.</Alert>
			) : null}

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, md: 4, lg: 2.4 }}><Card><CardContent><Typography color="text.secondary">Total Predicted Demand</Typography><Typography variant="h5" fontWeight={700}>{numberFormatter.format(dashboardQuery.data?.analytics.kpis.totalPredictedDemand ?? 0)}</Typography></CardContent></Card></Grid>
				<Grid size={{ xs: 12, md: 4, lg: 2.4 }}><Card><CardContent><Typography color="text.secondary">Products Expected To Run Out</Typography><Typography variant="h5" fontWeight={700}>{dashboardQuery.data?.analytics.kpis.productsExpectedToRunOut ?? 0}</Typography></CardContent></Card></Grid>
				<Grid size={{ xs: 12, md: 4, lg: 2.4 }}><Card><CardContent><Typography color="text.secondary">High Growth Products</Typography><Typography variant="h5" fontWeight={700}>{dashboardQuery.data?.analytics.kpis.highGrowthProducts ?? 0}</Typography></CardContent></Card></Grid>
				<Grid size={{ xs: 12, md: 4, lg: 2.4 }}><Card><CardContent><Typography color="text.secondary">Slow Moving Products</Typography><Typography variant="h5" fontWeight={700}>{dashboardQuery.data?.analytics.kpis.slowMovingProducts ?? 0}</Typography></CardContent></Card></Grid>
				<Grid size={{ xs: 12, md: 4, lg: 2.4 }}><Card><CardContent><Typography color="text.secondary">Forecast Accuracy</Typography><Typography variant="h5" fontWeight={700}>{(dashboardQuery.data?.analytics.kpis.forecastAccuracy ?? 0).toFixed(2)}%</Typography></CardContent></Card></Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 7 }}>
					<Paper sx={{ p: 2, height: 340 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Historical Sales vs Forecast</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={dashboardQuery.data?.analytics.historicalVsForecast ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="label" hide />
								<YAxis />
								<Tooltip />
								<Legend />
								<Bar dataKey="historical" fill="#2a9d8f" name="Historical" />
								<Bar dataKey="forecast" fill="#e76f51" name="Forecast" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 5 }}>
					<Paper sx={{ p: 2, height: 340 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Top Predicted Products</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<PieChart>
								<Tooltip />
								<Legend />
								<Pie data={dashboardQuery.data?.analytics.topPredictedProducts ?? []} dataKey="predictedDemand" nameKey="productName" outerRadius={100}>
									{(dashboardQuery.data?.analytics.topPredictedProducts ?? []).map((_, index) => (
										<Cell key={`pie-${index}`} fill={pieColors[index % pieColors.length]} />
									))}
								</Pie>
							</PieChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 320 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Product Demand Trend</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<LineChart data={dashboardQuery.data?.analytics.productDemandTrend ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="label" hide />
								<YAxis />
								<Tooltip />
								<Line type="monotone" dataKey="predictedDemand" stroke="#264653" strokeWidth={2} name="Predicted" />
								<Line type="monotone" dataKey="historicalSales" stroke="#2a9d8f" strokeWidth={2} name="Historical" />
							</LineChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 320 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Category Demand Trend</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={dashboardQuery.data?.analytics.categoryDemandTrend ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="label" />
								<YAxis />
								<Tooltip />
								<Bar dataKey="predictedDemand" fill="#b56576" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 8 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Product-Level Forecast</Typography>
						<Table size="small">
							<TableHead>
								<TableRow>
									<TableCell>Product</TableCell>
									<TableCell>Category</TableCell>
									<TableCell align="right">Current Stock</TableCell>
									<TableCell align="right">Historical Sales</TableCell>
									<TableCell align="right">Predicted Demand</TableCell>
									<TableCell align="right">Confidence</TableCell>
									<TableCell align="right">Accuracy</TableCell>
									<TableCell>Recommendation</TableCell>
								</TableRow>
							</TableHead>
							<TableBody>
								{(productsQuery.data?.items ?? []).map((item) => (
									<TableRow key={item.forecastId}>
										<TableCell>{item.productName}</TableCell>
										<TableCell>{item.categoryName}</TableCell>
										<TableCell align="right">{numberFormatter.format(item.currentStock)}</TableCell>
										<TableCell align="right">{numberFormatter.format(item.historicalSales)}</TableCell>
										<TableCell align="right">{numberFormatter.format(item.predictedDemand)}</TableCell>
										<TableCell align="right">{item.confidenceLevel.toFixed(1)}%</TableCell>
										<TableCell align="right">{item.accuracy !== null ? `${item.accuracy.toFixed(1)}%` : "-"}</TableCell>
										<TableCell><Chip label={item.recommendationType} color={recommendationColor(item.recommendationType)} size="small" /></TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>

						<Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }} sx={{ mt: 2 }}>
							<Typography color="text.secondary">Showing {productsQuery.data?.total ?? 0} forecasted products</Typography>
							<Stack direction="row" spacing={1}>
								<TextField select size="small" label="Rows" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} sx={{ minWidth: 100 }}>
									{[10, 25, 50].map((size) => <MenuItem key={size} value={size}>{size}</MenuItem>)}
								</TextField>
								<Button variant="outlined" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
								<Button
									variant="outlined"
									disabled={page >= (productsQuery.data?.totalPages ?? 0)}
									onClick={() => setPage((current) => current + 1)}
								>
									Next
								</Button>
							</Stack>
						</Stack>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Stack spacing={2}>
						<Paper sx={{ p: 2 }}>
							<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Inventory Recommendations</Typography>
							<Stack spacing={1}>
								{(dashboardQuery.data?.recommendations ?? []).slice(0, 10).map((item) => (
									<Box key={`${item.forecastId}-${item.productId}`} sx={{ border: "1px solid #e5ddd0", borderRadius: 1, p: 1 }}>
										<Typography fontWeight={700} variant="body2">{item.productName}</Typography>
										<Chip size="small" label={item.recommendationType} color={recommendationColor(item.recommendationType)} sx={{ my: 0.5 }} />
										<Typography variant="body2">{item.reason}</Typography>
									</Box>
								))}
							</Stack>
						</Paper>
						<Paper sx={{ p: 2 }}>
							<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Admin Notifications</Typography>
							<Stack spacing={1}>
								{(notificationsQuery.data ?? []).slice(0, 8).map((item) => (
									<Box key={item.id} sx={{ border: "1px solid #e5ddd0", borderRadius: 1, p: 1 }}>
										<Typography fontWeight={700} variant="body2">{item.notificationType}</Typography>
										<Typography variant="body2">{item.message}</Typography>
										<Typography variant="caption" color="text.secondary">{new Date(item.createdAt).toLocaleString()}</Typography>
									</Box>
								))}
							</Stack>
						</Paper>
					</Stack>
				</Grid>
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Category-Level Forecast</Typography>
				<Table size="small">
					<TableHead>
						<TableRow>
							<TableCell>Category</TableCell>
							<TableCell align="right">Total Historical Sales</TableCell>
							<TableCell align="right">Predicted Demand</TableCell>
							<TableCell align="right">Expected Growth %</TableCell>
						</TableRow>
					</TableHead>
					<TableBody>
						{(dashboardQuery.data?.categories ?? []).map((item) => (
							<TableRow key={item.categoryId}>
								<TableCell>{item.categoryName}</TableCell>
								<TableCell align="right">{currencyFormatter.format(item.totalHistoricalSales)}</TableCell>
								<TableCell align="right">{numberFormatter.format(item.predictedDemand)}</TableCell>
								<TableCell align="right">{item.expectedGrowthPercentage.toFixed(2)}%</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			</Paper>
		</Stack>
	);
}
