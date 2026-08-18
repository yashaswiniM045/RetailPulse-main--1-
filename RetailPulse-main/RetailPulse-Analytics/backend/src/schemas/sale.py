from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.sale import PaymentMethod, PaymentStatus, SalesChannel


class SaleItemUpsert(BaseModel):
    product_id: int = Field(alias="productId", gt=0)
    quantity: int = Field(gt=0)
    unit_price: float = Field(alias="unitPrice", gt=0)
    discount: float = Field(default=0, ge=0)
    tax: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_discount(self):
        line_subtotal = self.quantity * self.unit_price
        if self.discount > line_subtotal:
            raise ValueError("Discount cannot exceed total product value")
        return self


class SaleUpsert(BaseModel):
    sale_date: datetime = Field(alias="saleDate")
    customer_id: int | None = Field(default=None, alias="customerId", gt=0)
    customer_name: str = Field(alias="customerName", min_length=1, max_length=255)
    sales_channel: SalesChannel = Field(alias="salesChannel")
    payment_method: PaymentMethod = Field(alias="paymentMethod")
    payment_status: PaymentStatus = Field(default=PaymentStatus.PAID, alias="paymentStatus")
    notes: str | None = Field(default=None, max_length=1000)
    items: list[SaleItemUpsert] = Field(min_length=1)


class SaleNotification(BaseModel):
    type: str
    message: str


class SaleItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int = Field(alias="productId")
    product_name: str = Field(alias="productName")
    sku: str
    category_id: int = Field(alias="categoryId")
    category_name: str = Field(alias="categoryName")
    quantity: int
    unit_price: float = Field(alias="unitPrice")
    discount: float
    tax: float
    total: float
    remaining_stock: int = Field(alias="remainingStock")


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None = Field(alias="customerId")
    invoice_number: str = Field(alias="invoiceNumber")
    customer_name: str = Field(alias="customerName")
    sale_date: datetime = Field(alias="saleDate")
    sales_channel: SalesChannel = Field(alias="salesChannel")
    payment_method: PaymentMethod = Field(alias="paymentMethod")
    payment_status: PaymentStatus = Field(alias="paymentStatus")
    notes: str | None = None
    subtotal: float
    discount_total: float = Field(alias="discountTotal")
    tax_total: float = Field(alias="taxTotal")
    total_amount: float = Field(alias="totalAmount")
    created_by: int = Field(alias="createdBy")
    created_by_name: str = Field(alias="createdByName")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    items: list[SaleItemRead]
    notifications: list[SaleNotification] = []


class SaleListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None = Field(alias="customerId")
    invoice_number: str = Field(alias="invoiceNumber")
    customer_name: str = Field(alias="customerName")
    sale_date: datetime = Field(alias="saleDate")
    sales_channel: SalesChannel = Field(alias="salesChannel")
    payment_method: PaymentMethod = Field(alias="paymentMethod")
    payment_status: PaymentStatus = Field(alias="paymentStatus")
    total_amount: float = Field(alias="totalAmount")
    created_by_name: str = Field(alias="createdByName")
    item_count: int = Field(alias="itemCount")


class SaleListPageRead(BaseModel):
    items: list[SaleListRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
