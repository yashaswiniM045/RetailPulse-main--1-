import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Grid, IconButton, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
	createProduct,
	deleteProduct,
	listCategories,
	listProducts,
	setProductStatus,
	updateProduct,
} from "../../api/catalogApi";
import { useNotification } from "../../context/NotificationContext";
import { CategoryItem, CatalogStatus, ProductFormValues, ProductItem } from "../../types/catalog";

const emptyValues: ProductFormValues = {
	productName: "",
	sku: "",
	categoryId: 0,
	brand: "",
	description: "",
	unitPrice: 0,
	costPrice: 0,
	stockQuantity: 0,
	unitOfMeasure: "",
	status: "active",
};

export default function ProductsPage() {
	const queryClient = useQueryClient();
	const { notify } = useNotification();
	const [search, setSearch] = useState("");
	const [categoryFilter, setCategoryFilter] = useState<number | "all">("all");
	const [statusFilter, setStatusFilter] = useState<CatalogStatus | "all">("all");
	const [sortBy, setSortBy] = useState<"name" | "price" | "recentlyAdded">("recentlyAdded");
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState(10);
	const [open, setOpen] = useState(false);
	const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);
	const [viewingProduct, setViewingProduct] = useState<ProductItem | null>(null);
	const [pendingDeleteProduct, setPendingDeleteProduct] = useState<ProductItem | null>(null);

	const { data: categories = [] } = useQuery({ queryKey: ["category-options"], queryFn: () => listCategories({}) });
	const { data: productsPage, isLoading } = useQuery({
		queryKey: ["products", search, categoryFilter, statusFilter, sortBy, sortDirection, page, pageSize],
		queryFn: () =>
			listProducts({
				search: search || undefined,
				categoryId: categoryFilter === "all" ? undefined : categoryFilter,
				status: statusFilter === "all" ? undefined : statusFilter,
				sortBy,
				sortDirection,
				page,
				pageSize,
			}),
	});
	const products = productsPage?.items ?? [];
	const totalProducts = productsPage?.total ?? 0;
	const totalPages = productsPage?.totalPages ?? 0;

	const { register, handleSubmit, reset, watch, formState: { errors, isSubmitting } } = useForm<ProductFormValues>({ defaultValues: emptyValues });
	const watchedUnitPrice = watch("unitPrice");

	useEffect(() => {
		if (editingProduct) {
			reset({
				productName: editingProduct.name,
				sku: editingProduct.sku,
				categoryId: editingProduct.category.id,
				brand: editingProduct.brand ?? "",
				description: editingProduct.description ?? "",
				unitPrice: editingProduct.unitPrice,
				costPrice: editingProduct.costPrice,
				stockQuantity: editingProduct.stockQuantity,
				unitOfMeasure: editingProduct.unitOfMeasure,
				status: editingProduct.status,
			});
		} else {
			reset(emptyValues);
		}
	}, [editingProduct, reset]);

	useEffect(() => {
		setPage(1);
	}, [search, categoryFilter, statusFilter, sortBy, sortDirection]);

	const activeProducts = useMemo(() => products.filter((product) => product.status === "active").length, [products]);

	const saveMutation = useMutation({
		mutationFn: async (payload: ProductFormValues) => {
			if (editingProduct) {
				return updateProduct(editingProduct.id, payload);
			}
			return createProduct(payload);
		},
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["products"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-filters"] });
			await queryClient.invalidateQueries({ queryKey: ["categories"] });
			notify(editingProduct ? "Product updated successfully" : "Product created successfully", "success");
			setOpen(false);
			setEditingProduct(null);
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to save product", "error"),
	});

	const statusMutation = useMutation({
		mutationFn: ({ productId, status }: { productId: number; status: CatalogStatus }) => setProductStatus(productId, status),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["products"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			await queryClient.invalidateQueries({ queryKey: ["categories"] });
			notify("Product status updated", "success");
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to update status", "error"),
	});

	const deleteMutation = useMutation({
		mutationFn: deleteProduct,
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["products"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-filters"] });
			await queryClient.invalidateQueries({ queryKey: ["categories"] });
			notify("Product deleted", "success");
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to delete product", "error"),
	});

	const onSubmit = handleSubmit(async (values) => {
		saveMutation.mutate(values);
	});

	const openCreateDialog = () => {
		setEditingProduct(null);
		setOpen(true);
	};

	const openEditDialog = (product: ProductItem) => {
		setEditingProduct(product);
		setOpen(true);
	};

	const closeDialog = () => {
		setOpen(false);
		setEditingProduct(null);
	};

	const openDeleteDialog = (product: ProductItem) => {
		setPendingDeleteProduct(product);
	};

	const closeDeleteDialog = () => {
		setPendingDeleteProduct(null);
	};

	const confirmDeleteProduct = () => {
		if (!pendingDeleteProduct) {
			return;
		}
		deleteMutation.mutate(pendingDeleteProduct.id, {
			onSuccess: () => {
				closeDeleteDialog();
			},
		});
	};

	const categoryOptions = categories as CategoryItem[];

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Products</Typography>
				<Typography color="text.secondary">Manage SKU-driven product master data with search, filters, sorting, and activation controls.</Typography>
			</Box>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, md: 3 }}>
					<Paper sx={{ p: 2 }}><Typography color="text.secondary">Total Products</Typography><Typography variant="h4" fontWeight={700}>{totalProducts}</Typography></Paper>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Paper sx={{ p: 2 }}><Typography color="text.secondary">Active (Current Page)</Typography><Typography variant="h4" fontWeight={700}>{activeProducts}</Typography></Paper>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Paper sx={{ p: 2 }}><Typography color="text.secondary">Inactive (Current Page)</Typography><Typography variant="h4" fontWeight={700}>{Math.max(products.length - activeProducts, 0)}</Typography></Paper>
				</Grid>
				<Grid size={{ xs: 12, md: 3 }}>
					<Paper sx={{ p: 2 }}><Typography color="text.secondary">Categories</Typography><Typography variant="h4" fontWeight={700}>{categoryOptions.length}</Typography></Paper>
				</Grid>
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Stack spacing={2}>
					<Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }} justifyContent="space-between">
						<TextField fullWidth label="Search by name, SKU, or brand" value={search} onChange={(event) => setSearch(event.target.value)} />
						<TextField select label="Category" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value === "all" ? "all" : Number(event.target.value))} sx={{ minWidth: 180 }}>
							<MenuItem value="all">All Categories</MenuItem>
							{categoryOptions.map((category) => <MenuItem key={category.id} value={category.id}>{category.name}</MenuItem>)}
						</TextField>
						<TextField select label="Status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as CatalogStatus | "all")} sx={{ minWidth: 160 }}>
							<MenuItem value="all">All Status</MenuItem>
							<MenuItem value="active">Active</MenuItem>
							<MenuItem value="inactive">Inactive</MenuItem>
						</TextField>
						<TextField select label="Sort By" value={sortBy} onChange={(event) => setSortBy(event.target.value as "name" | "price" | "recentlyAdded")} sx={{ minWidth: 170 }}>
							<MenuItem value="recentlyAdded">Recently Added</MenuItem>
							<MenuItem value="name">Name</MenuItem>
							<MenuItem value="price">Price</MenuItem>
						</TextField>
						<TextField select label="Direction" value={sortDirection} onChange={(event) => setSortDirection(event.target.value as "asc" | "desc")} sx={{ minWidth: 140 }}>
							<MenuItem value="desc">Desc</MenuItem>
							<MenuItem value="asc">Asc</MenuItem>
						</TextField>
						<Button startIcon={<AddIcon />} variant="contained" onClick={openCreateDialog}>New Product</Button>
					</Stack>

					{categoryOptions.length === 0 ? <Alert severity="warning">Create at least one category before adding products.</Alert> : null}
					{!isLoading && products.length === 0 ? <Alert severity="info">No products match your search criteria.</Alert> : null}

					<Box sx={{ overflowX: "auto" }}>
						<table style={{ width: "100%", borderCollapse: "collapse" }}>
							<thead>
								<tr>
									{["Name", "SKU", "Category", "Brand", "Price", "Stock", "Status", "Actions"].map((heading) => (
										<th key={heading} style={{ textAlign: "left", padding: "12px 8px", borderBottom: "1px solid #e5ddd0" }}>{heading}</th>
									))}
								</tr>
							</thead>
							<tbody>
								{products.map((product) => (
									<tr key={product.id}>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de", fontWeight: 600 }}>{product.name}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{product.sku}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{product.category.name}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{product.brand || "-"}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{product.unitPrice.toFixed(2)}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{product.stockQuantity}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>
											<Chip size="small" label={product.status} color={product.status === "active" ? "success" : "default"} />
										</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>
											<Stack direction="row" spacing={0.5}>
												<Button size="small" variant="text" onClick={() => setViewingProduct(product)}>View</Button>
												<IconButton size="small" onClick={() => openEditDialog(product)}><EditIcon fontSize="small" /></IconButton>
												<IconButton size="small" onClick={() => statusMutation.mutate({ productId: product.id, status: product.status === "active" ? "inactive" : "active" })}>
													<Chip size="small" label={product.status === "active" ? "Disable" : "Enable"} />
												</IconButton>
												<IconButton size="small" onClick={() => openDeleteDialog(product)}><DeleteIcon fontSize="small" /></IconButton>
											</Stack>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</Box>

					<Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }}>
						<Typography color="text.secondary">
							Showing {totalProducts === 0 ? 0 : (page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalProducts)} of {totalProducts}
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
							<Button variant="outlined" disabled={totalPages === 0 || page >= totalPages} onClick={() => setPage((current) => current + 1)}>Next</Button>
						</Stack>
					</Stack>
				</Stack>
			</Paper>

			<Dialog open={open} onClose={closeDialog} fullWidth maxWidth="md">
				<DialogTitle>{editingProduct ? "Edit Product" : "Create Product"}</DialogTitle>
				<form onSubmit={onSubmit}>
					<DialogContent>
						<Grid container spacing={2} sx={{ pt: 1 }}>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField fullWidth label="Product Name" {...register("productName", { required: "Product name is required" })} error={Boolean(errors.productName)} helperText={errors.productName?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField fullWidth label="SKU" {...register("sku", { required: "SKU is required" })} error={Boolean(errors.sku)} helperText={errors.sku?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField select fullWidth label="Category" {...register("categoryId", { valueAsNumber: true, required: "Category is required", min: 1 })} error={Boolean(errors.categoryId)} helperText={errors.categoryId?.message}>
									{categoryOptions.map((category) => <MenuItem key={category.id} value={category.id}>{category.name}</MenuItem>)}
								</TextField>
							</Grid>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField fullWidth label="Brand" {...register("brand")} />
							</Grid>
							<Grid size={{ xs: 12 }}>
								<TextField fullWidth label="Product Description" multiline minRows={3} {...register("description")} />
							</Grid>
							<Grid size={{ xs: 12, md: 4 }}>
								<TextField fullWidth label="Unit Price" type="number" inputProps={{ step: "0.01", min: "0" }} {...register("unitPrice", { valueAsNumber: true, required: "Unit price is required", min: { value: 0.01, message: "Unit price must be greater than zero" } })} error={Boolean(errors.unitPrice)} helperText={errors.unitPrice?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 4 }}>
								<TextField fullWidth label="Cost Price" type="number" inputProps={{ step: "0.01", min: "0" }} {...register("costPrice", { valueAsNumber: true, required: "Cost price is required", validate: (value) => value <= watchedUnitPrice || "Cost price cannot exceed unit price" })} error={Boolean(errors.costPrice)} helperText={errors.costPrice?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 4 }}>
								<TextField fullWidth label="Stock Quantity" type="number" inputProps={{ step: "1", min: "0" }} {...register("stockQuantity", { valueAsNumber: true, required: "Stock quantity is required", min: { value: 0, message: "Stock quantity cannot be negative" } })} error={Boolean(errors.stockQuantity)} helperText={errors.stockQuantity?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField fullWidth label="Unit of Measure" {...register("unitOfMeasure", { required: "Unit of measure is required" })} error={Boolean(errors.unitOfMeasure)} helperText={errors.unitOfMeasure?.message} />
							</Grid>
							<Grid size={{ xs: 12, md: 6 }}>
								<TextField select fullWidth label="Status" {...register("status", { required: true })}>
									<MenuItem value="active">Active</MenuItem>
									<MenuItem value="inactive">Inactive</MenuItem>
								</TextField>
							</Grid>
						</Grid>
					</DialogContent>
					<DialogActions>
						<Button onClick={closeDialog} color="inherit">Cancel</Button>
						<Button type="submit" variant="contained" disabled={isSubmitting || saveMutation.isPending}>Save</Button>
					</DialogActions>
				</form>
			</Dialog>

			<Dialog open={Boolean(viewingProduct)} onClose={() => setViewingProduct(null)} fullWidth maxWidth="sm">
				<DialogTitle>Product Details</DialogTitle>
				<DialogContent>
					{viewingProduct ? (
						<Stack spacing={1.5} sx={{ pt: 1 }}>
							<Typography><strong>Name:</strong> {viewingProduct.name}</Typography>
							<Typography><strong>SKU:</strong> {viewingProduct.sku}</Typography>
							<Typography><strong>Category:</strong> {viewingProduct.category.name}</Typography>
							<Typography><strong>Brand:</strong> {viewingProduct.brand || "-"}</Typography>
							<Typography><strong>Description:</strong> {viewingProduct.description || "-"}</Typography>
							<Typography><strong>Unit Price:</strong> {viewingProduct.unitPrice.toFixed(2)}</Typography>
							<Typography><strong>Cost Price:</strong> {viewingProduct.costPrice.toFixed(2)}</Typography>
							<Typography><strong>Stock Quantity:</strong> {viewingProduct.stockQuantity}</Typography>
							<Typography><strong>Unit of Measure:</strong> {viewingProduct.unitOfMeasure}</Typography>
							<Typography><strong>Status:</strong> {viewingProduct.status}</Typography>
						</Stack>
					) : null}
				</DialogContent>
				<DialogActions>
					<Button onClick={() => setViewingProduct(null)}>Close</Button>
				</DialogActions>
			</Dialog>

			<Dialog open={Boolean(pendingDeleteProduct)} onClose={closeDeleteDialog} fullWidth maxWidth="xs">
				<DialogTitle>Delete Product</DialogTitle>
				<DialogContent>
					<Typography>
						Are you sure you want to delete {pendingDeleteProduct?.name}? This action cannot be undone.
					</Typography>
				</DialogContent>
				<DialogActions>
					<Button onClick={closeDeleteDialog} color="inherit">Cancel</Button>
					<Button color="error" variant="contained" onClick={confirmDeleteProduct} disabled={deleteMutation.isPending}>Delete</Button>
				</DialogActions>
			</Dialog>
		</Stack>
	);
}