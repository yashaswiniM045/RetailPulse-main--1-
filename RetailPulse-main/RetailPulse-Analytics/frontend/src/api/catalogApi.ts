import { apiClient } from "./axios";
import {
	CategoryFormValues,
	CategoryItem,
	CatalogStatus,
	CustomerAnalytics,
	CustomerFormValues,
	CustomerItem,
	CustomerNotificationItem,
	CustomerOptionItem,
	CustomerProfile,
	DashboardAnalytics,
	DashboardDrilldownKpiRecord,
	DashboardFilters,
	DashboardInventoryProduct,
	DashboardProductTransaction,
	DashboardQueryFilters,
	DashboardSummary,
	ForecastDashboard,
	ForecastFilterOptions,
	ForecastNotificationItem,
	ForecastPeriod,
	ForecastProductRow,
	ForecastSortBy,
	ForecastSortDirection,
	InventoryAdjustmentPayload,
	InventoryDashboardSummary,
	InventoryItem,
	InventoryMovementItem,
	InventoryMovementType,
	InventoryNotificationItem,
	InventoryReorderLevelPayload,
	InventoryStockStatus,
	PaymentMethod,
	PaymentStatus,
	PaginatedResult,
	ProductFormValues,
	ProductItem,
	SaleFormValues,
	SaleListItem,
	SaleNotification,
	SaleRecord,
	SalesChannel,
} from "../types/catalog";

function toNumber(value: unknown): number {
	return typeof value === "number" ? value : Number(value ?? 0);
}

function normalizeCategory(data: Record<string, unknown>): CategoryItem {
	return {
		id: toNumber(data.id),
		name: (data.name as string) ?? "",
		description: (data.description as string | null | undefined) ?? null,
		status: ((data.status as CatalogStatus | undefined) ?? "active") as CatalogStatus,
		productCount: toNumber(data.productCount ?? data.product_count),
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string),
		updatedAt: (data.updatedAt as string | undefined) ?? (data.updated_at as string),
	};
}

function normalizeProduct(data: Record<string, unknown>): ProductItem {
	const category = (data.category as Record<string, unknown>) ?? {};
	return {
		id: toNumber(data.id),
		name: (data.name as string) ?? "",
		sku: (data.sku as string) ?? "",
		category: {
			id: toNumber(category.id),
			name: (category.name as string) ?? "",
			status: ((category.status as CatalogStatus | undefined) ?? "active") as CatalogStatus,
		},
		brand: (data.brand as string | null | undefined) ?? null,
		description: (data.description as string | null | undefined) ?? null,
		unitPrice: toNumber(data.unitPrice ?? data.unit_price),
		costPrice: toNumber(data.costPrice ?? data.cost_price),
		stockQuantity: toNumber(data.stockQuantity ?? data.stock_quantity),
		isOutOfStock: Boolean(data.isOutOfStock ?? data.is_out_of_stock),
		unitOfMeasure: (data.unitOfMeasure as string | undefined) ?? (data.unit_of_measure as string),
		status: ((data.status as CatalogStatus | undefined) ?? "active") as CatalogStatus,
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string),
		updatedAt: (data.updatedAt as string | undefined) ?? (data.updated_at as string),
	};
}

function normalizeSaleNotification(data: Record<string, unknown>): SaleNotification {
	return {
		type: ((data.type as SaleNotification["type"] | undefined) ?? "low-stock") as SaleNotification["type"],
		message: (data.message as string | undefined) ?? "",
	};
}

function normalizeSaleListItem(data: Record<string, unknown>): SaleListItem {
	return {
		id: toNumber(data.id),
		customerId: data.customerId !== undefined || data.customer_id !== undefined ? toNumber(data.customerId ?? data.customer_id) : null,
		invoiceNumber: (data.invoiceNumber as string | undefined) ?? (data.invoice_number as string) ?? "",
		customerName: (data.customerName as string | undefined) ?? (data.customer_name as string) ?? "",
		saleDate: (data.saleDate as string | undefined) ?? (data.sale_date as string) ?? "",
		salesChannel: ((data.salesChannel as SalesChannel | undefined) ?? (data.sales_channel as SalesChannel) ?? "other") as SalesChannel,
		paymentMethod: ((data.paymentMethod as PaymentMethod | undefined) ?? (data.payment_method as PaymentMethod) ?? "other") as PaymentMethod,
		paymentStatus: ((data.paymentStatus as PaymentStatus | undefined) ?? (data.payment_status as PaymentStatus) ?? "paid") as PaymentStatus,
		totalAmount: toNumber(data.totalAmount ?? data.total_amount),
		createdByName: (data.createdByName as string | undefined) ?? (data.created_by_name as string) ?? "",
		itemCount: toNumber(data.itemCount ?? data.item_count),
	};
}

function normalizeSaleRecord(data: Record<string, unknown>): SaleRecord {
	const items = ((data.items as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
		id: toNumber(item.id),
		productId: toNumber(item.productId ?? item.product_id),
		productName: (item.productName as string | undefined) ?? (item.product_name as string) ?? "",
		sku: (item.sku as string | undefined) ?? "",
		categoryId: toNumber(item.categoryId ?? item.category_id),
		categoryName: (item.categoryName as string | undefined) ?? (item.category_name as string) ?? "",
		quantity: toNumber(item.quantity),
		unitPrice: toNumber(item.unitPrice ?? item.unit_price),
		discount: toNumber(item.discount),
		tax: toNumber(item.tax),
		total: toNumber(item.total),
		remainingStock: toNumber(item.remainingStock ?? item.remaining_stock),
	}));

	return {
		id: toNumber(data.id),
		customerId: data.customerId !== undefined || data.customer_id !== undefined ? toNumber(data.customerId ?? data.customer_id) : null,
		invoiceNumber: (data.invoiceNumber as string | undefined) ?? (data.invoice_number as string) ?? "",
		customerName: (data.customerName as string | undefined) ?? (data.customer_name as string) ?? "",
		saleDate: (data.saleDate as string | undefined) ?? (data.sale_date as string) ?? "",
		salesChannel: ((data.salesChannel as SalesChannel | undefined) ?? (data.sales_channel as SalesChannel) ?? "other") as SalesChannel,
		paymentMethod: ((data.paymentMethod as PaymentMethod | undefined) ?? (data.payment_method as PaymentMethod) ?? "other") as PaymentMethod,
		paymentStatus: ((data.paymentStatus as PaymentStatus | undefined) ?? (data.payment_status as PaymentStatus) ?? "paid") as PaymentStatus,
		notes: ((data.notes as string | null | undefined) ?? null),
		subtotal: toNumber(data.subtotal),
		discountTotal: toNumber(data.discountTotal ?? data.discount_total),
		taxTotal: toNumber(data.taxTotal ?? data.tax_total),
		totalAmount: toNumber(data.totalAmount ?? data.total_amount),
		createdBy: toNumber(data.createdBy ?? data.created_by),
		createdByName: (data.createdByName as string | undefined) ?? (data.created_by_name as string) ?? "",
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string) ?? "",
		updatedAt: (data.updatedAt as string | undefined) ?? (data.updated_at as string) ?? "",
		items,
		notifications: ((data.notifications as Record<string, unknown>[] | undefined) ?? []).map(normalizeSaleNotification),
	};
}

