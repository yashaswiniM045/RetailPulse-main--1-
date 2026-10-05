from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Notification(Base):
	__tablename__ = "notifications"
	__table_args__ = (
		UniqueConstraint("user_id", "event_key", name="uq_notifications_user_event"),
		Index("ix_notifications_user_created", "user_id", "created_at"),
		Index("ix_notifications_company_user_read", "company_id", "user_id", "is_read"),
		Index("ix_notifications_company_type_priority", "company_id", "type", "priority"),
	)

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	type: Mapped[str] = mapped_column(String(40), nullable=False)
	title: Mapped[str] = mapped_column(String(160), nullable=False)
	message: Mapped[str] = mapped_column(Text, nullable=False)
	priority: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
	resource_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
	resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
	details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	event_key: Mapped[str] = mapped_column(String(180), nullable=False)
	is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

	company = relationship("Company")
	user = relationship("User", back_populates="notifications")