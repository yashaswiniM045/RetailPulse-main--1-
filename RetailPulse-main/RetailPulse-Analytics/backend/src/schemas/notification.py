from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: int
    type: str
    title: str
    message: str
    priority: str
    resource_type: str | None = Field(alias="resourceType")
    resource_id: str | None = Field(alias="resourceId")
    details: dict[str, Any] | None = None
    is_read: bool = Field(alias="isRead")
    created_at: datetime = Field(alias="createdAt")
    read_at: datetime | None = Field(alias="readAt")
    resolved_at: datetime | None = Field(alias="resolvedAt")


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


class UnreadCountRead(BaseModel):
    unread_count: int = Field(alias="unreadCount")