function normalizeDashboard(data: Record<string, unknown>): DashboardSummary {
	return {
		totalProducts: toNumber(data.totalProducts ?? data.total_products),
		activeProducts: toNumber(data.activeProducts ?? data.active_products),
		inactiveProducts: toNumber(data.inactiveProducts ?? data.inactive_products),
		totalCategories: toNumber(data.totalCategories ?? data.total_categories),
		totalSales: toNumber(data.totalSales ?? data.total_sales),
		totalRevenue: toNumber(data.totalRevenue ?? data.total_revenue),
		totalOrders: toNumber(data.totalOrders ?? data.total_orders),
		averageOrderValue: toNumber(data.averageOrderValue ?? data.average_order_value),
	};
}

function normalizeDashboardInventoryProduct(data: Record<string, unknown>): DashboardInventoryProduct {
	return {
		productId: toNumber(data.productId ?? data.product_id),
		productName: (data.productName as string | undefined) ?? (data.product_name as string) ?? "",
		sku: (data.sku as string | undefined) ?? "",
		categoryName: (data.categoryName as string | undefined) ?? (data.category_name as string) ?? "",
		brand: (data.brand as string | null | undefined) ?? null,
		currentStock: toNumber(data.currentStock ?? data.current_stock),
		reorderLevel: toNumber(data.reorderLevel ?? data.reorder_level),
		stockStatus: ((data.stockStatus as InventoryStockStatus | undefined) ??
			(data.stock_status as InventoryStockStatus) ??
			"in-stock") as InventoryStockStatus,
		quantitySold:
			data.quantitySold !== undefined || data.quantity_sold !== undefined
				? toNumber(data.quantitySold ?? data.quantity_sold)
				: undefined,
		revenue:
			data.revenue !== undefined
				? toNumber(data.revenue)
				: undefined,
	};
}

function normalizeDashboardAnalytics(data: Record<string, unknown>): DashboardAnalytics {
	const kpis = (data.kpis as Record<string, unknown>) ?? {};
	return {
		kpis: {
			totalRevenue: toNumber(kpis.totalRevenue ?? kpis.total_revenue),
			totalOrders: toNumber(kpis.totalOrders ?? kpis.total_orders),
			totalProductsSold: toNumber(kpis.totalProductsSold ?? kpis.total_products_sold),
			averageOrderValue: toNumber(kpis.averageOrderValue ?? kpis.average_order_value),
			totalDiscount: toNumber(kpis.totalDiscount ?? kpis.total_discount),
			totalTax: toNumber(kpis.totalTax ?? kpis.total_tax),
			totalInventoryValue: toNumber(kpis.totalInventoryValue ?? kpis.total_inventory_value),
			lowStockProducts: toNumber(kpis.lowStockProducts ?? kpis.low_stock_products),
			outOfStockProducts: toNumber(kpis.outOfStockProducts ?? kpis.out_of_stock_products),
			totalCategories: toNumber(kpis.totalCategories ?? kpis.total_categories),
		},
		revenueTrend: ((data.revenueTrend as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			period: (item.period as string | undefined) ?? "",
			revenue: toNumber(item.revenue),
			orders: toNumber(item.orders),
			productsSold: toNumber(item.productsSold ?? item.products_sold),
		})),
		salesTrend: ((data.salesTrend as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			period: (item.period as string | undefined) ?? "",
			revenue: toNumber(item.revenue),
			orders: toNumber(item.orders),
			productsSold: toNumber(item.productsSold ?? item.products_sold),
		})),
		topProducts: ((data.topProducts as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			productId: toNumber(item.productId ?? item.product_id),
			productName: (item.productName as string | undefined) ?? (item.product_name as string) ?? "",
			quantitySold: toNumber(item.quantitySold ?? item.quantity_sold),
			revenue: toNumber(item.revenue),
		})),
		topCategories: ((data.topCategories as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			categoryId: toNumber(item.categoryId ?? item.category_id),
			categoryName: (item.categoryName as string | undefined) ?? (item.category_name as string) ?? "",
			orders: toNumber(item.orders),
			productsSold: toNumber(item.productsSold ?? item.products_sold),
			revenue: toNumber(item.revenue),
		})),
		paymentMethodDistribution: ((data.paymentMethodDistribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
			transactions: item.transactions !== undefined ? toNumber(item.transactions) : undefined,
		})),
		salesChannelDistribution: ((data.salesChannelDistribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		inventoryDistributionByCategory: ((data.inventoryDistributionByCategory as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			categoryId: toNumber(item.categoryId ?? item.category_id),
			categoryName: (item.categoryName as string | undefined) ?? (item.category_name as string) ?? "",
			quantity: toNumber(item.quantity),
			productCount: toNumber(item.productCount ?? item.product_count),
		})),
		stockStatusSummary: ((data.stockStatusSummary as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		topLowStockProducts: ((data.topLowStockProducts as Record<string, unknown>[] | undefined) ?? []).map(normalizeDashboardInventoryProduct),
		outOfStockProducts: ((data.outOfStockProducts as Record<string, unknown>[] | undefined) ?? []).map(normalizeDashboardInventoryProduct),
		inventoryValueByCategory: ((data.inventoryValueByCategory as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			categoryId: toNumber(item.categoryId ?? item.category_id),
			categoryName: (item.categoryName as string | undefined) ?? (item.category_name as string) ?? "",
			inventoryValue: toNumber(item.inventoryValue ?? item.inventory_value),
		})),
		topCustomers: ((data.topCustomers as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			customerId: toNumber(item.customerId ?? item.customer_id),
			customerName: (item.customerName as string | undefined) ?? (item.customer_name as string) ?? "",
			revenue: toNumber(item.revenue),
			orders: toNumber(item.orders),
			averageOrderValue: toNumber(item.averageOrderValue ?? item.average_order_value),
		})),
		recentCustomers: ((data.recentCustomers as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			customerId: toNumber(item.customerId ?? item.customer_id),
			customerCode: (item.customerCode as string | undefined) ?? (item.customer_code as string) ?? "",
			customerName: (item.customerName as string | undefined) ?? (item.customer_name as string) ?? "",
			customerSince: (item.customerSince as string | undefined) ?? (item.customer_since as string) ?? "",
		})),
		customerGrowth: ((data.customerGrowth as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			period: (item.period as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		customerRevenueContribution: ((data.customerRevenueContribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			customerId: toNumber(item.customerId ?? item.customer_id),
			customerName: (item.customerName as string | undefined) ?? (item.customer_name as string) ?? "",
			contributionPercent: toNumber(item.contributionPercent ?? item.contribution_percent),
		})),
		lastUpdatedAt: (data.lastUpdatedAt as string | null | undefined) ?? (data.last_updated_at as string | null | undefined) ?? null,
	};
}

