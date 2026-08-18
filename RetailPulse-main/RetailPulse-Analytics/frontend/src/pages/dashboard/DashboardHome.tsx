import DownloadIcon from "@mui/icons-material/Download";
import {
	Alert,
	Button,
	Card,
	CardActionArea,
	CardContent,
	Dialog,
	DialogContent,
	DialogTitle,
	Grid,
	MenuItem,
	Paper,
	Skeleton,
	Stack,
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableRow,
	TextField,
	Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
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
	exportDashboardCsv,
	exportDashboardPdf,
	getDashboardAnalytics,
	getDashboardCategoryProductsDrilldown,
	getDashboardFilters,
	getDashboardKpiDrilldown,
	getDashboardProductTransactionsDrilldown,
} from "../../api/catalogApi";
import { useAuth } from "../../context/AuthContext";
import { useNotification } from "../../context/NotificationContext";
import { DashboardDateGrain, DashboardQueryFilters, PaymentMethod, SalesChannel } from "../../types/catalog";

const currencyFormatter = new Intl.NumberFormat("en-US", {
	style: "currency",
	currency: "USD",
	minimumFractionDigits: 2,
	maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("en-US");
const pieColors = ["#2f5d50", "#f3b23f", "#e36414", "#2a9d8f", "#9a3412", "#0f766e"];

type SelectValue = number | "all";
type DatePreset = "today" | "last7" | "last30" | "thisMonth" | "lastMonth" | "custom";
type ProductSort = "revenue" | "quantitySold";

type KpiConfig = {
	key: string;
	label: string;
	format: "currency" | "number";
};

const kpiConfigs: KpiConfig[] = [
	{ key: "totalRevenue", label: "Total Revenue", format: "currency" },
	{ key: "totalOrders", label: "Total Orders", format: "number" },
	{ key: "totalProductsSold", label: "Total Items Sold", format: "number" },
	{ key: "averageOrderValue", label: "Average Order Value", format: "currency" },
	{ key: "totalDiscount", label: "Total Discount", format: "currency" },
	{ key: "totalTax", label: "Total Tax", format: "currency" },
	{ key: "totalInventoryValue", label: "Total Inventory Value", format: "currency" },
	{ key: "lowStockProducts", label: "Low Stock Products", format: "number" },
	{ key: "outOfStockProducts", label: "Out of Stock Products", format: "number" },
	{ key: "totalCategories", label: "Total Categories", format: "number" },
];

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

function asIsoDate(value: string): string | undefined {
	if (!value) {
		return undefined;
	}
	return new Date(`${value}T00:00:00`).toISOString();
}

function labelize(value: string): string {
	return value
		.split("-")
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

function formatDateInput(date: Date): string {
	return date.toISOString().slice(0, 10);
}

export default function DashboardHome({ salesAnalyticsOnly = false }: { salesAnalyticsOnly?: boolean }) {
	const { user } = useAuth();
	const { notify } = useNotification();
	const [dateGrain, setDateGrain] = useState<DashboardDateGrain>("daily");
	const [datePreset, setDatePreset] = useState<DatePreset>("custom");
	const [startDate, setStartDate] = useState("");
	const [endDate, setEndDate] = useState("");
	const [productId, setProductId] = useState<SelectValue>("all");
	const [categoryId, setCategoryId] = useState<SelectValue>("all");
	const [brand, setBrand] = useState<string | "all">("all");
	const [salesChannel, setSalesChannel] = useState<SalesChannel | "all">("all");
	const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | "all">("all");
	const [productSort, setProductSort] = useState<ProductSort>("quantitySold");
	const [kpiDrilldown, setKpiDrilldown] = useState<{ key: string; label: string } | null>(null);
	const [categoryDrilldown, setCategoryDrilldown] = useState<{ id: number; name: string } | null>(null);
	const [productDrilldown, setProductDrilldown] = useState<{ id: number; name: string } | null>(null);
	const visibleKpiConfigs = salesAnalyticsOnly ? kpiConfigs.slice(0, 6) : kpiConfigs;
	const sortedTopProducts = [...(analytics?.topProducts ?? [])].sort((left, right) => right[productSort] - left[productSort]);

	const applyDatePreset = (preset: DatePreset) => {
		setDatePreset(preset);
		if (preset === "custom") return;
		const today = new Date();
		const start = new Date(today);
		const end = new Date(today);
		if (preset === "last7") start.setDate(today.getDate() - 6);
		if (preset === "last30") start.setDate(today.getDate() - 29);
		if (preset === "thisMonth") start.setDate(1);
		if (preset === "lastMonth") {
			start.setMonth(today.getMonth() - 1, 1);
			end.setDate(0);
		}
		setStartDate(formatDateInput(start));
		setEndDate(formatDateInput(end));
	};

	const queryFilters = useMemo<DashboardQueryFilters>(
		() => ({
			dateGrain,
			startDate: asIsoDate(startDate),
			endDate: endDate ? new Date(`${endDate}T23:59:59`).toISOString() : undefined,
			productId: productId === "all" ? undefined : productId,
			categoryId: categoryId === "all" ? undefined : categoryId,
			brand: brand === "all" ? undefined : brand,
			salesChannel: salesChannel === "all" ? undefined : salesChannel,
			paymentMethod: paymentMethod === "all" ? undefined : paymentMethod,
		}),
		[dateGrain, startDate, endDate, productId, categoryId, brand, salesChannel, paymentMethod],
	);

	const {
		data: filterOptions,
		isLoading: loadingFilters,
		isError: filtersError,
	} = useQuery({
		queryKey: ["dashboard-filters"],
		queryFn: getDashboardFilters,
	});

	const {
		data: analytics,
		isLoading,
		isError,
		error,
		refetch,
		isFetching,
	} = useQuery({
		queryKey: ["dashboard-analytics", queryFilters],
		queryFn: () => getDashboardAnalytics(queryFilters),
		refetchInterval: 30000,
	});

	const kpiRecordsQuery = useQuery({
		queryKey: ["dashboard-kpi-drilldown", kpiDrilldown?.key, queryFilters],
		queryFn: () =>
			getDashboardKpiDrilldown(kpiDrilldown?.key ?? "", {
				...queryFilters,
				page: 1,
				pageSize: 25,
			}),
		enabled: Boolean(kpiDrilldown),
	});

	const categoryProductsQuery = useQuery({
		queryKey: ["dashboard-category-drilldown", categoryDrilldown?.id, queryFilters],
		queryFn: () =>
			getDashboardCategoryProductsDrilldown(categoryDrilldown?.id ?? 0, {
				...queryFilters,
				page: 1,
				pageSize: 25,
			}),
		enabled: Boolean(categoryDrilldown),
	});

	const productTransactionsQuery = useQuery({
		queryKey: ["dashboard-product-drilldown", productDrilldown?.id, queryFilters],
		queryFn: () =>
			getDashboardProductTransactionsDrilldown(productDrilldown?.id ?? 0, {
				...queryFilters,
				page: 1,
				pageSize: 25,
			}),
		enabled: Boolean(productDrilldown),
	});

	const errorMessage =
		(error as any)?.response?.data?.detail ??
		(error as Error | undefined)?.message ??
		"Unable to load dashboard analytics.";

	const manualRefresh = async () => {
		await refetch();
		notify("Dashboard refreshed", "success");
	};

	const onExportCsv = async () => {
		try {
			const blob = await exportDashboardCsv(queryFilters);
			triggerBlobDownload(blob, "dashboard-report.csv");
			notify("CSV export downloaded", "success");
		} catch (exportError: any) {
			notify(exportError?.response?.data?.detail ?? "CSV export failed", "error");
		}
	};

	const onExportPdf = async () => {
		try {
			const blob = await exportDashboardPdf(queryFilters);
			triggerBlobDownload(blob, "dashboard-report.pdf");
			notify("PDF export downloaded", "success");
		} catch (exportError: any) {
			notify(exportError?.response?.data?.detail ?? "PDF export failed", "error");
		}
	};

	return (
		<Stack spacing={3}>
			<Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
				<div>
					<Typography variant="h4" fontWeight={700}>{salesAnalyticsOnly ? "Sales Analytics" : "Analytics Dashboard"}</Typography>
					<Typography color="text.secondary">
						Welcome back, {user?.name}. Company scope: {user?.company.name}
					</Typography>
					<Typography color="text.secondary" variant="body2">
						Last updated: {analytics?.lastUpdatedAt ? new Date(analytics.lastUpdatedAt).toLocaleString() : "-"}
					</Typography>
				</div>
				<Stack direction="row" spacing={1.5}>
					<Button variant="outlined" onClick={() => void manualRefresh()} disabled={isFetching}>
						Refresh
					</Button>
					<Button variant="outlined" startIcon={<DownloadIcon />} onClick={() => void onExportCsv()}>
						Export CSV
					</Button>
					<Button variant="contained" startIcon={<DownloadIcon />} onClick={() => void onExportPdf()}>
						Export PDF
					</Button>
				</Stack>
			</Stack>

			<Paper sx={{ p: 2.5 }}>
				<Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
					Filters
				</Typography>
				<Grid container spacing={2}>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select label="Date Range" fullWidth value={datePreset} onChange={(e) => applyDatePreset(e.target.value as DatePreset)}>
							<MenuItem value="today">Today</MenuItem>
							<MenuItem value="last7">Last 7 Days</MenuItem>
							<MenuItem value="last30">Last 30 Days</MenuItem>
							<MenuItem value="thisMonth">This Month</MenuItem>
							<MenuItem value="lastMonth">Last Month</MenuItem>
							<MenuItem value="custom">Custom Range</MenuItem>
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select label="Date Grain" fullWidth value={dateGrain} onChange={(e) => setDateGrain(e.target.value as DashboardDateGrain)}>
							<MenuItem value="daily">Daily</MenuItem>
							<MenuItem value="weekly">Weekly</MenuItem>
							<MenuItem value="monthly">Monthly</MenuItem>
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField type="date" label="Start Date" fullWidth value={startDate} onChange={(e) => setStartDate(e.target.value)} InputLabelProps={{ shrink: true }} />
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField type="date" label="End Date" fullWidth value={endDate} onChange={(e) => setEndDate(e.target.value)} InputLabelProps={{ shrink: true }} />
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField
							select
							label="Product"
							fullWidth
							value={productId}
							onChange={(e) => setProductId(e.target.value === "all" ? "all" : Number(e.target.value))}
							disabled={loadingFilters}
						>
							<MenuItem value="all">All</MenuItem>
							{filterOptions?.products.map((item) => (
								<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField
							select
							label="Category"
							fullWidth
							value={categoryId}
							onChange={(e) => setCategoryId(e.target.value === "all" ? "all" : Number(e.target.value))}
							disabled={loadingFilters}
						>
							<MenuItem value="all">All</MenuItem>
							{filterOptions?.categories.map((item) => (
								<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 2 }}>
						<TextField select label="Brand" fullWidth value={brand} onChange={(e) => setBrand(e.target.value)} disabled={loadingFilters}>
							<MenuItem value="all">All</MenuItem>
							{filterOptions?.brands.map((item) => (
								<MenuItem key={item} value={item}>{item}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 3 }}>
						<TextField select label="Sales Channel" fullWidth value={salesChannel} onChange={(e) => setSalesChannel(e.target.value as SalesChannel | "all")} disabled={loadingFilters}>
							<MenuItem value="all">All</MenuItem>
							{filterOptions?.salesChannels.map((item) => (
								<MenuItem key={item} value={item}>{labelize(item)}</MenuItem>
							))}
						</TextField>
					</Grid>
					<Grid size={{ xs: 12, md: 3 }}>
						<TextField select label="Payment Method" fullWidth value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod | "all")} disabled={loadingFilters}>
							<MenuItem value="all">All</MenuItem>
							{filterOptions?.paymentMethods.map((item) => (
								<MenuItem key={item} value={item}>{labelize(item)}</MenuItem>
							))}
						</TextField>
					</Grid>
				</Grid>
				{filtersError ? <Alert severity="warning" sx={{ mt: 2 }}>Unable to load filter options.</Alert> : null}
			</Paper>

			{isError ? (
				<Alert severity="error" action={<Button color="inherit" size="small" onClick={() => void refetch()}>Retry</Button>}>
					{errorMessage}
				</Alert>
			) : null}

			<Grid container spacing={2}>
				{visibleKpiConfigs.map((kpi) => {
					const value = (analytics?.kpis as Record<string, number> | undefined)?.[kpi.key] ?? 0;
					return (
						<Grid key={kpi.key} size={{ xs: 12, sm: 6, lg: 3 }}>
							<Card>
								<CardActionArea onClick={() => setKpiDrilldown({ key: kpi.key, label: kpi.label })}>
									<CardContent>
										<Typography color="text.secondary" gutterBottom>{kpi.label}</Typography>
										{isLoading ? <Skeleton variant="text" width="70%" height={40} /> : (
											<Typography variant="h5" fontWeight={700}>
												{kpi.format === "currency" ? currencyFormatter.format(value) : numberFormatter.format(value)}
											</Typography>
										)}
									</CardContent>
								</CardActionArea>
							</Card>
						</Grid>
					);
				})}
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 8 }}>
					<Paper sx={{ p: 2, height: 360 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Revenue Trend</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<LineChart data={analytics?.revenueTrend ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" />
								<YAxis />
								<Tooltip />
								<Legend />
								<Line type="monotone" dataKey="revenue" stroke="#1d4e89" strokeWidth={2} />
							</LineChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2, height: 360 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Sales Trend</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<LineChart data={analytics?.salesTrend ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" />
								<YAxis />
								<Tooltip />
								<Legend />
								<Line type="monotone" dataKey="orders" stroke="#b45309" strokeWidth={2} />
								<Line type="monotone" dataKey="productsSold" stroke="#0f766e" strokeWidth={2} />
							</LineChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 360 }}>
						<Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
							<Typography variant="h6" fontWeight={700}>Top Performing Products</Typography>
							<TextField select size="small" value={productSort} onChange={(e) => setProductSort(e.target.value as ProductSort)}>
								<MenuItem value="quantitySold">Quantity Sold</MenuItem>
								<MenuItem value="revenue">Revenue</MenuItem>
							</TextField>
						</Stack>
						{isLoading ? <Skeleton variant="rounded" height={270} /> : sortedTopProducts.length === 0 ? <Typography color="text.secondary">No sales data available for the selected period.</Typography> : null}
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={sortedTopProducts}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="productName" hide />
								<YAxis />
								<Tooltip />
								<Bar dataKey="quantitySold" fill="#1f7a8c" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 360 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Top Performing Categories</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={analytics?.topCategories ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="categoryName" hide />
								<YAxis />
								<Tooltip />
								<Bar dataKey="revenue" fill="#4d7c0f" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 340 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Sales by Payment Method</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<PieChart>
								<Tooltip />
								<Legend />
								<Pie data={analytics?.paymentMethodDistribution ?? []} dataKey="value" nameKey="label" outerRadius={105}>
									{(analytics?.paymentMethodDistribution ?? []).map((_, index) => (
										<Cell key={`payment-${index}`} fill={pieColors[index % pieColors.length]} />
									))}
								</Pie>
							</PieChart>
						</ResponsiveContainer>
							<Stack spacing={0.25}>
								{(analytics?.paymentMethodDistribution ?? []).map((item) => <Typography key={item.label} variant="caption">{labelize(item.label)}: {numberFormatter.format(item.transactions ?? 0)} transactions, {currencyFormatter.format(item.value)}</Typography>)}
							</Stack>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 340 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Sales by Sales Channel</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<PieChart>
								<Tooltip />
								<Legend />
								<Pie data={analytics?.salesChannelDistribution ?? []} dataKey="value" nameKey="label" outerRadius={105}>
									{(analytics?.salesChannelDistribution ?? []).map((_, index) => (
										<Cell key={`channel-${index}`} fill={pieColors[index % pieColors.length]} />
									))}
								</Pie>
							</PieChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 350 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Inventory Distribution by Category</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={analytics?.inventoryDistributionByCategory ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="categoryName" hide />
								<YAxis />
								<Tooltip />
								<Bar dataKey="quantity" fill="#0f4c5c" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 350 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Inventory Value by Category</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={analytics?.inventoryValueByCategory ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="categoryName" hide />
								<YAxis />
								<Tooltip />
								<Bar dataKey="inventoryValue" fill="#5f0f40" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Stock Status Summary</Typography>
						<Stack spacing={1}>
							{(analytics?.stockStatusSummary ?? []).map((item) => (
								<Stack key={item.label} direction="row" justifyContent="space-between">
									<Typography>{labelize(item.label)}</Typography>
									<Typography fontWeight={700}>{numberFormatter.format(item.value)}</Typography>
								</Stack>
							))}
						</Stack>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Top Low Stock Products</Typography>
						<Stack spacing={0.5}>
							{(analytics?.topLowStockProducts ?? []).length === 0 ? <Typography color="text.secondary">No low stock products.</Typography> : null}
							{(analytics?.topLowStockProducts ?? []).map((item) => (
								<Button key={item.productId} onClick={() => setProductDrilldown({ id: item.productId, name: item.productName })} sx={{ justifyContent: "space-between" }}>
									<span>{item.productName}</span>
									<span>{item.currentStock}</span>
								</Button>
							))}
						</Stack>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Out of Stock Products</Typography>
						<Stack spacing={0.5}>
							{(analytics?.outOfStockProducts ?? []).length === 0 ? <Typography color="text.secondary">No out of stock products.</Typography> : null}
							{(analytics?.outOfStockProducts ?? []).map((item) => (
								<Button key={item.productId} onClick={() => setProductDrilldown({ id: item.productId, name: item.productName })} sx={{ justifyContent: "space-between" }}>
									<span>{item.productName}</span>
									<span>{item.currentStock}</span>
								</Button>
							))}
						</Stack>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Category Drill-down</Typography>
						<Stack spacing={0.5}>
							{(analytics?.topCategories ?? []).slice(0, 8).map((item) => (
								<Button key={item.categoryId} onClick={() => setCategoryDrilldown({ id: item.categoryId, name: item.categoryName })} sx={{ justifyContent: "space-between" }}>
									<span>{item.categoryName}</span>
									<span>{currencyFormatter.format(item.revenue)}</span>
								</Button>
							))}
						</Stack>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Product Drill-down</Typography>
						<Stack spacing={0.5}>
							{(analytics?.topProducts ?? []).slice(0, 8).map((item) => (
								<Button key={item.productId} onClick={() => setProductDrilldown({ id: item.productId, name: item.productName })} sx={{ justifyContent: "space-between" }}>
									<span>{item.productName}</span>
									<span>{numberFormatter.format(item.quantitySold)}</span>
								</Button>
							))}
						</Stack>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 340 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Customer Growth</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<LineChart data={analytics?.customerGrowth ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" />
								<YAxis />
								<Tooltip />
								<Line type="monotone" dataKey="value" stroke="#7c3aed" strokeWidth={2} />
							</LineChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 340 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Customer Revenue Contribution</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<PieChart>
								<Tooltip />
								<Legend />
								<Pie data={analytics?.customerRevenueContribution ?? []} dataKey="contributionPercent" nameKey="customerName" outerRadius={105}>
									{(analytics?.customerRevenueContribution ?? []).map((_, index) => (
										<Cell key={`contrib-${index}`} fill={pieColors[index % pieColors.length]} />
									))}
								</Pie>
							</PieChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Top Customers</Typography>
						<Stack spacing={0.5}>
							{!isLoading && (analytics?.topCustomers ?? []).length === 0 ? <Typography color="text.secondary">No customer revenue data available.</Typography> : null}
							{(analytics?.topCustomers ?? []).slice(0, 8).map((item) => (
								<Stack key={item.customerId} direction="row" justifyContent="space-between">
									<Typography>{item.customerName} ({numberFormatter.format(item.orders)} orders)</Typography>
									<Typography>{currencyFormatter.format(item.revenue)} / {currencyFormatter.format(item.averageOrderValue)}</Typography>
								</Stack>
							))}
						</Stack>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Recent Customers</Typography>
						<Stack spacing={0.5}>
							{(analytics?.recentCustomers ?? []).slice(0, 8).map((item) => (
								<Stack key={item.customerId} direction="row" justifyContent="space-between">
									<Typography>{item.customerName}</Typography>
									<Typography color="text.secondary">{new Date(item.customerSince).toLocaleDateString()}</Typography>
								</Stack>
							))}
						</Stack>
					</Paper>
				</Grid>
			</Grid>

			<Dialog open={Boolean(kpiDrilldown)} onClose={() => setKpiDrilldown(null)} maxWidth="md" fullWidth>
				<DialogTitle>{kpiDrilldown?.label} Details</DialogTitle>
				<DialogContent>
					<Table size="small">
						<TableHead>
							<TableRow>
								<TableCell>Label</TableCell>
								<TableCell>Secondary</TableCell>
								<TableCell align="right">Value</TableCell>
							</TableRow>
						</TableHead>
						<TableBody>
							{(kpiRecordsQuery.data?.items ?? []).map((item) => (
								<TableRow key={item.id}>
									<TableCell>{item.label}</TableCell>
									<TableCell>{item.secondary ?? "-"}</TableCell>
									<TableCell align="right">{currencyFormatter.format(item.value)}</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</DialogContent>
			</Dialog>

			<Dialog open={Boolean(categoryDrilldown)} onClose={() => setCategoryDrilldown(null)} maxWidth="md" fullWidth>
				<DialogTitle>{categoryDrilldown?.name} Products</DialogTitle>
				<DialogContent>
					<Table size="small">
						<TableHead>
							<TableRow>
								<TableCell>Product</TableCell>
								<TableCell>SKU</TableCell>
								<TableCell align="right">Stock</TableCell>
								<TableCell align="right">Sold Qty</TableCell>
								<TableCell align="right">Revenue</TableCell>
							</TableRow>
						</TableHead>
						<TableBody>
							{(categoryProductsQuery.data?.items ?? []).map((item) => (
								<TableRow key={item.productId}>
									<TableCell>{item.productName}</TableCell>
									<TableCell>{item.sku}</TableCell>
									<TableCell align="right">{numberFormatter.format(item.currentStock)}</TableCell>
									<TableCell align="right">{numberFormatter.format(item.quantitySold ?? 0)}</TableCell>
									<TableCell align="right">{currencyFormatter.format(item.revenue ?? 0)}</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</DialogContent>
			</Dialog>

			<Dialog open={Boolean(productDrilldown)} onClose={() => setProductDrilldown(null)} maxWidth="md" fullWidth>
				<DialogTitle>{productDrilldown?.name} Transactions</DialogTitle>
				<DialogContent>
					<Table size="small">
						<TableHead>
							<TableRow>
								<TableCell>Invoice</TableCell>
								<TableCell>Date</TableCell>
								<TableCell>Customer</TableCell>
								<TableCell align="right">Qty</TableCell>
								<TableCell align="right">Total</TableCell>
							</TableRow>
						</TableHead>
						<TableBody>
							{(productTransactionsQuery.data?.items ?? []).map((item) => (
								<TableRow key={item.saleId}>
									<TableCell>{item.invoiceNumber}</TableCell>
									<TableCell>{new Date(item.saleDate).toLocaleString()}</TableCell>
									<TableCell>{item.customerName}</TableCell>
									<TableCell align="right">{numberFormatter.format(item.quantity)}</TableCell>
									<TableCell align="right">{currencyFormatter.format(item.total)}</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</DialogContent>
			</Dialog>

			{isLoading ? <Typography color="text.secondary">Loading analytics...</Typography> : null}
		</Stack>
	);
}
