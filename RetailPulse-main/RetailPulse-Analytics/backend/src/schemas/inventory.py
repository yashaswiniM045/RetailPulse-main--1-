from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.inventory import InventoryMovementType, StockStatus


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    sku: str
    category: str
    brand: str | None
    current_stock: int = Field(alias="currentStock")
    reserved_stock: int = Field(alias="reservedStock")
    available_stock: int = Field(alias="availableStock")
    reorder_level: int = Field(alias="reorderLevel")
    stock_status: StockStatus = Field(alias="stockStatus")
    updated_at: datetime = Field(alias="updatedAt")


class InventoryListRead(BaseModel):
    items: list[InventoryRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_id: int = Field(alias="inventoryId")
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    sku: str
    movement_type: InventoryMovementType = Field(alias="movementType")
    previous_quantity: int = Field(alias="previousQuantity")
    updated_quantity: int = Field(alias="updatedQuantity")
    quantity_changed: int = Field(alias="quantityChanged")
    reason: str
    remarks: str | None
    performed_by: str | None = Field(alias="performedBy")
    created_at: datetime = Field(alias="createdAt")


class InventoryMovementListRead(BaseModel):
    items: list[InventoryMovementRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


class InventoryAdjustmentCreate(BaseModel):
    product_id: int = Field(alias="productId", gt=0)
    adjustment_type: Literal["stock-addition", "stock-removal", "manual-adjustment"] = Field(alias="adjustmentType")
    quantity: int | None = Field(default=None, gt=0)
    target_quantity: int | None = Field(default=None, alias="targetQuantity", ge=0)
    reason: str = Field(min_length=1, max_length=255)
    remarks: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_payload(self):
        if not self.reason.strip():
            raise ValueError("Reason is required")
        if self.adjustment_type in {"stock-addition", "stock-removal"} and self.quantity is None:
            raise ValueError("Quantity is required for stock addition/removal")
        if self.adjustment_type == "manual-adjustment":
            if self.target_quantity is None:
                raise ValueError("Target quantity is required for manual adjustment")
            if self.target_quantity < 0:
                raise ValueError("Target quantity cannot be negative")
        return self


class InventoryReorderLevelUpdate(BaseModel):
    reorder_level: int = Field(alias="reorderLevel", ge=0)
    reason: str = Field(min_length=1, max_length=255)


class InventoryCategoryBreakdownRead(BaseModel):
    category: str
    total_quantity: int = Field(alias="totalQuantity")
    product_count: int = Field(alias="productCount")


class InventoryStatusBreakdownRead(BaseModel):
    status: StockStatus
    count: int


class InventoryDashboardRead(BaseModel):
    total_products: int = Field(alias="totalProducts")
    total_inventory_quantity: int = Field(alias="totalInventoryQuantity")
    low_stock_products: int = Field(alias="lowStockProducts")
    out_of_stock_products: int = Field(alias="outOfStockProducts")
    inventory_by_category: list[InventoryCategoryBreakdownRead] = Field(alias="inventoryByCategory")
    stock_status_distribution: list[InventoryStatusBreakdownRead] = Field(alias="stockStatusDistribution")


class InventoryNotificationRead(BaseModel):
    id: int
    product_id: int | None = Field(alias="productId")
    product_name: str | None = Field(alias="productName")
    notification_type: str = Field(alias="notificationType")
    message: str
    created_at: datetime = Field(alias="createdAt")
