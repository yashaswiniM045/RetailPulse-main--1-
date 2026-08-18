import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import {
	Alert,
	Box,
	Button,
	Card,
	CardContent,
	Chip,
	Dialog,
	DialogActions,
	DialogContent,
	DialogTitle,
	Grid,
	IconButton,
	CircularProgress,
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Legend,
	Pie,
	PieChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	createCustomer,
	deleteCustomer,
	exportCustomerAnalyticsCsv,
	exportCustomerAnalyticsPdf,
	exportCustomerListCsv,
	exportCustomerListPdf,
	exportTopCustomersCsv,
	exportTopCustomersPdf,
	getCustomerAnalytics,
	getCustomerProfile,
	listCustomerNotifications,
	listCustomers,
	setCustomerStatus,
	updateCustomer,
} from "../../api/catalogApi";
import { useNotification } from "../../context/NotificationContext";
import { CustomerFormValues, CustomerItem, CustomerProfile } from "../../types/catalog";

const currencyFormatter = new Intl.NumberFormat("en-US", {
	style: "currency",
	currency: "USD",
	minimumFractionDigits: 2,
	maximumFractionDigits: 2,
});
const numberFormatter = new Intl.NumberFormat("en-US");
const pieColors = ["#2f5d50", "#e36414", "#3a86ff", "#6a4c93", "#4d7c0f"];

const emptyFormValues: CustomerFormValues = {
	firstName: "",
	lastName: "",
	fullName: "",
	email: "",
	phoneNumber: "",
	dateOfBirth: "",
	gender: undefined,
	addressLine1: "",
	addressLine2: "",
	city: "",
	state: "",
	country: "",
	postalCode: "",
	customerType: "retail",
	preferredSalesChannel: undefined,
	status: "active",
};

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

