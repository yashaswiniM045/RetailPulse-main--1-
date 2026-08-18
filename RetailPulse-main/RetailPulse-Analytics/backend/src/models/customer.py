import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .sale import SalesChannel


class CustomerGender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer-not-to-say"


class CustomerType(str, enum.Enum):
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    CORPORATE = "corporate"


class CustomerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CustomerSegment(str, enum.Enum):
    NEW = "new"
    REGULAR = "regular"
    LOYAL = "loyal"
    VIP = "vip"


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("company_id", "customer_code", name="uq_customers_company_code"),
        UniqueConstraint("company_id", "email", name="uq_customers_company_email"),
        UniqueConstraint("company_id", "phone_number", name="uq_customers_company_phone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    customer_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[CustomerGender | None] = mapped_column(Enum(CustomerGender), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(Enum(CustomerType), nullable=False)
    preferred_sales_channel: Mapped[SalesChannel | None] = mapped_column(Enum(SalesChannel), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus), nullable=False, default=CustomerStatus.ACTIVE)
    segment: Mapped[CustomerSegment] = mapped_column(Enum(CustomerSegment), nullable=False, default=CustomerSegment.NEW)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="customers")
    purchase_summary = relationship(
        "CustomerPurchaseSummary", back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )
    timeline_items = relationship("CustomerTimeline", back_populates="customer", cascade="all, delete-orphan")


class CustomerPurchaseSummary(Base):
    __tablename__ = "customer_purchase_summary"
    __table_args__ = (UniqueConstraint("company_id", "customer_id", name="uq_customer_purchase_summary_customer"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_revenue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    quantity_purchased: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_order_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    first_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchase_frequency_days: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    favorite_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    favorite_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer = relationship("Customer", back_populates="purchase_summary")
    favorite_product = relationship("Product")
    favorite_category = relationship("Category")


class CustomerTimelineType(str, enum.Enum):
    REGISTERED = "registered"
    PROFILE_UPDATED = "profile-updated"
    FIRST_PURCHASE = "first-purchase"
    LARGE_PURCHASE = "large-purchase"
    DEACTIVATED = "deactivated"
    REACTIVATED = "reactivated"
    STATUS_CHANGED = "status-changed"


class CustomerTimeline(Base):
    __tablename__ = "customer_timeline"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    event_type: Mapped[CustomerTimelineType] = mapped_column(Enum(CustomerTimelineType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    customer = relationship("Customer", back_populates="timeline_items")


class CustomerNotificationType(str, enum.Enum):
    NEW_REGISTRATION = "new-registration"
    VIP_STATUS = "vip-status"
    INACTIVITY = "inactivity"
    FIRST_PURCHASE = "first-purchase"


class CustomerNotification(Base):
    __tablename__ = "customer_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    notification_type: Mapped[CustomerNotificationType] = mapped_column(Enum(CustomerNotificationType), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
