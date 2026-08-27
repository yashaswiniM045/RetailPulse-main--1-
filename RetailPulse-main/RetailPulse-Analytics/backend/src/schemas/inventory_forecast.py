from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


InventoryForecastRisk = Literal["out-of-stock", "stockout-risk", "low-stock", "healthy", "overstock"]
InventoryForecastSort = Literal["currentStock", "forecastedDemand", "daysRemaining", "recommendedQuantity", "risk"]


class InventoryForecastRowRead(BaseModel):
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    sku: str
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    supplier: str | None
    current_stock: int = Field(alias="currentStock")
    average_daily_sales: float = Field(alias="averageDailySales")
    forecasted_demand: float = Field(alias="forecastedDemand")
    days_of_stock_remaining: float | None = Field(alias="daysOfStockRemaining")
    lead_time_days: int = Field(alias="leadTimeDays")
    safety_stock: int = Field(alias="safetyStock")
    reorder_point: int = Field(alias="reorderPoint")
    recommended_reorder_quantity: int = Field(alias="recommendedReorderQuantity")
    stock_risk: InventoryForecastRisk = Field(alias="stockRisk")
    recommendation: str
    reorder_required: bool = Field(alias="reorderRequired")
    historical_demand: list[dict] = Field(default_factory=list, alias="historicalDemand")
    forecast_start_date: date = Field(alias="forecastStartDate")
    forecast_end_date: date = Field(alias="forecastEndDate")


class InventoryForecastSummaryRead(BaseModel):
    products_requiring_reorder: int = Field(alias="productsRequiringReorder")
    products_at_stockout_risk: int = Field(alias="productsAtStockoutRisk")
    overstocked_products: int = Field(alias="overstockedProducts")
    healthy_products: int = Field(alias="healthyProducts")


class InventoryForecastRead(BaseModel):
    items: list[InventoryForecastRowRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
    summary: InventoryForecastSummaryRead
    generated_at: date = Field(alias="generatedAt")
    historical_window_days: int = Field(alias="historicalWindowDays")
    forecast_horizon_days: int = Field(alias="forecastHorizonDays")
