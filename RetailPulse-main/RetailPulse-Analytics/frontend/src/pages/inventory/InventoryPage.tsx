import { Alert, Box, Paper, Stack, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
	adjustInventoryStock,
	getInventoryDashboard,
	listCategories,
	listInventoryBrands,
	listInventory,
	listInventoryMovements,
	listInventoryNotifications,
	updateInventoryReorderLevel,
} from "../../api/catalogApi";
import { useAuth } from "../../context/AuthContext";
import { useNotification } from "../../context/NotificationContext";
import {
	CategoryItem,
	InventoryAdjustmentPayload,
	InventoryAdjustmentType,
	InventoryItem,
	InventoryMovementType,
	InventoryStockStatus,
} from "../../types/catalog";
import InventoryAdjustmentDialog from "./components/InventoryAdjustmentDialog";
import InventoryDashboardPanel from "./components/InventoryDashboardPanel";
import InventoryFiltersBar from "./components/InventoryFiltersBar";
import InventoryNotificationsPanel from "./components/InventoryNotificationsPanel";
import InventoryReorderDialog from "./components/InventoryReorderDialog";
import InventoryTable from "./components/InventoryTable";
import MovementHistoryTable from "./components/MovementHistoryTable";

export default function InventoryPage() {
	const queryClient = useQueryClient();
	const { notify } = useNotification();
	const { user } = useAuth();
	const isAdmin = user?.role === "Company Admin" || user?.role === "Super Admin";

	const [search, setSearch] = useState("");
	const [categoryFilter, setCategoryFilter] = useState<number | "all">("all");
	const [brandFilter, setBrandFilter] = useState("");
	const [stockStatusFilter, setStockStatusFilter] = useState<InventoryStockStatus | "all">("all");
	const [sortBy, setSortBy] = useState<"name" | "currentStock" | "recentlyUpdated">("recentlyUpdated");
	const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState(10);

	const [movementFilterType, setMovementFilterType] = useState<InventoryMovementType | "all">("all");
	const [movementPage, setMovementPage] = useState(1);
	const [movementPageSize, setMovementPageSize] = useState(10);

	const [adjustingInventory, setAdjustingInventory] = useState<InventoryItem | null>(null);
	const [adjustmentType, setAdjustmentType] = useState<InventoryAdjustmentType>("stock-addition");
	const [adjustmentQuantity, setAdjustmentQuantity] = useState(1);
	const [targetQuantity, setTargetQuantity] = useState(0);
	const [adjustmentReason, setAdjustmentReason] = useState("");
	const [adjustmentRemarks, setAdjustmentRemarks] = useState("");

	const [reorderEditing, setReorderEditing] = useState<InventoryItem | null>(null);
	const [reorderLevelValue, setReorderLevelValue] = useState(0);
	const [reorderReason, setReorderReason] = useState("");

	const { data: categories = [] } = useQuery({
		queryKey: ["inventory-categories"],
		queryFn: () => listCategories({}),
	});
	const { data: brands = [] } = useQuery({
		queryKey: ["inventory-brands"],
		queryFn: listInventoryBrands,
	});

	const { data: inventoryPageData, isLoading: inventoryLoading, isError: inventoryError } = useQuery({
		queryKey: [
			"inventory-overview",
			search,
			categoryFilter,
			brandFilter,
			stockStatusFilter,
			sortBy,
			sortDirection,
			page,
			pageSize,
		],
		queryFn: () =>
			listInventory({
				search: search || undefined,
				categoryId: categoryFilter === "all" ? undefined : categoryFilter,
				brand: brandFilter || undefined,
				stockStatus: stockStatusFilter === "all" ? undefined : stockStatusFilter,
				sortBy,
				sortDirection,
				page,
				pageSize,
			}),
	});

	const {
		data: inventoryDashboard,
		isError: dashboardError,
		error: dashboardErrorDetails,
		refetch: retryInventoryDashboard,
		isFetching: dashboardRefetching,
	} = useQuery({
		queryKey: ["inventory-dashboard"],
		queryFn: getInventoryDashboard,
	});

	const { data: movementData } = useQuery({
		queryKey: ["inventory-movements", movementFilterType, movementPage, movementPageSize],
		queryFn: () =>
			listInventoryMovements({
				movementType: movementFilterType === "all" ? undefined : movementFilterType,
				page: movementPage,
				pageSize: movementPageSize,
			}),
	});

	const { data: notifications = [] } = useQuery({
		queryKey: ["inventory-notifications"],
		queryFn: () => listInventoryNotifications(20),
		enabled: isAdmin,
	});

	useEffect(() => {
		setPage(1);
	}, [search, categoryFilter, brandFilter, stockStatusFilter, sortBy, sortDirection]);

	useEffect(() => {
		setMovementPage(1);
	}, [movementFilterType]);

	const inventoryItems = inventoryPageData?.items ?? [];
	const inventoryTotal = inventoryPageData?.total ?? 0;
	const inventoryTotalPages = inventoryPageData?.totalPages ?? 0;

	const movementItems = movementData?.items ?? [];
	const movementTotal = movementData?.total ?? 0;
	const movementTotalPages = movementData?.totalPages ?? 0;

	const adjustMutation = useMutation({
		mutationFn: (payload: InventoryAdjustmentPayload) => adjustInventoryStock(payload),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["inventory-overview"] });
			await queryClient.invalidateQueries({ queryKey: ["inventory-movements"] });
			await queryClient.invalidateQueries({ queryKey: ["inventory-dashboard"] });
			await queryClient.invalidateQueries({ queryKey: ["inventory-notifications"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			notify("Stock updated successfully", "success");
			closeAdjustDialog();
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to adjust stock", "error"),
	});

	const reorderMutation = useMutation({
		mutationFn: ({ productId, reorderLevel, reason }: { productId: number; reorderLevel: number; reason: string }) =>
			updateInventoryReorderLevel(productId, { reorderLevel, reason }),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["inventory-overview"] });
			await queryClient.invalidateQueries({ queryKey: ["inventory-dashboard"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
			notify("Reorder level updated", "success");
			closeReorderDialog();
		},
		onError: (error: any) => notify(error?.response?.data?.detail ?? "Unable to update reorder level", "error"),
	});

	const openAdjustDialog = (item: InventoryItem) => {
		setAdjustingInventory(item);
		setAdjustmentType("stock-addition");
		setAdjustmentQuantity(1);
		setTargetQuantity(item.currentStock);
		setAdjustmentReason("");
		setAdjustmentRemarks("");
	};

	const closeAdjustDialog = () => {
		setAdjustingInventory(null);
		setAdjustmentReason("");
		setAdjustmentRemarks("");
	};

	const submitAdjustment = () => {
		if (!adjustingInventory) {
			return;
		}
		if (!adjustmentReason.trim()) {
			notify("Reason is required for stock adjustments", "warning");
			return;
		}

		const payload: InventoryAdjustmentPayload = {
			productId: adjustingInventory.productId,
			adjustmentType,
			reason: adjustmentReason.trim(),
			remarks: adjustmentRemarks.trim() || undefined,
		};

		if (adjustmentType === "manual-adjustment") {
			payload.targetQuantity = Math.max(Number(targetQuantity) || 0, 0);
		} else {
			const quantity = Number(adjustmentQuantity);
			if (!Number.isFinite(quantity) || quantity <= 0) {
				notify("Quantity must be greater than zero", "warning");
				return;
			}
			payload.quantity = quantity;
		}

		adjustMutation.mutate(payload);
	};

	const openReorderDialog = (item: InventoryItem) => {
		setReorderEditing(item);
		setReorderLevelValue(item.reorderLevel);
		setReorderReason("");
	};

	const closeReorderDialog = () => {
		setReorderEditing(null);
		setReorderReason("");
	};

	const submitReorderLevel = () => {
		if (!reorderEditing) {
			return;
		}
		if (!reorderReason.trim()) {
			notify("Reason is required for reorder level updates", "warning");
			return;
		}
		reorderMutation.mutate({
			productId: reorderEditing.productId,
			reorderLevel: Math.max(Number(reorderLevelValue) || 0, 0),
			reason: reorderReason.trim(),
		});
	};

	const categoryOptions = categories as CategoryItem[];
	const dashboardErrorMessage =
		(dashboardErrorDetails as any)?.response?.data?.detail ??
		(dashboardErrorDetails as Error | undefined)?.message ??
		"Unable to load inventory dashboard metrics.";

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={700}>Inventory</Typography>
				<Typography color="text.secondary">Monitor stock levels, track stock movements, and manage adjustments with full history.</Typography>
			</Box>

			<InventoryDashboardPanel
				dashboard={inventoryDashboard}
				isError={dashboardError}
				errorMessage={dashboardErrorMessage}
				onRetry={() => void retryInventoryDashboard()}
				isRetrying={dashboardRefetching}
			/>

			<Paper sx={{ p: 2 }}>
				<Stack spacing={2}>
					<InventoryFiltersBar
						search={search}
						onSearchChange={setSearch}
						categoryFilter={categoryFilter}
						onCategoryChange={setCategoryFilter}
						brandFilter={brandFilter}
						onBrandChange={setBrandFilter}
						brands={brands}
						stockStatusFilter={stockStatusFilter}
						onStockStatusChange={setStockStatusFilter}
						sortBy={sortBy}
						onSortByChange={setSortBy}
						sortDirection={sortDirection}
						onSortDirectionChange={setSortDirection}
						categories={categoryOptions}
					/>

					{inventoryError ? <Alert severity="error">Unable to load inventory overview. Try refreshing.</Alert> : null}
					{!inventoryLoading && inventoryItems.length === 0 ? <Alert severity="info">No inventory records match your filters.</Alert> : null}

					<InventoryTable
						items={inventoryItems}
						isAdmin={isAdmin}
						onAdjust={openAdjustDialog}
						onReorder={openReorderDialog}
						total={inventoryTotal}
						page={page}
						pageSize={pageSize}
						totalPages={inventoryTotalPages}
						onPageChange={setPage}
						onPageSizeChange={(size) => {
							setPageSize(size);
							setPage(1);
						}}
					/>
				</Stack>
			</Paper>

			<Paper sx={{ p: 2 }}>
				<MovementHistoryTable
					items={movementItems}
					total={movementTotal}
					page={movementPage}
					pageSize={movementPageSize}
					totalPages={movementTotalPages}
					movementFilterType={movementFilterType}
					onMovementFilterTypeChange={setMovementFilterType}
					onPageChange={setMovementPage}
					onPageSizeChange={(size) => {
						setMovementPageSize(size);
						setMovementPage(1);
					}}
				/>
			</Paper>

			{isAdmin ? <InventoryNotificationsPanel notifications={notifications} /> : null}

			<InventoryAdjustmentDialog
				open={Boolean(adjustingInventory)}
				item={adjustingInventory}
				adjustmentType={adjustmentType}
				onAdjustmentTypeChange={setAdjustmentType}
				adjustmentQuantity={adjustmentQuantity}
				onAdjustmentQuantityChange={setAdjustmentQuantity}
				targetQuantity={targetQuantity}
				onTargetQuantityChange={setTargetQuantity}
				reason={adjustmentReason}
				onReasonChange={setAdjustmentReason}
				remarks={adjustmentRemarks}
				onRemarksChange={setAdjustmentRemarks}
				onClose={closeAdjustDialog}
				onSubmit={submitAdjustment}
				saving={adjustMutation.isPending}
			/>

			<InventoryReorderDialog
				open={Boolean(reorderEditing)}
				item={reorderEditing}
				reorderLevel={reorderLevelValue}
				onReorderLevelChange={setReorderLevelValue}
				reason={reorderReason}
				onReasonChange={setReorderReason}
				onClose={closeReorderDialog}
				onSubmit={submitReorderLevel}
				saving={reorderMutation.isPending}
			/>
		</Stack>
	);
}