function normalizeDashboardFilters(data: Record<string, unknown>): DashboardFilters {
	return {
		products: ((data.products as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			id: toNumber(item.id),
			name: (item.name as string | undefined) ?? "",
		})),
		categories: ((data.categories as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			id: toNumber(item.id),
			name: (item.name as string | undefined) ?? "",
		})),
		brands: ((data.brands as string[] | undefined) ?? []).filter(Boolean),
		salesChannels: ((data.salesChannels as SalesChannel[] | undefined) ?? (data.sales_channels as SalesChannel[] | undefined) ?? []),
		paymentMethods: ((data.paymentMethods as PaymentMethod[] | undefined) ?? (data.payment_methods as PaymentMethod[] | undefined) ?? []),
	};
}

function normalizeDashboardKpiRecord(data: Record<string, unknown>): DashboardDrilldownKpiRecord {
	return {
		id: String(data.id ?? ""),
		label: (data.label as string | undefined) ?? "",
		secondary: (data.secondary as string | null | undefined) ?? null,
		value: toNumber(data.value),
	};
}

function normalizeDashboardProductTransaction(data: Record<string, unknown>): DashboardProductTransaction {
	return {
		saleId: toNumber(data.saleId ?? data.sale_id),
		invoiceNumber: (data.invoiceNumber as string | undefined) ?? (data.invoice_number as string) ?? "",
		saleDate: (data.saleDate as string | undefined) ?? (data.sale_date as string) ?? "",
		customerName: (data.customerName as string | undefined) ?? (data.customer_name as string) ?? "",
		salesChannel: ((data.salesChannel as SalesChannel | undefined) ?? (data.sales_channel as SalesChannel) ?? "other") as SalesChannel,
		paymentMethod: ((data.paymentMethod as PaymentMethod | undefined) ?? (data.payment_method as PaymentMethod) ?? "other") as PaymentMethod,
		quantity: toNumber(data.quantity),
		total: toNumber(data.total),
	};
}

function toDashboardParams(filters?: DashboardQueryFilters) {
	if (!filters) {
		return undefined;
	}
	return {
		dateGrain: filters.dateGrain,
		startDate: filters.startDate,
		endDate: filters.endDate,
		productId: filters.productId,
		categoryId: filters.categoryId,
		brand: filters.brand,
		salesChannel: filters.salesChannel,
		paymentMethod: filters.paymentMethod,
	};
}
function normalizeInventoryItem(data: Record<string, unknown>): InventoryItem {
	return {
		id: toNumber(data.id),
		productId: toNumber(data.productId ?? data.product_id),
		productName: (data.productName as string | undefined) ?? (data.product_name as string) ?? "",
		sku: (data.sku as string | undefined) ?? "",
		category: (data.category as string | undefined) ?? "",
		brand: (data.brand as string | null | undefined) ?? null,
		currentStock: toNumber(data.currentStock ?? data.current_stock),
		reservedStock: toNumber(data.reservedStock ?? data.reserved_stock),
		availableStock: toNumber(data.availableStock ?? data.available_stock),
		reorderLevel: toNumber(data.reorderLevel ?? data.reorder_level),
		stockStatus: ((data.stockStatus as InventoryStockStatus | undefined) ?? (data.stock_status as InventoryStockStatus) ?? "in-stock") as InventoryStockStatus,
		updatedAt: (data.updatedAt as string | undefined) ?? (data.updated_at as string) ?? "",
	};
}

function normalizeInventoryMovement(data: Record<string, unknown>): InventoryMovementItem {
	return {
		id: toNumber(data.id),
		inventoryId: toNumber(data.inventoryId ?? data.inventory_id),
		productId: toNumber(data.productId ?? data.product_id),
		productName: (data.productName as string | undefined) ?? (data.product_name as string) ?? "",
		sku: (data.sku as string | undefined) ?? "",
		movementType: ((data.movementType as InventoryMovementType | undefined) ?? (data.movement_type as InventoryMovementType) ?? "manual-adjustment") as InventoryMovementType,
		previousQuantity: toNumber(data.previousQuantity ?? data.previous_quantity),
		updatedQuantity: toNumber(data.updatedQuantity ?? data.updated_quantity),
		quantityChanged: toNumber(data.quantityChanged ?? data.quantity_changed),
		reason: (data.reason as string | undefined) ?? "",
		remarks: (data.remarks as string | null | undefined) ?? null,
		performedBy: (data.performedBy as string | null | undefined) ?? (data.performed_by as string | null | undefined) ?? null,
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string) ?? "",
	};
}

