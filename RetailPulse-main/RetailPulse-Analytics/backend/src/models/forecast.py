import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ForecastPeriod(str, enum.Enum):
    NEXT_7_DAYS = "next-7-days"
    NEXT_30_DAYS = "next-30-days"
    NEXT_90_DAYS = "next-90-days"
    CUSTOM = "custom"


class InventoryRecommendationType(str, enum.Enum):
    REORDER_SOON = "reorder-soon"
    OVERSTOCK_RISK = "overstock-risk"
    STOCK_LEVEL_HEALTHY = "stock-level-healthy"
    IMMEDIATE_RESTOCK_REQUIRED = "immediate-restock-required"


class ForecastNotificationType(str, enum.Enum):
    RUN_OUT_RISK = "run-out-risk"
    DEMAND_EXCEEDS_STOCK = "demand-exceeds-stock"
    SIGNIFICANT_GROWTH = "significant-growth"


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "product_id",
            "forecast_period",
            "forecast_start_date",
            "forecast_end_date",
            "generated_at",
            name="uq_demand_forecasts_company_product_generation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    forecast_period: Mapped[ForecastPeriod] = mapped_column(Enum(ForecastPeriod), nullable=False, index=True)
    forecast_start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    forecast_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted_demand: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    growth_rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    recommendation_type: Mapped[InventoryRecommendationType] = mapped_column(
        Enum(InventoryRecommendationType),
        nullable=False,
        default=InventoryRecommendationType.STOCK_LEVEL_HEALTHY,
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    company = relationship("Company", back_populates="demand_forecasts")
    product = relationship("Product")
    category = relationship("Category")
    history_entries = relationship("ForecastHistory", back_populates="forecast", cascade="all, delete-orphan")


class ForecastHistory(Base):
    __tablename__ = "forecast_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("demand_forecasts.id"), nullable=False, index=True)
    historical_sales: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    prediction: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    forecast = relationship("DemandForecast", back_populates="history_entries")


class ForecastNotification(Base):
    __tablename__ = "forecast_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    forecast_id: Mapped[int | None] = mapped_column(ForeignKey("demand_forecasts.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    notification_type: Mapped[ForecastNotificationType] = mapped_column(Enum(ForecastNotificationType), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company", back_populates="forecast_notifications")
    product = relationship("Product")
    forecast = relationship("DemandForecast")
