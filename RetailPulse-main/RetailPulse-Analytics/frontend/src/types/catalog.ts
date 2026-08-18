export type CatalogStatus = "active" | "inactive";
export type SalesChannel = "in-store" | "online" | "wholesale" | "marketplace" | "other";
export type PaymentMethod = "cash" | "card" | "bank-transfer" | "upi" | "wallet" | "other";
export type PaymentStatus = "pending" | "paid" | "failed" | "refunded";

export interface CategorySummary {
	id: number;
	name: string;
	status: CatalogStatus;
}

export interface CategoryItem extends CategorySummary {
	description: string | null;
	productCount: number;
	createdAt: string;
	updatedAt: string;
}

export interface CategoryFormValues {
	categoryName: string;
	description: string;
	status: CatalogStatus;
}

export interface PaginatedResult<T> {
	items: T[];
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
}

export interface ProductItem {
	id: number;
	name: string;
	sku: string;
	category: CategorySummary;
	brand: string | null;
	description: string | null;
	unitPrice: number;
	costPrice: number;
	stockQuantity: number;
	isOutOfStock: boolean;
	unitOfMeasure: string;
	status: CatalogStatus;
	createdAt: string;
	updatedAt: string;
}

export interface ProductFormValues {
	productName: string;
	sku: string;
	categoryId: number;
	brand: string;
	description: string;
	unitPrice: number;
	costPrice: number;
	stockQuantity: number;
	unitOfMeasure: string;
	status: CatalogStatus;
}

export interface DashboardSummary {
	totalProducts: number;
	activeProducts: number;
	inactiveProducts: number;
	totalCategories: number;
	totalSales: number;
	totalRevenue: number;
	totalOrders: number;
	averageOrderValue: number;
}

export type DashboardDateGrain = "daily" | "weekly" | "monthly";

export interface DashboardKpis {
	totalRevenue: number;
	totalOrders: number;
	totalProductsSold: number;
	averageOrderValue: number;
	totalDiscount: number;
	totalTax: number;
	totalInventoryValue: number;
	lowStockProducts: number;
	outOfStockProducts: number;
	totalCategories: number;
}

export interface DashboardTrendPoint {
	period: string;
	revenue: number;
	orders: number;
	productsSold: number;
}

export interface DashboardTopProduct {
	productId: number;
	productName: string;
	quantitySold: number;
	revenue: number;
}

export interface DashboardTopCategory {
	categoryId: number;
	categoryName: string;
	orders: number;
	productsSold: number;
	revenue: number;
}

export interface DashboardKeyValue {
	label: string;
	value: number;
	transactions?: number;
}

export interface DashboardInventoryDistribution {
	categoryId: number;
	categoryName: string;
	quantity: number;
	productCount: number;
}

export interface DashboardInventoryProduct {
	productId: number;
	productName: string;
	sku: string;
	categoryName: string;
	brand: string | null;
	currentStock: number;
	reorderLevel: number;
	stockStatus: InventoryStockStatus;
	quantitySold?: number;
	revenue?: number;
}

export interface DashboardInventoryValueByCategory {
	categoryId: number;
	categoryName: string;
	inventoryValue: number;
}

export interface DashboardAnalytics {
	kpis: DashboardKpis;
	revenueTrend: DashboardTrendPoint[];
	salesTrend: DashboardTrendPoint[];
	topProducts: DashboardTopProduct[];
	topCategories: DashboardTopCategory[];
	paymentMethodDistribution: DashboardKeyValue[];
	salesChannelDistribution: DashboardKeyValue[];
	inventoryDistributionByCategory: DashboardInventoryDistribution[];
	stockStatusSummary: DashboardKeyValue[];
	topLowStockProducts: DashboardInventoryProduct[];
	outOfStockProducts: DashboardInventoryProduct[];
	inventoryValueByCategory: DashboardInventoryValueByCategory[];
	topCustomers: Array<{ customerId: number; customerName: string; revenue: number; orders: number; averageOrderValue: number }>;
	recentCustomers: Array<{ customerId: number; customerCode: string; customerName: string; customerSince: string }>;
	customerGrowth: Array<{ period: string; value: number }>;
	customerRevenueContribution: Array<{ customerId: number; customerName: string; contributionPercent: number }>;
	lastUpdatedAt: string | null;
}

export interface DashboardFilterOption {
	id: number;
	name: string;
}

export interface DashboardFilters {
	products: DashboardFilterOption[];
	categories: DashboardFilterOption[];
	brands: string[];
	salesChannels: SalesChannel[];
	paymentMethods: PaymentMethod[];
}

export interface DashboardQueryFilters {
	dateGrain?: DashboardDateGrain;
	startDate?: string;
	endDate?: string;
	productId?: number;
	categoryId?: number;
	brand?: string;
	salesChannel?: SalesChannel;
	paymentMethod?: PaymentMethod;
}

export interface DashboardDrilldownKpiRecord {
	id: string;
	label: string;
	secondary: string | null;
	value: number;
}

export interface DashboardProductTransaction {
	saleId: number;
	invoiceNumber: string;
	saleDate: string;
	customerName: string;
	salesChannel: SalesChannel;
	paymentMethod: PaymentMethod;
	quantity: number;
	total: number;
}

