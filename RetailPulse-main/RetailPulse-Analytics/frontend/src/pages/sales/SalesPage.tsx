import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import MenuIcon from "@mui/icons-material/Menu";
import {
	Alert,
	Box,
	Button,
	CircularProgress,
	Dialog,
	DialogActions,
	DialogContent,
	DialogTitle,
	Grid,
	IconButton,
	MenuItem,
	Paper,
	Stack,
	TextField,
	Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import {
	createSale,
	deleteSale,
	exportSaleInvoiceCsv,
	exportSaleInvoicePdf,
	getSale,
	listCustomerOptions,
	listCategories,
	listProducts,
	listSales,
	updateSale,
} from "../../api/catalogApi";
import { useNotification } from "../../context/NotificationContext";
import {
	CategoryItem,
	CustomerOptionItem,
	PaymentMethod,
	PaymentStatus,
	ProductItem,
	SaleFormValues,
	SaleListItem,
	SaleRecord,
	SalesChannel,
} from "../../types/catalog";

const salesChannels: SalesChannel[] = ["in-store", "online", "wholesale", "marketplace", "other"];
const paymentMethods: PaymentMethod[] = ["cash", "card", "bank-transfer", "upi", "wallet", "other"];
const paymentStatuses: PaymentStatus[] = ["pending", "paid", "failed", "refunded"];

const defaultFormValues: SaleFormValues = {
	saleDate: new Date().toISOString(),
	customerId: undefined,
	customerName: "",
	salesChannel: "in-store",
	paymentMethod: "cash",
	paymentStatus: "paid",
	notes: "",
	items: [{ productId: 0, quantity: 1, unitPrice: 0, discount: 0, tax: 0 }],
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

function toDateInputValue(value: string | undefined): string {
	if (!value) {
		return "";
	}
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) {
		return "";
	}
	const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
	return localDate.toISOString().slice(0, 16);
}

function fromDateInputValue(value: string): string {
	return new Date(value).toISOString();
}

export default function SalesPage() {
	const queryClient = useQueryClient();
	const { notify } = useNotification();
	const [search, setSearch] = useState("");
	const [startDate, setStartDate] = useState("");
	const [endDate, setEndDate] = useState("");
	const [categoryFilter, setCategoryFilter] = useState<number | "all">("all");
	const [channelFilter, setChannelFilter] = useState<SalesChannel | "all">("all");
	const [paymentFilter, setPaymentFilter] = useState<PaymentMethod | "all">("all");
	const [paymentStatusFilter, setPaymentStatusFilter] = useState<PaymentStatus | "all">("all");
	const [sortBy, setSortBy] = useState<"date" | "invoiceNumber" | "totalAmount" | "customerName">("date");
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState(10);
	const [open, setOpen] = useState(false);
	const [editingSale, setEditingSale] = useState<SaleRecord | null>(null);
	const [viewingSaleId, setViewingSaleId] = useState<number | null>(null);

	const { data: salesPage, isLoading: salesLoading } = useQuery({
		queryKey: ["sales", search, startDate, endDate, categoryFilter, channelFilter, paymentFilter, paymentStatusFilter, sortBy, sortDirection, page, pageSize],
		queryFn: () =>
			listSales({
				search: search || undefined,
				startDate: startDate || undefined,
				endDate: endDate || undefined,
				categoryId: categoryFilter === "all" ? undefined : categoryFilter,
				salesChannel: channelFilter === "all" ? undefined : channelFilter,
				paymentMethod: paymentFilter === "all" ? undefined : paymentFilter,
				paymentStatus: paymentStatusFilter === "all" ? undefined : paymentStatusFilter,
				sortBy,
				sortDirection,
				page,
				pageSize,
			}),
	});
	const sales = salesPage?.items ?? [];
	const totalSales = salesPage?.total ?? 0;
	const totalSalePages = salesPage?.totalPages ?? 0;
	const { data: products = [] } = useQuery({
		queryKey: ["sales-products"],
		queryFn: async () => {
			const response = await listProducts({ status: "active", sortBy: "name", sortDirection: "asc", page: 1, pageSize: 500 });
			return response.items;
		},
	});
	const { data: categories = [] } = useQuery({
		queryKey: ["sales-categories"],
		queryFn: () => listCategories({}),
	});
	const { data: customerOptions = [] } = useQuery({
		queryKey: ["sales-customer-options"],
		queryFn: listCustomerOptions,
	});
	const { data: viewingSale } = useQuery({
		queryKey: ["sale-details", viewingSaleId],
		queryFn: () => getSale(viewingSaleId ?? 0),
		enabled: viewingSaleId !== null,
	});

	useEffect(() => {
		setPage(1);
	}, [search, startDate, endDate, categoryFilter, channelFilter, paymentFilter, paymentStatusFilter, sortBy, sortDirection]);

	const productMap = useMemo(() => {
		return products.reduce<Record<number, ProductItem>>((acc, product) => {
			acc[product.id] = product;
			return acc;
		}, {});
	}, [products]);

	const {
		register,
		handleSubmit,
		control,
		watch,
		reset,
		getValues,
		setValue,
		formState: { errors, isSubmitting },
	} = useForm<SaleFormValues>({ defaultValues: defaultFormValues });
	const { fields, append, remove } = useFieldArray({ control, name: "items" });
	const watchedItems = watch("items");

	const saveMutation = useMutation({
		mutationFn: async (payload: SaleFormValues) => {
			if (editingSale) {
				return updateSale(editingSale.id, payload);
			}
			return createSale(payload);
		},
		onSuccess: async (result) => {
			await queryClient.invalidateQueries({ queryKey: ["sales"] });
			await queryClient.invalidateQueries({ queryKey: ["sales-products"] });
			await queryClient.invalidateQueries({ queryKey: ["products"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			notify(editingSale ? "Sale updated successfully" : "Sale created successfully", "success");
			result.notifications.forEach((item) => notify(item.message, item.type === "out-of-stock" ? "warning" : "info"));
			setOpen(false);
			setEditingSale(null);
			reset(defaultFormValues);
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to save sale", "error"),
	});

	const deleteMutation = useMutation({
		mutationFn: deleteSale,
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["sales"] });
			await queryClient.invalidateQueries({ queryKey: ["sales-products"] });
			await queryClient.invalidateQueries({ queryKey: ["products"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			notify("Sale deleted", "success");
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to delete sale", "error"),
	});

	const totalRevenue = useMemo(
		() => sales.reduce((acc: number, item: SaleListItem) => acc + item.totalAmount, 0),
		[sales],
	);

	const draftTotals = useMemo(() => {
		const subtotal = (watchedItems ?? []).reduce((acc, item) => acc + Number(item.quantity || 0) * Number(item.unitPrice || 0), 0);
		const discount = (watchedItems ?? []).reduce((acc, item) => acc + Number(item.discount || 0), 0);
		const tax = (watchedItems ?? []).reduce((acc, item) => acc + Number(item.tax || 0), 0);
		return {
			subtotal,
			discount,
			tax,
			grandTotal: subtotal - discount + tax,
		};
	}, [watchedItems]);

	const openCreateDialog = () => {
		setEditingSale(null);
		reset(defaultFormValues);
		setOpen(true);
	};

	const openEditDialog = async (saleId: number) => {
		try {
			const sale = await getSale(saleId);
			setEditingSale(sale);
			reset({
				saleDate: sale.saleDate,
				customerId: sale.customerId ?? undefined,
				customerName: sale.customerName,
				salesChannel: sale.salesChannel,
				paymentMethod: sale.paymentMethod,
				paymentStatus: sale.paymentStatus,
				notes: sale.notes ?? "",
				items: sale.items.map((item) => ({
					productId: item.productId,
					quantity: item.quantity,
					unitPrice: item.unitPrice,
					discount: item.discount,
					tax: item.tax,
				})),
			});
			setOpen(true);
		} catch (error: any) {
			notify(error?.response?.data?.detail ?? "Unable to load sale record", "error");
		}
	};

	useEffect(() => {
		(watchedItems ?? []).forEach((item, index) => {
			const selectedProduct = productMap[Number(item.productId ?? 0)];
			if (!selectedProduct) {
				return;
			}
			if (!item.unitPrice || Number(item.unitPrice) <= 0) {
				setValue(`items.${index}.unitPrice`, Number(selectedProduct.unitPrice), { shouldDirty: true });
			}
		});
	}, [watchedItems, productMap, setValue]);

	const closeDialog = () => {
		setOpen(false);
		setEditingSale(null);
		reset(defaultFormValues);
	};

	const onSubmit = handleSubmit(async (values) => {
		const payload: SaleFormValues = {
			...values,
			saleDate: values.saleDate,
			notes: values.notes?.trim() || "",
			items: values.items,
		};
		saveMutation.mutate(payload);
	});

	const handleInvoiceExport = async (saleId: number, format: "csv" | "pdf") => {
		try {
			if (format === "csv") {
				triggerBlobDownload(await exportSaleInvoiceCsv(saleId), `invoice-${saleId}.csv`);
			} else {
				triggerBlobDownload(await exportSaleInvoicePdf(saleId), `invoice-${saleId}.pdf`);
			}
			notify(`Invoice ${format.toUpperCase()} downloaded`, "success");
		} catch (error: any) {
			notify(error?.response?.data?.detail ?? "Invoice export failed", "error");
		}
	};

	const selectedCustomerId = watch("customerId");
	useEffect(() => {
		if (!selectedCustomerId) {
			return;
		}
		const selected = (customerOptions as CustomerOptionItem[]).find((item) => item.id === Number(selectedCustomerId));
		if (selected) {
			setValue("customerName", selected.fullName, { shouldDirty: true });
		}
	}, [selectedCustomerId, customerOptions, setValue]);

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Sales</Typography>
				<Typography color="text.secondary">Record and manage sales transactions with live inventory controls.</Typography>
			</Box>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, md: 3 }}><Paper sx={{ p: 2 }}><Typography color="text.secondary">Total Orders</Typography><Typography variant="h4" fontWeight={700}>{totalSales}</Typography></Paper></Grid>
				<Grid size={{ xs: 12, md: 3 }}><Paper sx={{ p: 2 }}><Typography color="text.secondary">Revenue (Current Page)</Typography><Typography variant="h4" fontWeight={700}>{totalRevenue.toFixed(2)}</Typography></Paper></Grid>
				<Grid size={{ xs: 12, md: 3 }}><Paper sx={{ p: 2 }}><Typography color="text.secondary">Avg Order (Current Page)</Typography><Typography variant="h4" fontWeight={700}>{sales.length ? (totalRevenue / sales.length).toFixed(2) : "0.00"}</Typography></Paper></Grid>
				<Grid size={{ xs: 12, md: 3 }}><Paper sx={{ p: 2 }}><Typography color="text.secondary">Products In Catalog</Typography><Typography variant="h4" fontWeight={700}>{products.length}</Typography></Paper></Grid>
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Stack spacing={2}>
					<Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }} justifyContent="space-between">
						<TextField fullWidth label="Search invoice, customer, product" value={search} onChange={(event) => setSearch(event.target.value)} />
						<TextField type="date" label="Start Date" value={startDate} onChange={(event) => setStartDate(event.target.value)} InputLabelProps={{ shrink: true }} />
						<TextField type="date" label="End Date" value={endDate} onChange={(event) => setEndDate(event.target.value)} InputLabelProps={{ shrink: true }} />
						<TextField select label="Category" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value === "all" ? "all" : Number(event.target.value))} sx={{ minWidth: 170 }}>
							<MenuItem value="all">All Categories</MenuItem>
							{(categories as CategoryItem[]).map((category) => <MenuItem key={category.id} value={category.id}>{category.name}</MenuItem>)}
						</TextField>
						<TextField select label="Channel" value={channelFilter} onChange={(event) => setChannelFilter(event.target.value as SalesChannel | "all")} sx={{ minWidth: 150 }}>
							<MenuItem value="all">All</MenuItem>
							{salesChannels.map((channel) => <MenuItem key={channel} value={channel}>{channel}</MenuItem>)}
						</TextField>
						<TextField select label="Payment" value={paymentFilter} onChange={(event) => setPaymentFilter(event.target.value as PaymentMethod | "all")} sx={{ minWidth: 150 }}>
							<MenuItem value="all">All</MenuItem>
							{paymentMethods.map((method) => <MenuItem key={method} value={method}>{method}</MenuItem>)}
						</TextField>
						<TextField select label="Payment Status" value={paymentStatusFilter} onChange={(event) => setPaymentStatusFilter(event.target.value as PaymentStatus | "all")} sx={{ minWidth: 170 }}>
							<MenuItem value="all">All</MenuItem>
							{paymentStatuses.map((status) => <MenuItem key={status} value={status}>{status}</MenuItem>)}
						</TextField>
						<TextField select label="Sort" value={sortBy} onChange={(event) => setSortBy(event.target.value as "date" | "invoiceNumber" | "totalAmount" | "customerName")} sx={{ minWidth: 150 }}>
							<MenuItem value="date">Date</MenuItem>
							<MenuItem value="invoiceNumber">Invoice</MenuItem>
							<MenuItem value="totalAmount">Total</MenuItem>
							<MenuItem value="customerName">Customer</MenuItem>
						</TextField>
						<TextField select label="Direction" value={sortDirection} onChange={(event) => setSortDirection(event.target.value as "asc" | "desc")} sx={{ minWidth: 130 }}>
							<MenuItem value="desc">Desc</MenuItem>
							<MenuItem value="asc">Asc</MenuItem>
						</TextField>
						<Button startIcon={<AddIcon />} variant="contained" onClick={openCreateDialog}>New Sale</Button>
					</Stack>

					{salesLoading ? (
						<Stack direction="row" spacing={1} alignItems="center">
							<CircularProgress size={18} />
							<Typography color="text.secondary">Loading sales...</Typography>
						</Stack>
					) : null}

					{!salesLoading && sales.length === 0 ? <Alert severity="info">No sales transactions match your criteria.</Alert> : null}

					<Box sx={{ overflowX: "auto" }}>
						<table style={{ width: "100%", borderCollapse: "collapse" }}>
							<thead>
								<tr>
									{["Invoice", "Date", "Customer", "Channel", "Payment", "Payment Status", "Items", "Total", "Created By", "Actions"].map((heading) => (
										<th key={heading} style={{ textAlign: "left", padding: "12px 8px", borderBottom: "1px solid #e5ddd0" }}>{heading}</th>
									))}
								</tr>
							</thead>
							<tbody>
								{sales.map((sale) => (
									<tr key={sale.id}>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de", fontWeight: 700 }}>{sale.invoiceNumber}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{new Date(sale.saleDate).toLocaleString()}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.customerName}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.salesChannel}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.paymentMethod}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.paymentStatus}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.itemCount}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.totalAmount.toFixed(2)}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{sale.createdByName}</td>
										<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>
											<Stack direction="row" spacing={0.5}>
												<IconButton size="small" onClick={() => setViewingSaleId(sale.id)}><MenuIcon fontSize="small" /></IconButton>
												<IconButton size="small" onClick={() => void handleInvoiceExport(sale.id, "csv")}><DownloadIcon fontSize="small" /></IconButton>
												<IconButton size="small" onClick={() => void handleInvoiceExport(sale.id, "pdf")} aria-label="export invoice pdf">PDF</IconButton>
												<IconButton size="small" onClick={() => void openEditDialog(sale.id)}><EditIcon fontSize="small" /></IconButton>
												<IconButton size="small" onClick={() => deleteMutation.mutate(sale.id)}><DeleteIcon fontSize="small" /></IconButton>
											</Stack>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</Box>

					<Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }}>
						<Typography color="text.secondary">
							Showing {totalSales === 0 ? 0 : (page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalSales)} of {totalSales}
						</Typography>
						<Stack direction="row" spacing={1} alignItems="center">
							<TextField
								select
								size="small"
								label="Rows"
								value={pageSize}
								onChange={(event) => {
									setPageSize(Number(event.target.value));
									setPage(1);
								}}
								sx={{ minWidth: 110 }}
							>
								{[10, 25, 50].map((size) => (
									<MenuItem key={size} value={size}>{size}</MenuItem>
								))}
							</TextField>
							<Button variant="outlined" disabled={page <= 1} onClick={() => setPage((current) => Math.max(current - 1, 1))}>Previous</Button>
							<Button variant="outlined" disabled={totalSalePages === 0 || page >= totalSalePages} onClick={() => setPage((current) => current + 1)}>Next</Button>
						</Stack>
					</Stack>
				</Stack>
			</Paper>

			<Dialog open={open} onClose={closeDialog} fullWidth maxWidth="lg">
				<DialogTitle>{editingSale ? `Edit Sale (${editingSale.invoiceNumber})` : "Create Sale"}</DialogTitle>
				<form onSubmit={onSubmit}>
					<DialogContent>
						<Grid container spacing={2} sx={{ pt: 1 }}>
							<Grid size={{ xs: 12, md: 4 }}>
								<TextField
									fullWidth
									type="datetime-local"
									label="Sale Date & Time"
									defaultValue={toDateInputValue(defaultFormValues.saleDate)}
									value={toDateInputValue(watch("saleDate"))}
									onChange={(event) => {
										setValue("saleDate", fromDateInputValue(event.target.value), { shouldDirty: true });
									}}
									InputLabelProps={{ shrink: true }}
								/>
							</Grid>
							<Grid size={{ xs: 12, md: 4 }}>
								<TextField
									select
									fullWidth
									label="Customer"
									defaultValue=""
									{...register("customerId", { valueAsNumber: true })}
								>
									<MenuItem value="">Walk-in / Not Linked</MenuItem>
									{(customerOptions as CustomerOptionItem[]).map((customer) => (
										<MenuItem key={customer.id} value={customer.id}>{customer.fullName} ({customer.customerId})</MenuItem>
									))}
								</TextField>
							</Grid>
							<Grid size={{ xs: 12, md: 4 }}>
								<TextField fullWidth label="Customer Name" {...register("customerName", { required: "Customer name is required" })} error={Boolean(errors.customerName)} helperText={errors.customerName?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 2 }}>
								<TextField select fullWidth label="Sales Channel" {...register("salesChannel", { required: true })}>
									{salesChannels.map((channel) => <MenuItem key={channel} value={channel}>{channel}</MenuItem>)}
								</TextField>
							</Grid>
							<Grid size={{ xs: 12, md: 2 }}>
								<TextField select fullWidth label="Payment Method" {...register("paymentMethod", { required: true })}>
									{paymentMethods.map((method) => <MenuItem key={method} value={method}>{method}</MenuItem>)}
								</TextField>
							</Grid>
							<Grid size={{ xs: 12, md: 2 }}>
								<TextField select fullWidth label="Payment Status" {...register("paymentStatus", { required: true })}>
									{paymentStatuses.map((status) => <MenuItem key={status} value={status}>{status}</MenuItem>)}
								</TextField>
							</Grid>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField fullWidth label="Notes" placeholder="Optional notes" {...register("notes")} />
							</Grid>

							<Grid size={{ xs: 12 }}>
								<Paper variant="outlined" sx={{ p: 2 }}>
									<Stack spacing={2}>
										<Stack direction="row" justifyContent="space-between" alignItems="center">
											<Typography variant="h6">Sale Items</Typography>
											<Button variant="outlined" onClick={() => append({ productId: 0, quantity: 1, unitPrice: 0, discount: 0, tax: 0 })}>Add Item</Button>
										</Stack>

										{fields.map((field, index) => {
											const product = productMap[Number(watchedItems?.[index]?.productId ?? 0)];
											const quantity = Number(watchedItems?.[index]?.quantity ?? 0);
											const unitPrice = Number(watchedItems?.[index]?.unitPrice ?? 0);
											const discount = Number(watchedItems?.[index]?.discount ?? 0);
											const tax = Number(watchedItems?.[index]?.tax ?? 0);
											const lineSubtotal = quantity * unitPrice;
											const lineTotal = lineSubtotal - discount + tax;

											return (
												<Paper key={field.id} variant="outlined" sx={{ p: 2 }}>
													<Grid container spacing={2}>
														<Grid size={{ xs: 12, md: 3 }}>
															<TextField
																select
																fullWidth
																label="Product"
																{...register(`items.${index}.productId`, { valueAsNumber: true, required: "Product is required", min: 1 })}
																error={Boolean(errors.items?.[index]?.productId)}
																helperText={errors.items?.[index]?.productId?.message}
															>
																<MenuItem value={0}>Select Product</MenuItem>
																{products.map((item) => (
																	<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>
																))}
															</TextField>
														</Grid>
														<Grid size={{ xs: 12, md: 2 }}>
															<TextField
																fullWidth
																type="number"
																label="Quantity"
																inputProps={{ min: 1 }}
																{...register(`items.${index}.quantity`, {
																	valueAsNumber: true,
																	required: "Quantity is required",
																	min: { value: 1, message: "Quantity must be greater than zero" },
																	validate: (value) => {
																		const selectedProduct = productMap[getValues(`items.${index}.productId`)];
																		if (!selectedProduct) {
																			return "Product selection is mandatory";
																		}
																		if (value > selectedProduct.stockQuantity) {
																			return "Quantity sold cannot exceed available stock";
																		}
																		return true;
																	},
																})}
																error={Boolean(errors.items?.[index]?.quantity)}
																helperText={errors.items?.[index]?.quantity?.message}
															/>
														</Grid>
														<Grid size={{ xs: 12, md: 2 }}>
															<TextField
																fullWidth
																type="number"
																label="Unit Price"
																inputProps={{ min: 0, step: "0.01" }}
																{...register(`items.${index}.unitPrice`, {
																	valueAsNumber: true,
																	required: "Unit price is required",
																	min: { value: 0, message: "Unit price cannot be negative" },
																})}
																error={Boolean(errors.items?.[index]?.unitPrice)}
																helperText={errors.items?.[index]?.unitPrice?.message}
															/>
														</Grid>
														<Grid size={{ xs: 12, md: 2 }}>
															<TextField
																fullWidth
																type="number"
																label="Discount"
																inputProps={{ min: 0, step: "0.01" }}
																{...register(`items.${index}.discount`, {
																	valueAsNumber: true,
																	min: { value: 0, message: "Discount cannot be negative" },
																	validate: (value) => value <= Number(getValues(`items.${index}.quantity`) * getValues(`items.${index}.unitPrice`)) || "Discount cannot exceed total product value",
																})}
																error={Boolean(errors.items?.[index]?.discount)}
																helperText={errors.items?.[index]?.discount?.message}
															/>
														</Grid>
														<Grid size={{ xs: 12, md: 2 }}>
															<TextField
																fullWidth
																type="number"
																label="Tax"
																inputProps={{ min: 0, step: "0.01" }}
																{...register(`items.${index}.tax`, {
																	valueAsNumber: true,
																	min: { value: 0, message: "Tax cannot be negative" },
																})}
																error={Boolean(errors.items?.[index]?.tax)}
																helperText={errors.items?.[index]?.tax?.message}
															/>
														</Grid>
														<Grid size={{ xs: 12, md: 1 }}>
															<IconButton disabled={fields.length === 1} onClick={() => remove(index)}><DeleteIcon /></IconButton>
														</Grid>
														<Grid size={{ xs: 12 }}>
															<Typography variant="body2" color="text.secondary">
																Product: {product?.name ?? "-"} | SKU: {product?.sku ?? "-"} | Category: {product?.category.name ?? "-"} | Available Stock: {product?.stockQuantity ?? 0} | Line Total: {Number.isFinite(lineTotal) ? lineTotal.toFixed(2) : "0.00"}
															</Typography>
														</Grid>
													</Grid>
												</Paper>
											);
										})}

										<Paper variant="outlined" sx={{ p: 2 }}>
											<Typography variant="h6" sx={{ mb: 1 }}>Billing Summary</Typography>
											<Typography>Subtotal: {draftTotals.subtotal.toFixed(2)}</Typography>
											<Typography>Discount: {draftTotals.discount.toFixed(2)}</Typography>
											<Typography>Tax: {draftTotals.tax.toFixed(2)}</Typography>
											<Typography fontWeight={700}>Grand Total: {draftTotals.grandTotal.toFixed(2)}</Typography>
										</Paper>
									</Stack>
								</Paper>
							</Grid>
						</Grid>
					</DialogContent>
					<DialogActions>
						<Button onClick={closeDialog} color="inherit">Cancel</Button>
						<Button type="submit" variant="contained" disabled={isSubmitting || saveMutation.isPending}>{saveMutation.isPending ? "Saving..." : "Save Sale"}</Button>
					</DialogActions>
				</form>
			</Dialog>

			<Dialog open={viewingSaleId !== null} onClose={() => setViewingSaleId(null)} fullWidth maxWidth="md">
				<DialogTitle>Sale Details</DialogTitle>
				<DialogContent>
					{viewingSale ? (
						<Stack spacing={2} sx={{ pt: 1 }}>
							<Paper variant="outlined" sx={{ p: 2 }}>
								<Typography variant="h6">Invoice Details</Typography>
								<Typography><strong>Invoice Number:</strong> {viewingSale.invoiceNumber}</Typography>
								<Typography><strong>Sale Date:</strong> {new Date(viewingSale.saleDate).toLocaleString()}</Typography>
								<Typography><strong>Sales Channel:</strong> {viewingSale.salesChannel}</Typography>
								<Typography><strong>Payment Method:</strong> {viewingSale.paymentMethod}</Typography>
								<Typography><strong>Payment Status:</strong> {viewingSale.paymentStatus}</Typography>
								<Typography><strong>Notes:</strong> {viewingSale.notes || "-"}</Typography>
							</Paper>
							<Paper variant="outlined" sx={{ p: 2 }}>
								<Typography variant="h6">Customer Information</Typography>
								<Typography><strong>Customer Name:</strong> {viewingSale.customerName}</Typography>
								<Typography><strong>Recorded By:</strong> {viewingSale.createdByName}</Typography>
							</Paper>
							<Paper variant="outlined" sx={{ p: 2 }}>
								<Typography variant="h6">Pricing Breakdown</Typography>
								{viewingSale.items.map((item) => (
									<Box key={item.id} sx={{ py: 1, borderBottom: "1px solid #f0e9de" }}>
										<Typography><strong>Product:</strong> {item.productName}</Typography>
										<Typography><strong>SKU:</strong> {item.sku}</Typography>
										<Typography><strong>Category:</strong> {item.categoryName}</Typography>
										<Typography><strong>Quantity:</strong> {item.quantity}</Typography>
										<Typography><strong>Unit Price:</strong> {item.unitPrice.toFixed(2)}</Typography>
										<Typography><strong>Discount:</strong> {item.discount.toFixed(2)}</Typography>
										<Typography><strong>Tax:</strong> {item.tax.toFixed(2)}</Typography>
										<Typography><strong>Line Total:</strong> {item.total.toFixed(2)}</Typography>
										<Typography><strong>Remaining Stock:</strong> {item.remainingStock}</Typography>
									</Box>
								))}
								<Typography sx={{ mt: 1 }}><strong>Subtotal:</strong> {viewingSale.subtotal.toFixed(2)}</Typography>
								<Typography><strong>Discount:</strong> {viewingSale.discountTotal.toFixed(2)}</Typography>
								<Typography><strong>Tax:</strong> {viewingSale.taxTotal.toFixed(2)}</Typography>
								<Typography sx={{ mt: 1 }} variant="h6">Grand Total: {viewingSale.totalAmount.toFixed(2)}</Typography>
							</Paper>
							{viewingSale.notifications.length > 0 ? (
								<Paper variant="outlined" sx={{ p: 2 }}>
									<Typography variant="h6">Notifications</Typography>
									{viewingSale.notifications.map((item, index) => (
										<Alert key={`${item.type}-${index}`} severity={item.type === "out-of-stock" ? "warning" : "info"} sx={{ mt: 1 }}>
											{item.message}
										</Alert>
									))}
								</Paper>
							) : null}
						</Stack>
					) : (
						<Typography color="text.secondary">Loading sale details...</Typography>
					)}
				</DialogContent>
				<DialogActions>
					<Button onClick={() => setViewingSaleId(null)}>Close</Button>
				</DialogActions>
			</Dialog>
		</Stack>
	);
}
