from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.user import UserRole

WorkflowRequestType = Literal[
    "stock-adjustment",
    "product-deactivation",
    "product-price-change",
    "customer-information-change",
    "inventory-import-approval",
]


class ApprovalRequestCreate(BaseModel):
    request_type: WorkflowRequestType = Field(alias="requestType")
    related_record_id: int = Field(alias="relatedRecordId", gt=0)
    requested_changes: dict[str, Any] = Field(alias="requestedChanges")
    reason: str = Field(min_length=1, max_length=2000)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    draft: bool = False

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def normalize_reason(self):
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("A reason is required")
        return self


class ApprovalDecision(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def normalize_comment(self):
        if self.comment is not None:
            self.comment = self.comment.strip() or None
        return self


class ApprovalRejection(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def normalize_comment(self):
        self.comment = self.comment.strip()
        if not self.comment:
            raise ValueError("A rejection reason is required")
        return self


class WorkflowConfigurationUpdate(BaseModel):
    approver_role: UserRole = Field(alias="approverRole")
    approval_required: bool = Field(alias="approvalRequired")
    allow_self_approval: bool = Field(default=False, alias="allowSelfApproval")
    is_active: bool = Field(alias="isActive")

    model_config = ConfigDict(populate_by_name=True)
