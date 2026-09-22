from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    user_name: str | None = Field(default=None, alias="userName")
    user_email: str | None = Field(default=None, alias="userEmail")
    action: str
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    resource_name: str | None = Field(default=None, alias="resourceName")
    description: str | None = None
    ip_address: str | None = Field(default=None, alias="ipAddress")
    user_agent: str | None = Field(default=None, alias="userAgent")
    timestamp: datetime
    status: str
    before_values: dict[str, Any] | None = Field(default=None, alias="beforeValues")
    after_values: dict[str, Any] | None = Field(default=None, alias="afterValues")


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