export default function CustomersPage() {
	const queryClient = useQueryClient();
	const { notify } = useNotification();
	const [search, setSearch] = useState("");
	const [segmentFilter, setSegmentFilter] = useState<string | "all">("all");
	const [statusFilter, setStatusFilter] = useState<string | "all">("all");
	const [city, setCity] = useState("");
	const [stateFilter, setStateFilter] = useState("");
	const [country, setCountry] = useState("");
	const [registeredFrom, setRegisteredFrom] = useState("");
	const [registeredTo, setRegisteredTo] = useState("");
	const [sortBy, setSortBy] = useState<"name" | "totalSpend" | "totalOrders" | "lastPurchase" | "customerSince">("customerSince");
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState(10);
	const [openForm, setOpenForm] = useState(false);
	const [editingCustomer, setEditingCustomer] = useState<CustomerItem | null>(null);
	const [pendingDelete, setPendingDelete] = useState<CustomerItem | null>(null);
	const [profileCustomerId, setProfileCustomerId] = useState<number | null>(null);
	const [analyticsFrom, setAnalyticsFrom] = useState("");
	const [analyticsTo, setAnalyticsTo] = useState("");

	const { data: customerPage, isLoading } = useQuery({
		queryKey: [
			"customers",
			search,
			segmentFilter,
			statusFilter,
			city,
			stateFilter,
			country,
			registeredFrom,
			registeredTo,
			sortBy,
			sortDirection,
			page,
			pageSize,
		],
		queryFn: () =>
			listCustomers({
				search: search || undefined,
				customerType: undefined,
				segment: segmentFilter === "all" ? undefined : segmentFilter,
				status: statusFilter === "all" ? undefined : statusFilter,
				city: city || undefined,
				state: stateFilter || undefined,
				country: country || undefined,
				registeredFrom: registeredFrom || undefined,
				registeredTo: registeredTo || undefined,
				sortBy,
				sortDirection,
				page,
				pageSize,
			}),
	});

	const { data: analytics, isLoading: analyticsLoading } = useQuery({
		queryKey: ["customer-analytics", analyticsFrom, analyticsTo],
		queryFn: () => getCustomerAnalytics({ startDate: analyticsFrom || undefined, endDate: analyticsTo || undefined }),
	});

	const { data: customerNotifications = [] } = useQuery({
		queryKey: ["customer-notifications"],
		queryFn: () => listCustomerNotifications(10),
	});

	const { data: customerProfile } = useQuery<CustomerProfile>({
		queryKey: ["customer-profile", profileCustomerId],
		queryFn: () => getCustomerProfile(profileCustomerId ?? 0),
		enabled: profileCustomerId !== null,
	});

	useEffect(() => {
		setPage(1);
	}, [search, segmentFilter, statusFilter, city, stateFilter, country, registeredFrom, registeredTo, sortBy, sortDirection]);

	const customers = customerPage?.items ?? [];
	const totalCustomers = customerPage?.total ?? 0;
	const totalPages = customerPage?.totalPages ?? 0;

	const cityOptions = useMemo(() => {
		const set = new Set(customers.map((item) => item.city).filter(Boolean) as string[]);
		return Array.from(set.values()).sort();
	}, [customers]);

	const {
		register,
		handleSubmit,
		reset,
		formState: { errors, isSubmitting },
	} = useForm<CustomerFormValues>({ defaultValues: emptyFormValues });

	useEffect(() => {
		if (editingCustomer) {
			const [firstName = "", ...last] = editingCustomer.fullName.split(" ");
			reset({
				firstName,
				lastName: last.join(" "),
				fullName: editingCustomer.fullName,
				email: editingCustomer.email,
				phoneNumber: editingCustomer.phoneNumber,
				dateOfBirth: editingCustomer.dateOfBirth ?? "",
				gender: editingCustomer.gender ?? undefined,
				addressLine1: editingCustomer.addressLine1 ?? "",
				addressLine2: editingCustomer.addressLine2 ?? "",
				city: editingCustomer.city ?? "",
				state: editingCustomer.state ?? "",
				country: editingCustomer.country ?? "",
				postalCode: editingCustomer.postalCode ?? "",
				customerType: editingCustomer.customerType,
				preferredSalesChannel: editingCustomer.preferredSalesChannel ?? undefined,
				status: editingCustomer.status,
			});
		} else {
			reset(emptyFormValues);
		}
	}, [editingCustomer, reset]);

	const saveMutation = useMutation({
		mutationFn: async (payload: CustomerFormValues) => {
			if (editingCustomer) {
				return updateCustomer(editingCustomer.id, payload);
			}
			return createCustomer(payload);
		},
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["customers"] });
			await queryClient.invalidateQueries({ queryKey: ["customer-analytics"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			await queryClient.invalidateQueries({ queryKey: ["customer-notifications"] });
			notify(editingCustomer ? "Customer updated" : "Customer created", "success");
			setOpenForm(false);
			setEditingCustomer(null);
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to save customer", "error"),
	});

	const deleteMutation = useMutation({
		mutationFn: deleteCustomer,
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["customers"] });
			await queryClient.invalidateQueries({ queryKey: ["customer-analytics"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			notify("Customer deleted", "success");
			setPendingDelete(null);
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to delete customer", "error"),
	});

	const statusMutation = useMutation({
		mutationFn: ({ customerId, status }: { customerId: number; status: "active" | "inactive" }) =>
			setCustomerStatus(customerId, status),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["customers"] });
			await queryClient.invalidateQueries({ queryKey: ["customer-analytics"] });
			notify("Customer status updated", "success");
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to update status", "error"),
	});

	const onSubmit = handleSubmit(async (values) => {
		const mergedName = `${values.firstName} ${values.lastName}`.trim();
		values.fullName = mergedName;
		saveMutation.mutate(values);
	});

	const segmentColor = (segment: string): "default" | "primary" | "secondary" | "success" | "warning" => {
		if (segment === "new") return "primary";
		if (segment === "regular") return "secondary";
		if (segment === "loyal") return "success";
		if (segment === "vip") return "warning";
		return "default";
	};

	const handleExport = async (type: "list-csv" | "list-pdf" | "analytics-csv" | "analytics-pdf" | "top-csv" | "top-pdf") => {
		try {
			if (type === "list-csv") {
				triggerBlobDownload(await exportCustomerListCsv(), "customers-list.csv");
			}
			if (type === "list-pdf") {
				triggerBlobDownload(await exportCustomerListPdf(), "customers-list.pdf");
			}
			if (type === "analytics-csv") {
				triggerBlobDownload(await exportCustomerAnalyticsCsv({ startDate: analyticsFrom || undefined, endDate: analyticsTo || undefined }), "customer-analytics.csv");
			}
			if (type === "analytics-pdf") {
				triggerBlobDownload(await exportCustomerAnalyticsPdf({ startDate: analyticsFrom || undefined, endDate: analyticsTo || undefined }), "customer-analytics.pdf");
			}
			if (type === "top-csv") {
				triggerBlobDownload(await exportTopCustomersCsv({ startDate: analyticsFrom || undefined, endDate: analyticsTo || undefined }), "top-customers.csv");
			}
			if (type === "top-pdf") {
				triggerBlobDownload(await exportTopCustomersPdf({ startDate: analyticsFrom || undefined, endDate: analyticsTo || undefined }), "top-customers.pdf");
			}
			notify("Export downloaded", "success");
		} catch (error: any) {
			notify(error?.response?.data?.detail ?? "Export failed", "error");
		}
	};

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Customers</Typography>
				<Typography color="text.secondary">Manage customer profiles, purchase intelligence, and behaviour analytics.</Typography>
			</Box>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card><CardContent><Typography color="text.secondary">Total Customers</Typography><Typography variant="h4" fontWeight={700}>{analytics?.kpis.totalCustomers ?? 0}</Typography></CardContent></Card>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card><CardContent><Typography color="text.secondary">Active Customers</Typography><Typography variant="h4" fontWeight={700}>{analytics?.kpis.activeCustomers ?? 0}</Typography></CardContent></Card>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card><CardContent><Typography color="text.secondary">New Customers</Typography><Typography variant="h4" fontWeight={700}>{analytics?.kpis.newCustomers ?? 0}</Typography></CardContent></Card>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Card><CardContent><Typography color="text.secondary">Returning Customers</Typography><Typography variant="h4" fontWeight={700}>{analytics?.kpis.returningCustomers ?? 0}</Typography></CardContent></Card>
				</Grid>
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }} justifyContent="space-between">
					<Stack direction="row" spacing={1.5}>
						<TextField type="date" label="Analytics From" value={analyticsFrom} onChange={(e) => setAnalyticsFrom(e.target.value)} InputLabelProps={{ shrink: true }} />
						<TextField type="date" label="Analytics To" value={analyticsTo} onChange={(e) => setAnalyticsTo(e.target.value)} InputLabelProps={{ shrink: true }} />
					</Stack>
					<Stack direction="row" spacing={1}>
						<Button variant="outlined" startIcon={<DownloadIcon />} onClick={() => void handleExport("list-csv")}>Customers CSV</Button>
						<Button variant="outlined" startIcon={<DownloadIcon />} onClick={() => void handleExport("analytics-csv")}>Analytics CSV</Button>
						<Button variant="contained" startIcon={<DownloadIcon />} onClick={() => void handleExport("top-pdf")}>Top Customers PDF</Button>
					</Stack>
				</Stack>
			</Paper>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 8 }}>
					<Paper sx={{ p: 2, height: 330 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Customer Growth Trend</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={analytics?.customerGrowthTrend ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" />
								<YAxis />
								<Tooltip />
								<Bar dataKey="value" fill="#1f7a8c" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2, height: 330 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>New vs Returning</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<PieChart>
								<Legend />
								<Tooltip />
								<Pie data={analytics?.newVsReturning ?? []} dataKey="value" nameKey="label" outerRadius={100}>
									{(analytics?.newVsReturning ?? []).map((_, index) => <Cell key={`nvr-${index}`} fill={pieColors[index % pieColors.length]} />)}
								</Pie>
							</PieChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 330 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Revenue by Customer Type</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={analytics?.revenueByCustomerType ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="label" />
								<YAxis />
								<Tooltip />
								<Bar dataKey="value" fill="#4d7c0f" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 6 }}>
					<Paper sx={{ p: 2, height: 330 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Customer Spending Distribution</Typography>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={analytics?.customerSpendingDistribution ?? []}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="label" />
								<YAxis />
								<Tooltip />
								<Bar dataKey="value" fill="#b45309" />
							</BarChart>
						</ResponsiveContainer>
					</Paper>
				</Grid>
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }} justifyContent="space-between">
					<TextField fullWidth label="Search by name or email" value={search} onChange={(e) => setSearch(e.target.value)} />
					<TextField select label="Customer Segment" value={segmentFilter} onChange={(e) => setSegmentFilter(e.target.value)} sx={{ minWidth: 170 }}>
						<MenuItem value="all">All</MenuItem>
						<MenuItem value="new">New</MenuItem>
						<MenuItem value="regular">Regular</MenuItem>
						<MenuItem value="loyal">Loyal</MenuItem>
						<MenuItem value="vip">VIP</MenuItem>
					</TextField>
					<TextField select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} sx={{ minWidth: 150 }}>
						<MenuItem value="all">All</MenuItem>
						<MenuItem value="active">Active</MenuItem>
						<MenuItem value="inactive">Inactive</MenuItem>
					</TextField>
					<TextField select label="City" value={city} onChange={(e) => setCity(e.target.value)} sx={{ minWidth: 160 }}>
						<MenuItem value="">All</MenuItem>
						{cityOptions.map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}
					</TextField>
					<TextField label="State" value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} sx={{ minWidth: 130 }} />
					<TextField label="Country" value={country} onChange={(e) => setCountry(e.target.value)} sx={{ minWidth: 130 }} />
					<TextField type="date" label="Registered From" value={registeredFrom} onChange={(e) => setRegisteredFrom(e.target.value)} InputLabelProps={{ shrink: true }} />
					<TextField type="date" label="Registered To" value={registeredTo} onChange={(e) => setRegisteredTo(e.target.value)} InputLabelProps={{ shrink: true }} />
					<TextField select label="Sort By" value={sortBy} onChange={(e) => setSortBy(e.target.value as any)} sx={{ minWidth: 150 }}>
						<MenuItem value="name">Name</MenuItem>
						<MenuItem value="totalSpend">Total Spend</MenuItem>
						<MenuItem value="totalOrders">Total Purchases</MenuItem>
						<MenuItem value="lastPurchase">Last Purchase</MenuItem>
						<MenuItem value="customerSince">Customer Since</MenuItem>
					</TextField>
					<TextField select label="Direction" value={sortDirection} onChange={(e) => setSortDirection(e.target.value as any)} sx={{ minWidth: 130 }}>
						<MenuItem value="desc">Desc</MenuItem>
						<MenuItem value="asc">Asc</MenuItem>
					</TextField>
					<Button startIcon={<AddIcon />} variant="contained" onClick={() => { setEditingCustomer(null); setOpenForm(true); }}>New Customer</Button>
				</Stack>

				{isLoading ? (
					<Stack spacing={1.5} sx={{ mt: 2 }}>
						<Skeleton variant="rounded" height={46} />
						<Skeleton variant="rounded" height={46} />
						<Skeleton variant="rounded" height={46} />
					</Stack>
				) : null}
				{!isLoading && customers.length === 0 ? <Alert severity="info" sx={{ mt: 2 }}>No customers available.</Alert> : null}

				<Box sx={{ overflowX: "auto", mt: 2 }}>
					<table style={{ width: "100%", borderCollapse: "collapse" }}>
						<thead>
							<tr>
								{["Customer Name", "Email", "Phone Number", "Customer Segment", "Total Purchases", "Total Spend", "Status", "Actions"].map((heading) => (
									<th key={heading} style={{ textAlign: "left", padding: "12px 8px", borderBottom: "1px solid #e5ddd0" }}>{heading}</th>
								))}
							</tr>
						</thead>
						<tbody>
							{customers.map((customer) => (
								<tr key={customer.id}>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{customer.fullName}</td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{customer.email}</td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{customer.phoneNumber}</td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}><Chip size="small" label={customer.segment.toUpperCase()} color={segmentColor(customer.segment)} /></td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{numberFormatter.format(customer.totalPurchases)}</td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{currencyFormatter.format(customer.totalSpend)}</td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}><Chip size="small" label={customer.status} color={customer.status === "active" ? "success" : "default"} /></td>
									<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>
										<Stack direction="row" spacing={0.5}>
											<IconButton size="small" onClick={() => setProfileCustomerId(customer.id)} aria-label="view customer">View</IconButton>
											<IconButton size="small" onClick={() => { setEditingCustomer(customer); setOpenForm(true); }}><EditIcon fontSize="small" /></IconButton>
											<IconButton size="small" onClick={() => statusMutation.mutate({ customerId: customer.id, status: customer.status === "active" ? "inactive" : "active" })}>{customer.status === "active" ? "Pause" : "Activate"}</IconButton>
											<IconButton size="small" onClick={() => setPendingDelete(customer)}><DeleteIcon fontSize="small" /></IconButton>
										</Stack>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</Box>

				<Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }} sx={{ mt: 2 }}>
					<Typography color="text.secondary">Showing {totalCustomers === 0 ? 0 : (page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalCustomers)} of {totalCustomers}</Typography>
					<Stack direction="row" spacing={1}>
						<TextField select size="small" label="Rows" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} sx={{ minWidth: 110 }}>
							{[10, 25, 50].map((size) => <MenuItem key={size} value={size}>{size}</MenuItem>)}
						</TextField>
						<Button variant="outlined" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
						<Button variant="outlined" disabled={totalPages === 0 || page >= totalPages} onClick={() => setPage((current) => current + 1)}>Next</Button>
					</Stack>
				</Stack>
			</Paper>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, lg: 8 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Top 10 Customers by Revenue</Typography>
						<Table size="small">
							<TableHead>
								<TableRow>
									<TableCell>Customer</TableCell>
									<TableCell>Customer Code</TableCell>
									<TableCell align="right">Revenue</TableCell>
								</TableRow>
							</TableHead>
							<TableBody>
								{(analytics?.topCustomersByRevenue ?? []).map((item) => (
									<TableRow key={item.customerId}>
										<TableCell>{item.customerName}</TableCell>
										<TableCell>{item.customerCode}</TableCell>
										<TableCell align="right">{currencyFormatter.format(item.revenue)}</TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, lg: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Admin Notifications</Typography>
						<Stack spacing={1}>
							{customerNotifications.length === 0 ? <Typography color="text.secondary">No notifications.</Typography> : null}
							{customerNotifications.map((item) => (
								<Box key={item.id} sx={{ p: 1, border: "1px solid #e5ddd0", borderRadius: 1 }}>
									<Typography fontWeight={600} variant="body2">{item.notificationType}</Typography>
									<Typography variant="body2">{item.message}</Typography>
									<Typography variant="caption" color="text.secondary">{new Date(item.createdAt).toLocaleString()}</Typography>
								</Box>
							))}
						</Stack>
					</Paper>
				</Grid>
			</Grid>

			<Dialog open={openForm} onClose={() => { setOpenForm(false); setEditingCustomer(null); }} fullWidth maxWidth="md">
				<DialogTitle>{editingCustomer ? "Edit Customer" : "Create Customer"}</DialogTitle>
				<form onSubmit={onSubmit}>
					<DialogContent>
						<Grid container spacing={2} sx={{ pt: 1 }}>
							<Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="First Name" {...register("firstName", { required: "First name is required" })} error={Boolean(errors.firstName)} helperText={errors.firstName?.message} /></Grid>
							<Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Last Name" {...register("lastName", { required: "Last name is required" })} error={Boolean(errors.lastName)} helperText={errors.lastName?.message} /></Grid>
							<Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Email" {...register("email", { required: "Email is required" })} error={Boolean(errors.email)} helperText={errors.email?.message} /></Grid>
							<Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Phone" {...register("phoneNumber", { required: "Phone number is required", pattern: { value: /^\+?[0-9\-\s()]{7,20}$/, message: "Invalid phone number format" } })} error={Boolean(errors.phoneNumber)} helperText={errors.phoneNumber?.message} /></Grid>
							<Grid size={{ xs: 12, md: 4 }}><TextField fullWidth type="date" label="Date of Birth" {...register("dateOfBirth")} InputLabelProps={{ shrink: true }} /></Grid>
							<Grid size={{ xs: 12, md: 4 }}><TextField select fullWidth label="Gender" {...register("gender")}><MenuItem value="">Unspecified</MenuItem><MenuItem value="male">Male</MenuItem><MenuItem value="female">Female</MenuItem><MenuItem value="other">Other</MenuItem><MenuItem value="prefer-not-to-say">Prefer not to say</MenuItem></TextField></Grid>
							<Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Address" {...register("addressLine1", { required: "Address is required" })} error={Boolean(errors.addressLine1)} helperText={errors.addressLine1?.message} /></Grid>
							<Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Address Line 2" {...register("addressLine2")} error={Boolean(errors.addressLine2)} helperText={errors.addressLine2?.message} /></Grid>
							<Grid size={{ xs: 12, md: 3 }}><TextField fullWidth label="City" {...register("city", { required: "City is required" })} error={Boolean(errors.city)} helperText={errors.city?.message} /></Grid>
							<Grid size={{ xs: 12, md: 3 }}><TextField fullWidth label="State" {...register("state", { required: "State is required" })} error={Boolean(errors.state)} helperText={errors.state?.message} /></Grid>
							<Grid size={{ xs: 12, md: 3 }}><TextField fullWidth label="Country" {...register("country", { required: "Country is required" })} error={Boolean(errors.country)} helperText={errors.country?.message} /></Grid>
							<Grid size={{ xs: 12, md: 3 }}><TextField fullWidth label="Postal Code" {...register("postalCode", { required: "Postal code is required" })} error={Boolean(errors.postalCode)} helperText={errors.postalCode?.message} /></Grid>
							<Grid size={{ xs: 12, md: 4 }}><TextField select fullWidth label="Customer Type" {...register("customerType", { required: true })}><MenuItem value="retail">Retail</MenuItem><MenuItem value="wholesale">Wholesale</MenuItem><MenuItem value="corporate">Corporate</MenuItem></TextField></Grid>
							<Grid size={{ xs: 12, md: 4 }}><TextField select fullWidth label="Preferred Sales Channel" {...register("preferredSalesChannel")}><MenuItem value="">Unspecified</MenuItem><MenuItem value="in-store">In-store</MenuItem><MenuItem value="online">Online</MenuItem><MenuItem value="wholesale">Wholesale</MenuItem><MenuItem value="marketplace">Marketplace</MenuItem><MenuItem value="other">Other</MenuItem></TextField></Grid>
							<Grid size={{ xs: 12, md: 4 }}><TextField select fullWidth label="Status" {...register("status", { required: true })}><MenuItem value="active">Active</MenuItem><MenuItem value="inactive">Inactive</MenuItem></TextField></Grid>
						</Grid>
					</DialogContent>
					<DialogActions>
						<Button color="inherit" onClick={() => { setOpenForm(false); setEditingCustomer(null); }}>Cancel</Button>
						<Button type="submit" variant="contained" disabled={isSubmitting || saveMutation.isPending}>Save</Button>
					</DialogActions>
				</form>
			</Dialog>

			<Dialog open={Boolean(pendingDelete)} onClose={() => setPendingDelete(null)} fullWidth maxWidth="xs">
				<DialogTitle>Delete Customer</DialogTitle>
				<DialogContent>
					<Typography>Delete {pendingDelete?.fullName}? This action deactivates and removes the customer from active lists.</Typography>
				</DialogContent>
				<DialogActions>
					<Button color="inherit" onClick={() => setPendingDelete(null)}>Cancel</Button>
					<Button color="error" variant="contained" onClick={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)} disabled={deleteMutation.isPending}>Delete</Button>
				</DialogActions>
			</Dialog>

			<Dialog open={profileCustomerId !== null} onClose={() => setProfileCustomerId(null)} fullWidth maxWidth="lg">
				<DialogTitle>Customer Profile</DialogTitle>
				<DialogContent>
					{customerProfile ? (
						<Stack spacing={2} sx={{ pt: 1 }}>
							<Grid container spacing={2}>
								<Grid size={{ xs: 12, md: 6 }}>
									<Paper variant="outlined" sx={{ p: 2 }}>
										<Typography variant="h6">Profile</Typography>
										<Typography><strong>{customerProfile.customer.fullName}</strong> ({customerProfile.customer.customerId})</Typography>
										<Typography>{customerProfile.customer.email}</Typography>
										<Typography>{customerProfile.customer.phoneNumber}</Typography>
										<Typography>{customerProfile.customer.city ?? "-"}, {customerProfile.customer.state ?? "-"}, {customerProfile.customer.country ?? "-"}</Typography>
									</Paper>
								</Grid>
								<Grid size={{ xs: 12, md: 6 }}>
									<Paper variant="outlined" sx={{ p: 2 }}>
										<Typography variant="h6">Purchase Summary</Typography>
										<Typography>Total Orders: {numberFormatter.format(customerProfile.purchaseSummary.totalOrders)}</Typography>
										<Typography>Total Revenue: {currencyFormatter.format(customerProfile.purchaseSummary.totalRevenue)}</Typography>
										<Typography>Average Order: {currencyFormatter.format(customerProfile.purchaseSummary.averageOrderValue)}</Typography>
										<Typography>Last Purchase: {customerProfile.purchaseSummary.lastPurchaseDate ? new Date(customerProfile.purchaseSummary.lastPurchaseDate).toLocaleString() : "-"}</Typography>
										<Typography>Favorite Product: {customerProfile.purchaseSummary.favoriteProduct.name ?? "-"}</Typography>
										<Typography>Favorite Category: {customerProfile.purchaseSummary.favoriteCategory.name ?? "-"}</Typography>
									</Paper>
								</Grid>
							</Grid>

							<Paper variant="outlined" sx={{ p: 2 }}>
								<Typography variant="h6" sx={{ mb: 1 }}>Recent Transactions</Typography>
								<Table size="small">
									<TableHead><TableRow><TableCell>Invoice</TableCell><TableCell>Date</TableCell><TableCell>Channel</TableCell><TableCell>Payment</TableCell><TableCell align="right">Amount</TableCell></TableRow></TableHead>
									<TableBody>
										{customerProfile.purchaseSummary.recentTransactions.map((item) => (
											<TableRow key={item.saleId}><TableCell>{item.invoiceNumber}</TableCell><TableCell>{new Date(item.saleDate).toLocaleString()}</TableCell><TableCell>{item.salesChannel}</TableCell><TableCell>{item.paymentMethod}</TableCell><TableCell align="right">{currencyFormatter.format(item.totalAmount)}</TableCell></TableRow>
										))}
									</TableBody>
								</Table>
							</Paper>

							<Paper variant="outlined" sx={{ p: 2 }}>
								<Typography variant="h6" sx={{ mb: 1 }}>Customer Timeline</Typography>
								<Stack spacing={1}>
									{customerProfile.timeline.map((item) => (
										<Box key={item.id} sx={{ p: 1, border: "1px solid #e5ddd0", borderRadius: 1 }}>
											<Typography fontWeight={600}>{item.title}</Typography>
											<Typography variant="body2">{item.description ?? ""}</Typography>
											<Typography variant="caption" color="text.secondary">{new Date(item.timestamp).toLocaleString()}</Typography>
										</Box>
									))}
								</Stack>
							</Paper>
						</Stack>
					) : (
						<Stack direction="row" spacing={1} alignItems="center"><CircularProgress size={18} /><Typography color="text.secondary">Loading profile...</Typography></Stack>
					)}
				</DialogContent>
				<DialogActions><Button onClick={() => setProfileCustomerId(null)}>Close</Button></DialogActions>
			</Dialog>

			{analyticsLoading ? <Typography color="text.secondary">Loading customer analytics...</Typography> : null}
		</Stack>
	);
}
