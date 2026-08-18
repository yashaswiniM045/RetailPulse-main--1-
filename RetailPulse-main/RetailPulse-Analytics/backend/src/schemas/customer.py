from datetime import date, datetime
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from src.models.customer import CustomerGender, CustomerSegment, CustomerStatus, CustomerTimelineType, CustomerType
from src.models.sale import SalesChannel


class CustomerUpsert(BaseModel):
    full_name: str = Field(alias="fullName", min_length=1, max_length=255)
    email: EmailStr
    phone_number: str = Field(alias="phoneNumber", min_length=5, max_length=50)
    date_of_birth: date | None = Field(default=None, alias="dateOfBirth")
    gender: CustomerGender | None = None
    address_line1: str = Field(alias="addressLine1", min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, alias="addressLine2", max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(alias="postalCode", min_length=1, max_length=20)
    customer_type: CustomerType = Field(alias="customerType")
    preferred_sales_channel: SalesChannel | None = Field(default=None, alias="preferredSalesChannel")
    status: CustomerStatus = CustomerStatus.ACTIVE

    @model_validator(mode="after")
    def normalize(self):
        self.full_name = self.full_name.strip()
        self.phone_number = self.phone_number.strip()
        self.address_line1 = self.address_line1.strip()
        if self.address_line2 is not None:
            self.address_line2 = self.address_line2.strip() or None
        self.city = self.city.strip()
        self.state = self.state.strip()
        self.country = self.country.strip()
        self.postal_code = self.postal_code.strip()
        if not re.fullmatch(r"^\+?[0-9\-\s()]{7,20}$", self.phone_number):
            raise ValueError("Phone number format is invalid")
        return self


class CustomerStatusUpdate(BaseModel):
    status: CustomerStatus


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_code: str = Field(alias="customerId")
    full_name: str = Field(alias="fullName")
    email: str
    phone_number: str = Field(alias="phoneNumber")
    date_of_birth: date | None = Field(alias="dateOfBirth")
    gender: CustomerGender | None
    address_line1: str | None = Field(alias="addressLine1")
    address_line2: str | None = Field(alias="addressLine2")
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None = Field(alias="postalCode")
    customer_type: CustomerType = Field(alias="customerType")
    preferred_sales_channel: SalesChannel | None = Field(alias="preferredSalesChannel")
    status: CustomerStatus
    segment: CustomerSegment
    total_orders: int = Field(default=0, alias="totalPurchases")
    total_spend: float = Field(default=0, alias="totalSpend")
    last_purchase_date: datetime | None = Field(default=None, alias="lastPurchaseDate")
    created_at: datetime = Field(alias="customerSince")
    updated_at: datetime = Field(alias="updatedAt")


class CustomerListRead(BaseModel):
    items: list[CustomerRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


class CustomerFavoriteRead(BaseModel):
    id: int | None
    name: str | None


class CustomerPurchaseSummaryRead(BaseModel):
    total_orders: int = Field(alias="totalOrders")
    total_revenue: float = Field(alias="totalRevenue")
    quantity_purchased: int = Field(alias="quantityPurchased")
    average_order_value: float = Field(alias="averageOrderValue")
    first_purchase_at: datetime | None = Field(alias="firstPurchaseDate")
    last_purchase_at: datetime | None = Field(alias="lastPurchaseDate")
    purchase_frequency_days: float = Field(alias="purchaseFrequencyDays")
    favorite_product: CustomerFavoriteRead = Field(alias="favoriteProduct")
    favorite_category: CustomerFavoriteRead = Field(alias="favoriteCategory")
    frequently_purchased_products: list[dict] = Field(alias="frequentlyPurchasedProducts")
    recent_transactions: list[dict] = Field(alias="recentTransactions")


class CustomerTimelineRead(BaseModel):
    id: int
    event_type: CustomerTimelineType = Field(alias="eventType")
    title: str
    description: str | None
    created_at: datetime = Field(alias="timestamp")


class CustomerProfileRead(BaseModel):
    customer: CustomerRead
    purchase_summary: CustomerPurchaseSummaryRead = Field(alias="purchaseSummary")
    timeline: list[CustomerTimelineRead]


class CustomerAnalyticsKpiRead(BaseModel):
    total_customers: int = Field(alias="totalCustomers")
    active_customers: int = Field(alias="activeCustomers")
    new_customers: int = Field(alias="newCustomers")
    returning_customers: int = Field(alias="returningCustomers")
    average_customer_spend: float = Field(alias="averageCustomerSpend")
    total_revenue_generated: float = Field(alias="totalRevenueGenerated")
    average_purchase_frequency: float = Field(alias="averagePurchaseFrequency")


class CustomerAnalyticsRead(BaseModel):
    kpis: CustomerAnalyticsKpiRead
    customer_growth_trend: list[dict] = Field(alias="customerGrowthTrend")
    new_vs_returning: list[dict] = Field(alias="newVsReturning")
    revenue_by_customer_type: list[dict] = Field(alias="revenueByCustomerType")
    top_customers_by_revenue: list[dict] = Field(alias="topCustomersByRevenue")
    purchase_frequency_distribution: list[dict] = Field(alias="purchaseFrequencyDistribution")
    location_distribution: list[dict] = Field(alias="locationDistribution")
    monthly_customer_acquisition: list[dict] = Field(alias="monthlyCustomerAcquisition")
    spending_distribution: list[dict] = Field(alias="customerSpendingDistribution")


class CustomerNotificationRead(BaseModel):
    id: int
    customer_id: int | None = Field(alias="customerId")
    customer_name: str | None = Field(alias="customerName")
    notification_type: str = Field(alias="notificationType")
    message: str
    created_at: datetime = Field(alias="createdAt")


CustomerSortBy = Literal["name", "totalSpend", "totalOrders", "lastPurchase", "customerSince"]
CustomerSortDirection = Literal["asc", "desc"]
