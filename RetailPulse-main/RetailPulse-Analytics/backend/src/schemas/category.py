from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CategoryStatusUpdate(BaseModel):
    status: Literal["active", "inactive"] = Field(default="active")


class CategoryUpsert(BaseModel):
    category_name: str = Field(alias="categoryName", min_length=2, max_length=255)
    description: str = Field(default="", max_length=1000)
    status: Literal["active", "inactive"] = Field(default="active")


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    status: str
    product_count: int = Field(alias="productCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")