function normalizeInventoryDashboard(data: Record<string, unknown>): InventoryDashboardSummary {
	return {
		totalProducts: toNumber(data.totalProducts ?? data.total_products),
		totalInventoryQuantity: toNumber(data.totalInventoryQuantity ?? data.total_inventory_quantity),
		lowStockProducts: toNumber(data.lowStockProducts ?? data.low_stock_products),
		outOfStockProducts: toNumber(data.outOfStockProducts ?? data.out_of_stock_products),
		inventoryByCategory: ((data.inventoryByCategory as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			category: (item.category as string | undefined) ?? "",
			totalQuantity: toNumber(item.totalQuantity ?? item.total_quantity),
			productCount: toNumber(item.productCount ?? item.product_count),
		})),
		stockStatusDistribution: ((data.stockStatusDistribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			status: ((item.status as InventoryStockStatus | undefined) ?? "in-stock") as InventoryStockStatus,
			count: toNumber(item.count),
		})),
	};
}

function normalizeInventoryNotification(data: Record<string, unknown>): InventoryNotificationItem {
	return {
		id: toNumber(data.id),
		productId: (data.productId as number | null | undefined) ?? (data.product_id as number | null | undefined) ?? null,
		productName: (data.productName as string | null | undefined) ?? (data.product_name as string | null | undefined) ?? null,
		notificationType: ((data.notificationType as InventoryNotificationItem["notificationType"] | undefined) ?? "stock-adjusted") as InventoryNotificationItem["notificationType"],
		message: (data.message as string | undefined) ?? "",
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string) ?? "",
	};
}

function normalizePaginatedResponse<T>(
	data: Record<string, unknown>,
	normalizer: (item: Record<string, unknown>) => T,
): PaginatedResult<T> {
	const items = ((data.items as Record<string, unknown>[] | undefined) ?? []).map(normalizer);
	return {
		items,
		total: toNumber(data.total),
		page: toNumber(data.page),
		pageSize: toNumber(data.pageSize ?? data.page_size),
		totalPages: toNumber(data.totalPages ?? data.total_pages),
	};
}

export async function getDashboardSummary() {
	const response = await apiClient.get<Record<string, unknown>>("/dashboard/summary");
	return normalizeDashboard(response.data);
}

export async function getDashboardFilters() {
	const response = await apiClient.get<Record<string, unknown>>("/dashboard/filters");
	return normalizeDashboardFilters(response.data);
}

export async function getDashboardAnalytics(filters?: DashboardQueryFilters) {
	const response = await apiClient.get<Record<string, unknown>>("/dashboard/analytics", {
		params: toDashboardParams(filters),
	});
	return normalizeDashboardAnalytics(response.data);
}

export async function getDashboardKpiDrilldown(
	kpiKey: string,
	filters?: DashboardQueryFilters & { page?: number; pageSize?: number },
) {
	const response = await apiClient.get<Record<string, unknown>>("/dashboard/drilldown/kpi", {
		params: {
			kpiKey,
			...toDashboardParams(filters),
			page: filters?.page,
			pageSize: filters?.pageSize,
		},
	});
	return normalizePaginatedResponse(response.data, normalizeDashboardKpiRecord);
}

export async function getDashboardCategoryProductsDrilldown(
	categoryId: number,
	filters?: DashboardQueryFilters & { page?: number; pageSize?: number },
) {
	const response = await apiClient.get<Record<string, unknown>>(`/dashboard/drilldown/category/${categoryId}/products`, {
		params: {
			startDate: filters?.startDate,
			endDate: filters?.endDate,
			brand: filters?.brand,
			salesChannel: filters?.salesChannel,
			paymentMethod: filters?.paymentMethod,
			page: filters?.page,
			pageSize: filters?.pageSize,
		},
	});
	return normalizePaginatedResponse(response.data, normalizeDashboardInventoryProduct);
}

export async function getDashboardProductTransactionsDrilldown(
	productId: number,
	filters?: DashboardQueryFilters & { page?: number; pageSize?: number },
) {
	const response = await apiClient.get<Record<string, unknown>>(`/dashboard/drilldown/product/${productId}/transactions`, {
		params: {
			startDate: filters?.startDate,
			endDate: filters?.endDate,
			salesChannel: filters?.salesChannel,
			paymentMethod: filters?.paymentMethod,
			page: filters?.page,
			pageSize: filters?.pageSize,
		},
	});
	return normalizePaginatedResponse(response.data, normalizeDashboardProductTransaction);
}

export async function exportDashboardCsv(filters?: DashboardQueryFilters) {
	const response = await apiClient.get<Blob>("/dashboard/export/csv", {
		params: toDashboardParams(filters),
		responseType: "blob",
	});
	return response.data;
}

export async function exportDashboardPdf(filters?: DashboardQueryFilters) {
	const response = await apiClient.get<Blob>("/dashboard/export/pdf", {
		params: toDashboardParams(filters),
		responseType: "blob",
	});
	return response.data;
}

export async function listCategories(params: { search?: string; status?: CatalogStatus }) {
	const response = await apiClient.get<Record<string, unknown>[]>("/categories", { params });
	return response.data.map(normalizeCategory);
}

export async function getCategory(categoryId: number) {
	const response = await apiClient.get<Record<string, unknown>>(`/categories/${categoryId}`);
	return normalizeCategory(response.data);
}

export async function createCategory(payload: CategoryFormValues) {
	const response = await apiClient.post<Record<string, unknown>>("/categories", payload);
	return normalizeCategory(response.data);
}

export async function updateCategory(categoryId: number, payload: CategoryFormValues) {
	const response = await apiClient.put<Record<string, unknown>>(`/categories/${categoryId}`, payload);
	return normalizeCategory(response.data);
}

export async function deleteCategory(categoryId: number) {
	await apiClient.delete(`/categories/${categoryId}`);
}

