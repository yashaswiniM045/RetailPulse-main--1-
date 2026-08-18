from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .category import CategorySummary


class ProductUpsert(BaseModel):
    product_name: str = Field(alias="productName", min_length=1, max_length=255)
    sku: str = Field(min_length=1, max_length=120)
    category_id: int = Field(alias="categoryId", gt=0)
    brand: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=1000)
    unit_price: float = Field(alias="unitPrice", gt=0)
    cost_price: float = Field(alias="costPrice", ge=0)
    stock_quantity: int = Field(alias="stockQuantity", ge=0)
    unit_of_measure: str = Field(alias="unitOfMeasure", min_length=1, max_length=50)
    status: Literal["active", "inactive"] = Field(default="active")

    @model_validator(mode="after")
    def validate_prices(self):
        if self.cost_price > self.unit_price:
            raise ValueError("Cost price cannot exceed unit price")
        return self


class ProductStatusUpdate(BaseModel):
    status: Literal["active", "inactive"]


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    category: CategorySummary
    brand: str | None
    description: str | None
    unit_price: float = Field(alias="unitPrice")
    cost_price: float = Field(alias="costPrice")
    stock_quantity: int = Field(alias="stockQuantity")
    is_out_of_stock: bool = Field(alias="isOutOfStock")
    unit_of_measure: str = Field(alias="unitOfMeasure")
    status: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ProductListRead(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")