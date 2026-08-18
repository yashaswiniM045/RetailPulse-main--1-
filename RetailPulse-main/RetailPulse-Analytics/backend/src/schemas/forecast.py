from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.models.forecast import ForecastPeriod, InventoryRecommendationType


ForecastSortBy = Literal["highestPredictedDemand", "lowestStock", "highestGrowth", "forecastAccuracy"]
ForecastSortDirection = Literal["asc", "desc"]


class ForecastGenerateRequest(BaseModel):
    forecast_period: ForecastPeriod = Field(alias="forecastPeriod")
    custom_start_date: date | None = Field(default=None, alias="customStartDate")
    custom_end_date: date | None = Field(default=None, alias="customEndDate")
    force_refresh: bool = Field(default=False, alias="forceRefresh")

    @model_validator(mode="after")
    def validate_custom_dates(self):
        if self.forecast_period == ForecastPeriod.CUSTOM:
            if self.custom_start_date is None or self.custom_end_date is None:
                raise ValueError("Custom forecast requires customStartDate and customEndDate")
            if self.custom_end_date < self.custom_start_date:
                raise ValueError("customEndDate cannot be before customStartDate")
        return self


class ForecastFilterRead(BaseModel):
    products: list[dict]
    categories: list[dict]
    brands: list[str]


class ForecastProductRowRead(BaseModel):
    forecast_id: int = Field(alias="forecastId")
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    brand: str | None
    current_stock: int = Field(alias="currentStock")
    historical_sales: float = Field(alias="historicalSales")
    predicted_demand: float = Field(alias="predictedDemand")
    forecast_period: ForecastPeriod = Field(alias="forecastPeriod")
    forecast_start_date: date = Field(alias="forecastStartDate")
    forecast_end_date: date = Field(alias="forecastEndDate")
    confidence_level: float = Field(alias="confidenceLevel")
    accuracy: float | None
    growth_percentage: float = Field(alias="growthPercentage")
    recommendation_type: InventoryRecommendationType = Field(alias="recommendationType")


class ForecastCategoryRowRead(BaseModel):
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    total_historical_sales: float = Field(alias="totalHistoricalSales")
    predicted_demand: float = Field(alias="predictedDemand")
    expected_growth_percentage: float = Field(alias="expectedGrowthPercentage")


class ForecastRecommendationRead(BaseModel):
    forecast_id: int = Field(alias="forecastId")
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    recommendation_type: InventoryRecommendationType = Field(alias="recommendationType")
    reason: str
    current_stock: int = Field(alias="currentStock")
    reorder_level: int = Field(alias="reorderLevel")
    predicted_demand: float = Field(alias="predictedDemand")


class ForecastKpisRead(BaseModel):
    total_predicted_demand: float = Field(alias="totalPredictedDemand")
    products_expected_to_run_out: int = Field(alias="productsExpectedToRunOut")
    high_growth_products: int = Field(alias="highGrowthProducts")
    slow_moving_products: int = Field(alias="slowMovingProducts")
    forecast_accuracy: float = Field(alias="forecastAccuracy")


class ForecastAnalyticsRead(BaseModel):
    kpis: ForecastKpisRead
    historical_vs_forecast: list[dict] = Field(alias="historicalVsForecast")
    product_demand_trend: list[dict] = Field(alias="productDemandTrend")
    category_demand_trend: list[dict] = Field(alias="categoryDemandTrend")
    top_predicted_products: list[dict] = Field(alias="topPredictedProducts")
    seasonal_sales_pattern: list[dict] = Field(alias="seasonalSalesPattern")


class ForecastNotificationRead(BaseModel):
    id: int
    forecast_id: int | None = Field(alias="forecastId")
    product_id: int | None = Field(alias="productId")
    product_name: str | None = Field(alias="productName")
    notification_type: str = Field(alias="notificationType")
    message: str
    created_at: datetime = Field(alias="createdAt")


class ForecastDashboardRead(BaseModel):
    generated_at: datetime = Field(alias="generatedAt")
    forecast_period: ForecastPeriod = Field(alias="forecastPeriod")
    forecast_start_date: date = Field(alias="forecastStartDate")
    forecast_end_date: date = Field(alias="forecastEndDate")
    products: list[ForecastProductRowRead]
    categories: list[ForecastCategoryRowRead]
    analytics: ForecastAnalyticsRead
    recommendations: list[ForecastRecommendationRead]


class ForecastListRead(BaseModel):
    items: list[ForecastProductRowRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