export async function listProducts(params: {
	search?: string;
	categoryId?: number;
	status?: CatalogStatus;
	sortBy?: "name" | "price" | "recentlyAdded";
	sortDirection?: "asc" | "desc";
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<Record<string, unknown>>("/products", { params });
	return normalizePaginatedResponse(response.data, normalizeProduct);
}

export async function getProduct(productId: number) {
	const response = await apiClient.get<Record<string, unknown>>(`/products/${productId}`);
	return normalizeProduct(response.data);
}

export async function createProduct(payload: ProductFormValues) {
	const response = await apiClient.post<Record<string, unknown>>("/products", payload);
	return normalizeProduct(response.data);
}

export async function updateProduct(productId: number, payload: ProductFormValues) {
	const response = await apiClient.put<Record<string, unknown>>(`/products/${productId}`, payload);
	return normalizeProduct(response.data);
}

export async function setProductStatus(productId: number, status: CatalogStatus) {
	const response = await apiClient.patch<Record<string, unknown>>(`/products/${productId}/status`, { status });
	return normalizeProduct(response.data);
}

export async function deleteProduct(productId: number) {
	await apiClient.delete(`/products/${productId}`);
}

export async function listSales(params: {
	search?: string;
	startDate?: string;
	endDate?: string;
	categoryId?: number;
	salesChannel?: SalesChannel;
	paymentMethod?: PaymentMethod;
	paymentStatus?: PaymentStatus;
	sortBy?: "date" | "invoiceNumber" | "totalAmount" | "customerName";
	sortDirection?: "asc" | "desc";
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<Record<string, unknown>>("/sales", { params });
	return normalizePaginatedResponse(response.data, normalizeSaleListItem);
}

export async function getSale(saleId: number) {
	const response = await apiClient.get<Record<string, unknown>>(`/sales/${saleId}`);
	return normalizeSaleRecord(response.data);
}

export async function createSale(payload: SaleFormValues) {
	const response = await apiClient.post<Record<string, unknown>>("/sales", payload);
	return normalizeSaleRecord(response.data);
}

export async function updateSale(saleId: number, payload: SaleFormValues) {
	const response = await apiClient.put<Record<string, unknown>>(`/sales/${saleId}`, payload);
	return normalizeSaleRecord(response.data);
}

export async function deleteSale(saleId: number) {
	await apiClient.delete(`/sales/${saleId}`);
}

export async function exportSaleInvoiceCsv(saleId: number) {
	const response = await apiClient.get<Blob>(`/sales/${saleId}/invoice/csv`, { responseType: "blob" });
	return response.data;
}

export async function exportSaleInvoicePdf(saleId: number) {
	const response = await apiClient.get<Blob>(`/sales/${saleId}/invoice/pdf`, { responseType: "blob" });
	return response.data;
}

export async function listInventory(params: {
	search?: string;
	categoryId?: number;
	brand?: string;
	stockStatus?: InventoryStockStatus;
	sortBy?: "name" | "currentStock" | "recentlyUpdated";
	sortDirection?: "asc" | "desc";
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<Record<string, unknown>>("/inventory", { params });
	return normalizePaginatedResponse(response.data, normalizeInventoryItem);
}

export async function getInventoryDashboard() {
	const response = await apiClient.get<Record<string, unknown>>("/inventory/dashboard");
	return normalizeInventoryDashboard(response.data);
}

export async function listInventoryMovements(params: {
	productId?: number;
	movementType?: InventoryMovementType;
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<Record<string, unknown>>("/inventory/movements", { params });
	return normalizePaginatedResponse(response.data, normalizeInventoryMovement);
}

export async function adjustInventoryStock(payload: InventoryAdjustmentPayload) {
	const response = await apiClient.post<Record<string, unknown>>("/inventory/adjustments", payload);
	return normalizeInventoryItem(response.data);
}

export async function updateInventoryReorderLevel(productId: number, payload: InventoryReorderLevelPayload) {
	const response = await apiClient.patch<Record<string, unknown>>(`/inventory/${productId}/reorder-level`, payload);
	return normalizeInventoryItem(response.data);
}

export async function listInventoryNotifications(limit = 20) {
	const response = await apiClient.get<Record<string, unknown>[]>("/inventory/notifications", { params: { limit } });
	return response.data.map(normalizeInventoryNotification);
}

export async function listInventoryBrands() {
	const response = await apiClient.get<string[]>("/inventory/brands");
	return response.data;
}

function normalizeCustomer(data: Record<string, unknown>): CustomerItem {
	const fullName = (data.fullName as string | undefined) ?? (data.full_name as string) ?? "";
	const [firstName = "", ...tailNames] = fullName.trim().split(/\s+/);
	const lastName = tailNames.join(" ");
	return {
		id: toNumber(data.id),
		customerId: (data.customerId as string | undefined) ?? (data.customer_code as string) ?? "",
		fullName,
		firstName,
		lastName,
		email: (data.email as string | undefined) ?? "",
		phoneNumber: (data.phoneNumber as string | undefined) ?? (data.phone_number as string) ?? "",
		dateOfBirth: (data.dateOfBirth as string | null | undefined) ?? (data.date_of_birth as string | null | undefined) ?? null,
		gender: ((data.gender as any) ?? null),
		addressLine1: (data.addressLine1 as string | null | undefined) ?? (data.address_line1 as string | null | undefined) ?? null,
		addressLine2: (data.addressLine2 as string | null | undefined) ?? (data.address_line2 as string | null | undefined) ?? null,
		city: (data.city as string | null | undefined) ?? null,
		state: (data.state as string | null | undefined) ?? null,
		country: (data.country as string | null | undefined) ?? null,
		postalCode: (data.postalCode as string | null | undefined) ?? (data.postal_code as string | null | undefined) ?? null,
		customerType: ((data.customerType as any) ?? (data.customer_type as any) ?? "retail"),
		preferredSalesChannel: ((data.preferredSalesChannel as any) ?? (data.preferred_sales_channel as any) ?? null),
		status: ((data.status as any) ?? "active"),
		segment: ((data.segment as any) ?? "new"),
		totalPurchases: toNumber(data.totalPurchases ?? data.total_purchases),
		totalSpend: toNumber(data.totalSpend ?? data.total_spend),
		lastPurchaseDate: (data.lastPurchaseDate as string | null | undefined) ?? (data.last_purchase_date as string | null | undefined) ?? null,
		customerSince: (data.customerSince as string | undefined) ?? (data.created_at as string) ?? "",
		updatedAt: (data.updatedAt as string | undefined) ?? (data.updated_at as string) ?? "",
	};
}

function normalizeCustomerProfile(data: Record<string, unknown>): CustomerProfile {
	const purchaseSummary = (data.purchaseSummary as Record<string, unknown> | undefined) ?? (data.purchase_summary as Record<string, unknown> | undefined) ?? {};
	return {
		customer: normalizeCustomer((data.customer as Record<string, unknown>) ?? {}),
		purchaseSummary: {
			totalOrders: toNumber(purchaseSummary.totalOrders ?? purchaseSummary.total_orders),
			totalRevenue: toNumber(purchaseSummary.totalRevenue ?? purchaseSummary.total_revenue),
			quantityPurchased: toNumber(purchaseSummary.quantityPurchased ?? purchaseSummary.quantity_purchased),
			averageOrderValue: toNumber(purchaseSummary.averageOrderValue ?? purchaseSummary.average_order_value),
			firstPurchaseDate: (purchaseSummary.firstPurchaseDate as string | null | undefined) ?? (purchaseSummary.first_purchase_at as string | null | undefined) ?? null,
			lastPurchaseDate: (purchaseSummary.lastPurchaseDate as string | null | undefined) ?? (purchaseSummary.last_purchase_at as string | null | undefined) ?? null,
			purchaseFrequencyDays: toNumber(purchaseSummary.purchaseFrequencyDays ?? purchaseSummary.purchase_frequency_days),
			favoriteProduct: {
				id: toNumber((purchaseSummary.favoriteProduct as any)?.id ?? (purchaseSummary.favorite_product as any)?.id ?? 0) || null,
				name: ((purchaseSummary.favoriteProduct as any)?.name ?? (purchaseSummary.favorite_product as any)?.name ?? null),
			},
			favoriteCategory: {
				id: toNumber((purchaseSummary.favoriteCategory as any)?.id ?? (purchaseSummary.favorite_category as any)?.id ?? 0) || null,
				name: ((purchaseSummary.favoriteCategory as any)?.name ?? (purchaseSummary.favorite_category as any)?.name ?? null),
			},
			frequentlyPurchasedProducts: ((purchaseSummary.frequentlyPurchasedProducts as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				productId: toNumber(item.productId ?? item.product_id),
				productName: (item.productName as string | undefined) ?? (item.product_name as string) ?? "",
				quantity: toNumber(item.quantity),
				revenue: toNumber(item.revenue),
			})),
			recentTransactions: ((purchaseSummary.recentTransactions as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				saleId: toNumber(item.saleId ?? item.sale_id),
				invoiceNumber: (item.invoiceNumber as string | undefined) ?? (item.invoice_number as string) ?? "",
				saleDate: (item.saleDate as string | undefined) ?? (item.sale_date as string) ?? "",
				totalAmount: toNumber(item.totalAmount ?? item.total_amount),
				salesChannel: ((item.salesChannel as any) ?? (item.sales_channel as any) ?? "other"),
				paymentMethod: ((item.paymentMethod as any) ?? (item.payment_method as any) ?? "other"),
			})),
		},
		timeline: ((data.timeline as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			id: toNumber(item.id),
			eventType: (item.eventType as string | undefined) ?? (item.event_type as string) ?? "",
			title: (item.title as string | undefined) ?? "",
			description: (item.description as string | null | undefined) ?? null,
			timestamp: (item.timestamp as string | undefined) ?? (item.created_at as string) ?? "",
		})),
	};
}

function normalizeCustomerAnalytics(data: Record<string, unknown>): CustomerAnalytics {
	const kpis = (data.kpis as Record<string, unknown>) ?? {};
	return {
		kpis: {
			totalCustomers: toNumber(kpis.totalCustomers ?? kpis.total_customers),
			activeCustomers: toNumber(kpis.activeCustomers ?? kpis.active_customers),
			newCustomers: toNumber(kpis.newCustomers ?? kpis.new_customers),
			returningCustomers: toNumber(kpis.returningCustomers ?? kpis.returning_customers),
			averageCustomerSpend: toNumber(kpis.averageCustomerSpend ?? kpis.average_customer_spend),
			totalRevenueGenerated: toNumber(kpis.totalRevenueGenerated ?? kpis.total_revenue_generated),
			averagePurchaseFrequency: toNumber(kpis.averagePurchaseFrequency ?? kpis.average_purchase_frequency),
		},
		customerGrowthTrend: ((data.customerGrowthTrend as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			period: (item.period as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		newVsReturning: ((data.newVsReturning as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		revenueByCustomerType: ((data.revenueByCustomerType as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		topCustomersByRevenue: ((data.topCustomersByRevenue as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			customerId: toNumber(item.customerId ?? item.customer_id),
			customerCode: (item.customerCode as string | undefined) ?? (item.customer_code as string) ?? "",
			customerName: (item.customerName as string | undefined) ?? (item.customer_name as string) ?? "",
			revenue: toNumber(item.revenue),
		})),
		purchaseFrequencyDistribution: ((data.purchaseFrequencyDistribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		locationDistribution: ((data.locationDistribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			city: (item.city as string | undefined) ?? "",
			country: (item.country as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		monthlyCustomerAcquisition: ((data.monthlyCustomerAcquisition as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			period: (item.period as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
		customerSpendingDistribution: ((data.customerSpendingDistribution as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			label: (item.label as string | undefined) ?? "",
			value: toNumber(item.value),
		})),
	};
}

function normalizeCustomerNotification(data: Record<string, unknown>): CustomerNotificationItem {
	return {
		id: toNumber(data.id),
		customerId: data.customerId === null || data.customer_id === null ? null : toNumber(data.customerId ?? data.customer_id),
		customerName: (data.customerName as string | null | undefined) ?? (data.customer_name as string | null | undefined) ?? null,
		notificationType: (data.notificationType as string | undefined) ?? (data.notification_type as string) ?? "",
		message: (data.message as string | undefined) ?? "",
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string) ?? "",
	};
}

export async function listCustomers(params: {
	search?: string;
	customerType?: string;
	segment?: string;
	status?: string;
	city?: string;
	state?: string;
	country?: string;
	registeredFrom?: string;
	registeredTo?: string;
	sortBy?: "name" | "totalSpend" | "totalOrders" | "lastPurchase" | "customerSince";
	sortDirection?: "asc" | "desc";
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<Record<string, unknown>>("/customers", { params });
	return normalizePaginatedResponse(response.data, normalizeCustomer);
}

export async function listCustomerOptions() {
	const response = await apiClient.get<Record<string, unknown>[]>("/customers/options");
	return response.data.map((item) => ({
		id: toNumber(item.id),
		customerId: (item.customerId as string | undefined) ?? (item.customer_code as string) ?? "",
		fullName: (item.fullName as string | undefined) ?? (item.full_name as string) ?? "",
	})) as CustomerOptionItem[];
}

export async function getCustomer(customerId: number) {
	const response = await apiClient.get<Record<string, unknown>>(`/customers/${customerId}`);
	return normalizeCustomer(response.data);
}

export async function createCustomer(payload: CustomerFormValues) {
	const fullName = `${payload.firstName} ${payload.lastName}`.trim();
	const response = await apiClient.post<Record<string, unknown>>("/customers", {
		...payload,
		fullName,
	});
	return normalizeCustomer(response.data);
}

export async function updateCustomer(customerId: number, payload: CustomerFormValues) {
	const fullName = `${payload.firstName} ${payload.lastName}`.trim();
	const response = await apiClient.put<Record<string, unknown>>(`/customers/${customerId}`, {
		...payload,
		fullName,
	});
	return normalizeCustomer(response.data);
}

export async function setCustomerStatus(customerId: number, status: "active" | "inactive") {
	const response = await apiClient.patch<Record<string, unknown>>(`/customers/id/${customerId}/status`, { status });
	return normalizeCustomer(response.data);
}

export async function deleteCustomer(customerId: number) {
	await apiClient.delete(`/customers/${customerId}`);
}

export async function getCustomerProfile(customerId: number) {
	const response = await apiClient.get<Record<string, unknown>>(`/customers/id/${customerId}/profile`);
	return normalizeCustomerProfile(response.data);
}

export async function getCustomerPurchaseHistory(customerId: number) {
	const response = await apiClient.get<Record<string, unknown>>(`/customers/id/${customerId}/purchase-history`);
	return normalizeCustomerProfile({ customer: {}, purchaseSummary: response.data, timeline: [] }).purchaseSummary;
}

export async function getCustomerAnalytics(params?: { startDate?: string; endDate?: string }) {
	const response = await apiClient.get<Record<string, unknown>>("/customers/analytics", { params });
	return normalizeCustomerAnalytics(response.data);
}

export async function listCustomerNotifications(limit = 20) {
	const response = await apiClient.get<Record<string, unknown>[]>("/customers/notifications", { params: { limit } });
	return response.data.map(normalizeCustomerNotification);
}

export async function exportCustomerListCsv() {
	const response = await apiClient.get<Blob>("/customers/exports/list/csv", { responseType: "blob" });
	return response.data;
}

export async function exportCustomerListPdf() {
	const response = await apiClient.get<Blob>("/customers/exports/list/pdf", { responseType: "blob" });
	return response.data;
}

export async function exportCustomerAnalyticsCsv(params?: { startDate?: string; endDate?: string }) {
	const response = await apiClient.get<Blob>("/customers/exports/analytics/csv", { params, responseType: "blob" });
	return response.data;
}

export async function exportCustomerAnalyticsPdf(params?: { startDate?: string; endDate?: string }) {
	const response = await apiClient.get<Blob>("/customers/exports/analytics/pdf", { params, responseType: "blob" });
	return response.data;
}

export async function exportTopCustomersCsv(params?: { startDate?: string; endDate?: string }) {
	const response = await apiClient.get<Blob>("/customers/exports/top-customers/csv", { params, responseType: "blob" });
	return response.data;
}

export async function exportTopCustomersPdf(params?: { startDate?: string; endDate?: string }) {
	const response = await apiClient.get<Blob>("/customers/exports/top-customers/pdf", { params, responseType: "blob" });
	return response.data;
}

function normalizeForecastProduct(data: Record<string, unknown>): ForecastProductRow {
	return {
		forecastId: toNumber(data.forecastId ?? data.forecast_id),
		productId: toNumber(data.productId ?? data.product_id),
		productName: (data.productName as string | undefined) ?? (data.product_name as string) ?? "",
		categoryId: toNumber(data.categoryId ?? data.category_id),
		categoryName: (data.categoryName as string | undefined) ?? (data.category_name as string) ?? "",
		brand: (data.brand as string | null | undefined) ?? null,
		currentStock: toNumber(data.currentStock ?? data.current_stock),
		historicalSales: toNumber(data.historicalSales ?? data.historical_sales),
		predictedDemand: toNumber(data.predictedDemand ?? data.predicted_demand),
		forecastPeriod: ((data.forecastPeriod as ForecastPeriod | undefined) ?? (data.forecast_period as ForecastPeriod) ?? "next-30-days") as ForecastPeriod,
		forecastStartDate: (data.forecastStartDate as string | undefined) ?? (data.forecast_start_date as string) ?? "",
		forecastEndDate: (data.forecastEndDate as string | undefined) ?? (data.forecast_end_date as string) ?? "",
		confidenceLevel: toNumber(data.confidenceLevel ?? data.confidence_level),
		accuracy: data.accuracy === null || data.accuracy === undefined ? null : toNumber(data.accuracy),
		growthPercentage: toNumber(data.growthPercentage ?? data.growth_percentage),
		recommendationType: (data.recommendationType as ForecastProductRow["recommendationType"] | undefined) ??
			(data.recommendation_type as ForecastProductRow["recommendationType"]) ??
			"stock-level-healthy",
	};
}

function normalizeForecastDashboard(data: Record<string, unknown>): ForecastDashboard {
	const analytics = (data.analytics as Record<string, unknown> | undefined) ?? {};
	const kpis = (analytics.kpis as Record<string, unknown> | undefined) ?? {};
	return {
		generatedAt: (data.generatedAt as string | undefined) ?? (data.generated_at as string) ?? "",
		forecastPeriod: ((data.forecastPeriod as ForecastPeriod | undefined) ?? (data.forecast_period as ForecastPeriod) ?? "next-30-days") as ForecastPeriod,
		forecastStartDate: (data.forecastStartDate as string | undefined) ?? (data.forecast_start_date as string) ?? "",
		forecastEndDate: (data.forecastEndDate as string | undefined) ?? (data.forecast_end_date as string) ?? "",
		products: ((data.products as Record<string, unknown>[] | undefined) ?? []).map(normalizeForecastProduct),
		categories: ((data.categories as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			categoryId: toNumber(item.categoryId ?? item.category_id),
			categoryName: (item.categoryName as string | undefined) ?? (item.category_name as string) ?? "",
			totalHistoricalSales: toNumber(item.totalHistoricalSales ?? item.total_historical_sales),
			predictedDemand: toNumber(item.predictedDemand ?? item.predicted_demand),
			expectedGrowthPercentage: toNumber(item.expectedGrowthPercentage ?? item.expected_growth_percentage),
		})),
		analytics: {
			kpis: {
				totalPredictedDemand: toNumber(kpis.totalPredictedDemand ?? kpis.total_predicted_demand),
				productsExpectedToRunOut: toNumber(kpis.productsExpectedToRunOut ?? kpis.products_expected_to_run_out),
				highGrowthProducts: toNumber(kpis.highGrowthProducts ?? kpis.high_growth_products),
				slowMovingProducts: toNumber(kpis.slowMovingProducts ?? kpis.slow_moving_products),
				forecastAccuracy: toNumber(kpis.forecastAccuracy ?? kpis.forecast_accuracy),
			},
			historicalVsForecast: ((analytics.historicalVsForecast as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				label: (item.label as string | undefined) ?? "",
				historical: toNumber(item.historical),
				forecast: toNumber(item.forecast),
			})),
			productDemandTrend: ((analytics.productDemandTrend as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				label: (item.label as string | undefined) ?? "",
				predictedDemand: toNumber(item.predictedDemand ?? item.predicted_demand),
				historicalSales: toNumber(item.historicalSales ?? item.historical_sales),
				growthPercentage: toNumber(item.growthPercentage ?? item.growth_percentage),
			})),
			categoryDemandTrend: ((analytics.categoryDemandTrend as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				label: (item.label as string | undefined) ?? "",
				predictedDemand: toNumber(item.predictedDemand ?? item.predicted_demand),
				historicalSales: toNumber(item.historicalSales ?? item.historical_sales),
			})),
			topPredictedProducts: ((analytics.topPredictedProducts as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				productId: toNumber(item.productId ?? item.product_id),
				productName: (item.productName as string | undefined) ?? (item.product_name as string) ?? "",
				predictedDemand: toNumber(item.predictedDemand ?? item.predicted_demand),
				confidenceLevel: toNumber(item.confidenceLevel ?? item.confidence_level),
			})),
			seasonalSalesPattern: ((analytics.seasonalSalesPattern as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
				period: (item.period as string | undefined) ?? "",
				value: toNumber(item.value),
			})),
		},
		recommendations: ((data.recommendations as Record<string, unknown>[] | undefined) ?? []).map((item) => ({
			forecastId: toNumber(item.forecastId ?? item.forecast_id),
			productId: toNumber(item.productId ?? item.product_id),
			productName: (item.productName as string | undefined) ?? (item.product_name as string) ?? "",
			recommendationType: (item.recommendationType as any) ?? (item.recommendation_type as any) ?? "stock-level-healthy",
			reason: (item.reason as string | undefined) ?? "",
			currentStock: toNumber(item.currentStock ?? item.current_stock),
			reorderLevel: toNumber(item.reorderLevel ?? item.reorder_level),
			predictedDemand: toNumber(item.predictedDemand ?? item.predicted_demand),
		})),
	};
}

function normalizeForecastNotification(data: Record<string, unknown>): ForecastNotificationItem {
	return {
		id: toNumber(data.id),
		forecastId: data.forecastId === null || data.forecast_id === null ? null : toNumber(data.forecastId ?? data.forecast_id),
		productId: data.productId === null || data.product_id === null ? null : toNumber(data.productId ?? data.product_id),
		productName: (data.productName as string | null | undefined) ?? (data.product_name as string | null | undefined) ?? null,
		notificationType: (data.notificationType as string | undefined) ?? (data.notification_type as string) ?? "",
		message: (data.message as string | undefined) ?? "",
		createdAt: (data.createdAt as string | undefined) ?? (data.created_at as string) ?? "",
	};
}

type ForecastParams = {
	forecastPeriod: ForecastPeriod;
	customStartDate?: string;
	customEndDate?: string;
};

export async function getForecastFilters() {
	const response = await apiClient.get<Record<string, unknown>>("/forecasts/filters");
	return {
		products: ((response.data.products as Record<string, unknown>[] | undefined) ?? []).map((item) => ({ id: toNumber(item.id), name: (item.name as string | undefined) ?? "" })),
		categories: ((response.data.categories as Record<string, unknown>[] | undefined) ?? []).map((item) => ({ id: toNumber(item.id), name: (item.name as string | undefined) ?? "" })),
		brands: ((response.data.brands as string[] | undefined) ?? []).filter(Boolean),
	} as ForecastFilterOptions;
}

export async function generateForecasts(payload: ForecastParams & { forceRefresh?: boolean }) {
	const response = await apiClient.post<Record<string, unknown>>("/forecasts/generate", payload);
	return normalizeForecastDashboard(response.data);
}

export async function getForecastDashboard(params: ForecastParams) {
	const response = await apiClient.get<Record<string, unknown>>("/forecasts/dashboard", { params });
	return normalizeForecastDashboard(response.data);
}

export async function listForecastProducts(params: ForecastParams & {
	productId?: number;
	categoryId?: number;
	brand?: string;
	search?: string;
	sortBy?: ForecastSortBy;
	sortDirection?: ForecastSortDirection;
	page?: number;
	pageSize?: number;
}) {
	const response = await apiClient.get<Record<string, unknown>>("/forecasts/products", { params });
	return normalizePaginatedResponse(response.data, normalizeForecastProduct);
}

export async function listForecastNotifications(limit = 20) {
	const response = await apiClient.get<Record<string, unknown>[]>("/forecasts/notifications", { params: { limit } });
	return response.data.map(normalizeForecastNotification);
}

export async function exportDemandForecastCsv(params: ForecastParams) {
	const response = await apiClient.get<Blob>("/forecasts/exports/demand-report/csv", { params, responseType: "blob" });
	return response.data;
}

export async function exportProductForecastPdf(params: ForecastParams) {
	const response = await apiClient.get<Blob>("/forecasts/exports/product-report/pdf", { params, responseType: "blob" });
	return response.data;
}

export async function exportCategoryForecastCsv(params: ForecastParams) {
	const response = await apiClient.get<Blob>("/forecasts/exports/category-report/csv", { params, responseType: "blob" });
	return response.data;
}