export interface SaleItem {
	id: number;
	productId: number;
	productName: string;
	sku: string;
	categoryId: number;
	categoryName: string;
	quantity: number;
	unitPrice: number;
	discount: number;
	tax: number;
	total: number;
	remainingStock: number;
}

export interface SaleNotification {
	type: "low-stock" | "out-of-stock";
	message: string;
}

export interface SaleItemFormValues {
	productId: number;
	quantity: number;
	unitPrice: number;
	discount: number;
	tax: number;
}

export interface SaleFormValues {
	customerId?: number;
	saleDate: string;
	customerName: string;
	salesChannel: SalesChannel;
	paymentMethod: PaymentMethod;
	paymentStatus: PaymentStatus;
	notes?: string;
	items: SaleItemFormValues[];
}

export interface SaleItemDetails extends SaleItem {
	categoryName: string;
	productName: string;
}

export interface SaleRecord {
	id: number;
	customerId?: number | null;
	invoiceNumber: string;
	customerName: string;
	saleDate: string;
	salesChannel: SalesChannel;
	paymentMethod: PaymentMethod;
	paymentStatus: PaymentStatus;
	notes: string | null;
	subtotal: number;
	discountTotal: number;
	taxTotal: number;
	totalAmount: number;
	createdBy: number;
	createdByName: string;
	createdAt: string;
	updatedAt: string;
	items: SaleItemDetails[];
	notifications: SaleNotification[];
}

export interface SaleListItem {
	id: number;
	customerId?: number | null;
	invoiceNumber: string;
	customerName: string;
	saleDate: string;
	salesChannel: SalesChannel;
	paymentMethod: PaymentMethod;
	paymentStatus: PaymentStatus;
	totalAmount: number;
	createdByName: string;
	itemCount: number;
}

export type InventoryStockStatus = "in-stock" | "low-stock" | "out-of-stock";
export type InventoryMovementType = "sale" | "manual-adjustment" | "stock-addition" | "stock-removal";
export type InventoryAdjustmentType = "stock-addition" | "stock-removal" | "manual-adjustment";

export interface InventoryItem {
	id: number;
	productId: number;
	productName: string;
	sku: string;
	category: string;
	brand: string | null;
	currentStock: number;
	reservedStock: number;
	availableStock: number;
	reorderLevel: number;
	stockStatus: InventoryStockStatus;
	updatedAt: string;
}

export interface InventoryMovementItem {
	id: number;
	inventoryId: number;
	productId: number;
	productName: string;
	sku: string;
	movementType: InventoryMovementType;
	previousQuantity: number;
	updatedQuantity: number;
	quantityChanged: number;
	reason: string;
	remarks: string | null;
	performedBy: string | null;
	createdAt: string;
}

export interface InventoryAdjustmentPayload {
	productId: number;
	adjustmentType: InventoryAdjustmentType;
	quantity?: number;
	targetQuantity?: number;
	reason: string;
	remarks?: string;
}

export interface InventoryReorderLevelPayload {
	reorderLevel: number;
	reason: string;
}

export interface InventoryCategoryBreakdown {
	category: string;
	totalQuantity: number;
	productCount: number;
}

export interface InventoryStatusBreakdown {
	status: InventoryStockStatus;
	count: number;
}

export interface InventoryDashboardSummary {
	totalProducts: number;
	totalInventoryQuantity: number;
	lowStockProducts: number;
	outOfStockProducts: number;
	inventoryByCategory: InventoryCategoryBreakdown[];
	stockStatusDistribution: InventoryStatusBreakdown[];
}

export interface InventoryNotificationItem {
	id: number;
	productId: number | null;
	productName: string | null;
	notificationType: "low-stock" | "out-of-stock" | "stock-adjusted";
	message: string;
	createdAt: string;
}

export type CustomerType = "retail" | "wholesale" | "corporate";
export type CustomerGender = "male" | "female" | "other" | "prefer-not-to-say";
export type CustomerStatus = "active" | "inactive";
export type CustomerSegment = "new" | "regular" | "loyal" | "vip";

export interface CustomerItem {
	id: number;
	customerId: string;
	fullName: string;
	firstName: string;
	lastName: string;
	email: string;
	phoneNumber: string;
	dateOfBirth: string | null;
	gender: CustomerGender | null;
	addressLine1: string | null;
	addressLine2: string | null;
	city: string | null;
	state: string | null;
	country: string | null;
	postalCode: string | null;
	customerType: CustomerType;
	preferredSalesChannel: SalesChannel | null;
	status: CustomerStatus;
	segment: CustomerSegment;
	totalPurchases: number;
	totalSpend: number;
	lastPurchaseDate: string | null;
	customerSince: string;
	updatedAt: string;
}

export interface CustomerFormValues {
	firstName: string;
	lastName: string;
	fullName: string;
	email: string;
	phoneNumber: string;
	dateOfBirth?: string;
	gender?: CustomerGender;
	addressLine1: string;
	addressLine2: string;
	city: string;
	state: string;
	country: string;
	postalCode: string;
	customerType: CustomerType;
	preferredSalesChannel?: SalesChannel;
	status: CustomerStatus;
}

