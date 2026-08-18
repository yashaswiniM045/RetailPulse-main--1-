import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class StockStatus(str, enum.Enum):
    IN_STOCK = "in-stock"
    LOW_STOCK = "low-stock"
    OUT_OF_STOCK = "out-of-stock"


class InventoryMovementType(str, enum.Enum):
    SALE = "sale"
    MANUAL_ADJUSTMENT = "manual-adjustment"
    STOCK_ADDITION = "stock-addition"
    STOCK_REMOVAL = "stock-removal"


class InventoryNotificationType(str, enum.Enum):
    LOW_STOCK = "low-stock"
    OUT_OF_STOCK = "out-of-stock"
    STOCK_ADJUSTED = "stock-adjusted"


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("company_id", "product_id", name="uq_inventory_company_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    stock_status: Mapped[StockStatus] = mapped_column(Enum(StockStatus), nullable=False, default=StockStatus.IN_STOCK)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company", back_populates="inventories")
    product = relationship("Product", back_populates="inventory")
    movements = relationship("InventoryMovement", back_populates="inventory", cascade="all, delete-orphan")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"), nullable=False, index=True)
    movement_type: Mapped[InventoryMovementType] = mapped_column(Enum(InventoryMovementType), nullable=False)
    quantity_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inventory = relationship("Inventory", back_populates="movements")
    user = relationship("User", back_populates="inventory_movements")


class InventoryNotification(Base):
    __tablename__ = "inventory_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    notification_type: Mapped[InventoryNotificationType] = mapped_column(Enum(InventoryNotificationType), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company", back_populates="inventory_notifications")
    product = relationship("Product", back_populates="inventory_notifications")
    creator = relationship("User", back_populates="inventory_notifications_created")
