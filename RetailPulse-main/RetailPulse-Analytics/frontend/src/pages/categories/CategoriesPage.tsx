import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Grid, IconButton, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { createCategory, deleteCategory, listCategories, updateCategory } from "../../api/catalogApi";
import { useNotification } from "../../context/NotificationContext";
import { CategoryFormValues, CategoryItem, CatalogStatus } from "../../types/catalog";

const emptyValues: CategoryFormValues = {
	categoryName: "",
	description: "",
	status: "active",
};

export default function CategoriesPage() {
	const queryClient = useQueryClient();
	const { notify } = useNotification();
	const [search, setSearch] = useState("");
	const [status, setStatus] = useState<CatalogStatus | "all">("all");
	const [open, setOpen] = useState(false);
	const [editingCategory, setEditingCategory] = useState<CategoryItem | null>(null);
	const [pendingDeleteCategory, setPendingDeleteCategory] = useState<CategoryItem | null>(null);

	const { data: categories = [], isLoading } = useQuery({
		queryKey: ["categories", search, status],
		queryFn: () => listCategories({ search: search || undefined, status: status === "all" ? undefined : status }),
	});

	const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<CategoryFormValues>({ defaultValues: emptyValues });

	useEffect(() => {
		if (editingCategory) {
			reset({
				categoryName: editingCategory.name,
				description: editingCategory.description ?? "",
				status: editingCategory.status,
			});
		} else {
			reset(emptyValues);
		}
	}, [editingCategory, reset]);

	const totalProducts = useMemo(() => categories.reduce((count, category) => count + category.productCount, 0), [categories]);

	const createMutation = useMutation({
		mutationFn: createCategory,
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["categories"] });
			notify("Category saved successfully", "success");
			setOpen(false);
			setEditingCategory(null);
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to save category", "error"),
	});

	const updateMutation = useMutation({
		mutationFn: ({ categoryId, payload }: { categoryId: number; payload: CategoryFormValues }) => updateCategory(categoryId, payload),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["categories"] });
			notify("Category updated successfully", "success");
			setOpen(false);
			setEditingCategory(null);
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to update category", "error"),
	});

	const deleteMutation = useMutation({
		mutationFn: deleteCategory,
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["categories"] });
			notify("Category deleted", "success");
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to delete category", "error"),
	});

	const onSubmit = handleSubmit(async (values) => {
		if (editingCategory) {
			updateMutation.mutate({ categoryId: editingCategory.id, payload: values });
			return;
		}
		createMutation.mutate(values);
	});

	const openCreateDialog = () => {
		setEditingCategory(null);
		setOpen(true);
	};

	const openEditDialog = (category: CategoryItem) => {
		setEditingCategory(category);
		setOpen(true);
	};

	const closeDialog = () => {
		setOpen(false);
		setEditingCategory(null);
	};

	const closeDeleteDialog = () => {
		setPendingDeleteCategory(null);
	};

	const confirmDeleteCategory = () => {
		if (!pendingDeleteCategory) {
			return;
		}
		deleteMutation.mutate(pendingDeleteCategory.id, {
			onSuccess: () => {
				closeDeleteDialog();
			},
		});
	};

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Categories</Typography>
				<Typography color="text.secondary">Manage company product categories with search, edit, and status control.</Typography>
			</Box>

			<Grid container spacing={2}>
				<Grid size={{ xs: 12, md: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography color="text.secondary">Total Categories</Typography>
						<Typography variant="h4" fontWeight={700}>{categories.length}</Typography>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, md: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography color="text.secondary">Total Products</Typography>
						<Typography variant="h4" fontWeight={700}>{totalProducts}</Typography>
					</Paper>
				</Grid>
				<Grid size={{ xs: 12, md: 4 }}>
					<Paper sx={{ p: 2 }}>
						<Typography color="text.secondary">Active Categories</Typography>
						<Typography variant="h4" fontWeight={700}>{categories.filter((item) => item.status === "active").length}</Typography>
					</Paper>
				</Grid>
			</Grid>

			<Paper sx={{ p: 2 }}>
				<Stack spacing={2}>
					<Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }} justifyContent="space-between">
						<TextField fullWidth label="Search categories" value={search} onChange={(event) => setSearch(event.target.value)} />
						<TextField select label="Status" value={status} onChange={(event) => setStatus(event.target.value as CatalogStatus | "all")} sx={{ minWidth: 180 }}>
							<MenuItem value="all">All</MenuItem>
							<MenuItem value="active">Active</MenuItem>
							<MenuItem value="inactive">Inactive</MenuItem>
						</TextField>
						<Button startIcon={<AddIcon />} variant="contained" onClick={openCreateDialog}>New Category</Button>
					</Stack>

					{!isLoading && categories.length === 0 ? (
						<Alert severity="info">No categories found. Create your first category to organize products.</Alert>
					) : null}

					<Box sx={{ overflowX: "auto" }}>
						<table style={{ width: "100%", borderCollapse: "collapse" }}>
							<thead>
								<tr>
									{["Name", "Description", "Status", "Products", "Actions"].map((heading) => (
										<th key={heading} style={{ textAlign: "left", padding: "12px 8px", borderBottom: "1px solid #e5ddd0" }}>{heading}</th>
									))}
								</tr>
							</thead>
							<tbody>
								{categories.map((category) => (
									<tr key={category.id}>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de", fontWeight: 600 }}>{category.name}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{category.description || "-"}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>
											<Chip size="small" label={category.status} color={category.status === "active" ? "success" : "default"} />
										</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{category.productCount}</td>
										<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>
											<Stack direction="row" spacing={1}>
												<IconButton size="small" onClick={() => openEditDialog(category)}><EditIcon fontSize="small" /></IconButton>
												<IconButton size="small" onClick={() => setPendingDeleteCategory(category)}><DeleteIcon fontSize="small" /></IconButton>
											</Stack>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</Box>
				</Stack>
			</Paper>

			<Dialog open={open} onClose={closeDialog} fullWidth maxWidth="sm">
				<DialogTitle>{editingCategory ? "Edit Category" : "Create Category"}</DialogTitle>
				<form onSubmit={onSubmit}>
					<DialogContent>
						<Stack spacing={2} sx={{ pt: 1 }}>
							<TextField label="Category Name" {...register("categoryName", { required: "Category name is required" })} error={Boolean(errors.categoryName)} helperText={errors.categoryName?.message} />
							<TextField label="Description" multiline minRows={3} {...register("description")} />
							<TextField select label="Status" {...register("status", { required: true })}>
								<MenuItem value="active">Active</MenuItem>
								<MenuItem value="inactive">Inactive</MenuItem>
							</TextField>
						</Stack>
					</DialogContent>
					<DialogActions>
						<Button onClick={closeDialog} color="inherit">Cancel</Button>
						<Button type="submit" variant="contained" disabled={isSubmitting || createMutation.isPending || updateMutation.isPending}>
							{editingCategory ? "Update" : "Create"}
						</Button>
					</DialogActions>
				</form>
			</Dialog>

			<Dialog open={Boolean(pendingDeleteCategory)} onClose={closeDeleteDialog} fullWidth maxWidth="xs">
				<DialogTitle>Delete Category</DialogTitle>
				<DialogContent>
					<Typography>
						Are you sure you want to delete {pendingDeleteCategory?.name}? This action cannot be undone.
					</Typography>
				</DialogContent>
				<DialogActions>
					<Button onClick={closeDeleteDialog} color="inherit">Cancel</Button>
					<Button color="error" variant="contained" onClick={confirmDeleteCategory} disabled={deleteMutation.isPending}>Delete</Button>
				</DialogActions>
			</Dialog>
		</Stack>
	);
}