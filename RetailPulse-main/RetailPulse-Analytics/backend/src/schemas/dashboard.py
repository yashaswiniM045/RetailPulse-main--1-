from datetime import datetime

from pydantic import BaseModel, Field

from src.models.inventory import StockStatus
from src.models.sale import PaymentMethod, SalesChannel


class DashboardSummaryRead(BaseModel):
    total_products: int = Field(alias="totalProducts")
    active_products: int = Field(alias="activeProducts")
    inactive_products: int = Field(alias="inactiveProducts")
    total_categories: int = Field(alias="totalCategories")
    total_sales: int = Field(alias="totalSales")
    total_revenue: float = Field(alias="totalRevenue")
    total_orders: int = Field(alias="totalOrders")
    average_order_value: float = Field(alias="averageOrderValue")


class DashboardKpisRead(BaseModel):
    total_revenue: float = Field(alias="totalRevenue")
    total_orders: int = Field(alias="totalOrders")
    total_products_sold: int = Field(alias="totalProductsSold")
    average_order_value: float = Field(alias="averageOrderValue")
    total_discount: float = Field(alias="totalDiscount")
    total_tax: float = Field(alias="totalTax")
    total_inventory_value: float = Field(alias="totalInventoryValue")
    low_stock_products: int = Field(alias="lowStockProducts")
    out_of_stock_products: int = Field(alias="outOfStockProducts")
    total_categories: int = Field(alias="totalCategories")


class DashboardTrendPointRead(BaseModel):
    period: str
    revenue: float
    orders: int
    products_sold: int = Field(alias="productsSold")


class DashboardKeyValueRead(BaseModel):
    label: str
    value: float
    transactions: int | None = None


class DashboardTopProductRead(BaseModel):
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    quantity_sold: int = Field(alias="quantitySold")
    revenue: float


class DashboardCategoryPerformanceRead(BaseModel):
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    orders: int
    products_sold: int = Field(alias="productsSold")
    revenue: float


class DashboardInventoryDistributionRead(BaseModel):
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    quantity: int
    product_count: int = Field(alias="productCount")


class DashboardInventoryValueByCategoryRead(BaseModel):
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    inventory_value: float = Field(alias="inventoryValue")


class DashboardInventoryProductRead(BaseModel):
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    sku: str
    category_name: str = Field(alias="categoryName")
    brand: str | None
    current_stock: int = Field(alias="currentStock")
    reorder_level: int = Field(alias="reorderLevel")
    stock_status: StockStatus = Field(alias="stockStatus")


class DashboardFiltersRead(BaseModel):
    products: list[dict]
    categories: list[dict]
    brands: list[str]
    sales_channels: list[SalesChannel] = Field(alias="salesChannels")
    payment_methods: list[PaymentMethod] = Field(alias="paymentMethods")


class DashboardSalesTransactionRead(BaseModel):
    sale_id: int = Field(alias="saleId")
    invoice_number: str = Field(alias="invoiceNumber")
    sale_date: datetime = Field(alias="saleDate")
    customer_name: str = Field(alias="customerName")
    sales_channel: SalesChannel = Field(alias="salesChannel")
    payment_method: PaymentMethod = Field(alias="paymentMethod")
    quantity: int
    total: float


class DashboardDrilldownCategoryProductRead(BaseModel):
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    sku: str
    brand: str | None
    current_stock: int = Field(alias="currentStock")
    stock_status: StockStatus = Field(alias="stockStatus")
    quantity_sold: int = Field(alias="quantitySold")
    revenue: float


class DashboardDrilldownKpiRecordRead(BaseModel):
    id: str
    label: str
    secondary: str | None = None
    value: float


class DashboardPaginatedRead(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


class DashboardAnalyticsRead(BaseModel):
    kpis: DashboardKpisRead
    revenue_trend: list[DashboardTrendPointRead] = Field(alias="revenueTrend")
    sales_trend: list[DashboardTrendPointRead] = Field(alias="salesTrend")
    top_products: list[DashboardTopProductRead] = Field(alias="topProducts")
    top_categories: list[DashboardCategoryPerformanceRead] = Field(alias="topCategories")
    payment_method_distribution: list[DashboardKeyValueRead] = Field(alias="paymentMethodDistribution")
    sales_channel_distribution: list[DashboardKeyValueRead] = Field(alias="salesChannelDistribution")
    inventory_distribution_by_category: list[DashboardInventoryDistributionRead] = Field(alias="inventoryDistributionByCategory")
    stock_status_summary: list[DashboardKeyValueRead] = Field(alias="stockStatusSummary")
    top_low_stock_products: list[DashboardInventoryProductRead] = Field(alias="topLowStockProducts")
    out_of_stock_products: list[DashboardInventoryProductRead] = Field(alias="outOfStockProducts")
    inventory_value_by_category: list[DashboardInventoryValueByCategoryRead] = Field(alias="inventoryValueByCategory")
    top_customers: list[dict] = Field(alias="topCustomers")
    recent_customers: list[dict] = Field(alias="recentCustomers")
    customer_growth: list[dict] = Field(alias="customerGrowth")
    customer_revenue_contribution: list[dict] = Field(alias="customerRevenueContribution")
    last_updated_at: datetime | None = Field(alias="lastUpdatedAt")