export interface CustomerOptionItem {
	id: number;
	customerId: string;
	fullName: string;
}

export interface CustomerPurchaseSummary {
	totalOrders: number;
	totalRevenue: number;
	quantityPurchased: number;
	averageOrderValue: number;
	firstPurchaseDate: string | null;
	lastPurchaseDate: string | null;
	purchaseFrequencyDays: number;
	favoriteProduct: { id: number | null; name: string | null };
	favoriteCategory: { id: number | null; name: string | null };
	frequentlyPurchasedProducts: Array<{
		productId: number;
		productName: string;
		quantity: number;
		revenue: number;
	}>;
	recentTransactions: Array<{
		saleId: number;
		invoiceNumber: string;
		saleDate: string;
		totalAmount: number;
		salesChannel: SalesChannel;
		paymentMethod: PaymentMethod;
	}>;
}

export interface CustomerTimelineItem {
	id: number;
	eventType: string;
	title: string;
	description: string | null;
	timestamp: string;
}

export interface CustomerProfile {
	customer: CustomerItem;
	purchaseSummary: CustomerPurchaseSummary;
	timeline: CustomerTimelineItem[];
}

export interface CustomerAnalytics {
	kpis: {
		totalCustomers: number;
		activeCustomers: number;
		newCustomers: number;
		returningCustomers: number;
		averageCustomerSpend: number;
		totalRevenueGenerated: number;
		averagePurchaseFrequency: number;
	};
	customerGrowthTrend: Array<{ period: string; value: number }>;
	newVsReturning: Array<{ label: string; value: number }>;
	revenueByCustomerType: Array<{ label: string; value: number }>;
	topCustomersByRevenue: Array<{
		customerId: number;
		customerCode: string;
		customerName: string;
		revenue: number;
	}>;
	purchaseFrequencyDistribution: Array<{ label: string; value: number }>;
	locationDistribution: Array<{ city: string; country: string; value: number }>;
	monthlyCustomerAcquisition: Array<{ period: string; value: number }>;
	customerSpendingDistribution: Array<{ label: string; value: number }>;
}

export interface CustomerNotificationItem {
	id: number;
	customerId: number | null;
	customerName: string | null;
	notificationType: string;
	message: string;
	createdAt: string;
}

export type ForecastPeriod = "next-7-days" | "next-30-days" | "next-90-days" | "custom";
export type ForecastRecommendationType =
	| "reorder-soon"
	| "overstock-risk"
	| "stock-level-healthy"
	| "immediate-restock-required";
export type ForecastSortBy = "highestPredictedDemand" | "lowestStock" | "highestGrowth" | "forecastAccuracy";
export type ForecastSortDirection = "asc" | "desc";

export interface ForecastFilterOptions {
	products: Array<{ id: number; name: string }>;
	categories: Array<{ id: number; name: string }>;
	brands: string[];
}

export interface ForecastProductRow {
	forecastId: number;
	productId: number;
	productName: string;
	categoryId: number;
	categoryName: string;
	brand: string | null;
	currentStock: number;
	historicalSales: number;
	predictedDemand: number;
	forecastPeriod: ForecastPeriod;
	forecastStartDate: string;
	forecastEndDate: string;
	confidenceLevel: number;
	accuracy: number | null;
	growthPercentage: number;
	recommendationType: ForecastRecommendationType;
}

export interface ForecastCategoryRow {
	categoryId: number;
	categoryName: string;
	totalHistoricalSales: number;
	predictedDemand: number;
	expectedGrowthPercentage: number;
}

export interface ForecastRecommendation {
	forecastId: number;
	productId: number;
	productName: string;
	recommendationType: ForecastRecommendationType;
	reason: string;
	currentStock: number;
	reorderLevel: number;
	predictedDemand: number;
}

export interface ForecastAnalytics {
	kpis: {
		totalPredictedDemand: number;
		productsExpectedToRunOut: number;
		highGrowthProducts: number;
		slowMovingProducts: number;
		forecastAccuracy: number;
	};
	historicalVsForecast: Array<{ label: string; historical: number; forecast: number }>;
	productDemandTrend: Array<{ label: string; predictedDemand: number; historicalSales: number; growthPercentage: number }>;
	categoryDemandTrend: Array<{ label: string; predictedDemand: number; historicalSales: number }>;
	topPredictedProducts: Array<{ productId: number; productName: string; predictedDemand: number; confidenceLevel: number }>;
	seasonalSalesPattern: Array<{ period: string; value: number }>;
}

export interface ForecastDashboard {
	generatedAt: string;
	forecastPeriod: ForecastPeriod;
	forecastStartDate: string;
	forecastEndDate: string;
	products: ForecastProductRow[];
	categories: ForecastCategoryRow[];
	analytics: ForecastAnalytics;
	recommendations: ForecastRecommendation[];
}

export interface ForecastNotificationItem {
	id: number;
	forecastId: number | null;
	productId: number | null;
	productName: string | null;
	notificationType: string;
	message: string;
	createdAt: string;
}