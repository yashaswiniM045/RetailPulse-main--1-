from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class WorkflowConfiguration(Base):
    __tablename__ = "workflow_configurations"
    __table_args__ = (
        UniqueConstraint("company_id", "request_type", name="uq_workflow_config_company_type"),
        Index("ix_workflow_config_company_active", "company_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(50), nullable=False)
    approval_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    allow_self_approval: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_company_status", "company_id", "status"),
        Index("ix_approval_requests_company_type", "company_id", "request_type"),
        Index("ix_approval_requests_company_created", "company_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    approver_role: Mapped[str] = mapped_column(String(50), nullable=False)
    related_record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_record_id: Mapped[int] = mapped_column(nullable=False)
    current_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requested_changes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    requester = relationship("User", foreign_keys=[requested_by_id])
    history = relationship("ApprovalHistory", back_populates="approval_request", order_by="ApprovalHistory.created_at", cascade="all, delete-orphan")


class ApprovalHistory(Base):
    __tablename__ = "approval_history"
    __table_args__ = (Index("ix_approval_history_request_created", "request_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    approval_request = relationship("ApprovalRequest", back_populates="history")
    actor = relationship("User")
