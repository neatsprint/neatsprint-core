from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TenantSettingsOut(BaseModel):
    timezone: str
    week_start: str
    locale: str
    screenshot_interval_min: int
    screenshot_interval_max: int
    privacy_window_hours: int
    retention_days: int
    aggregation_threshold: int
    domain_auto_join: bool
    allow_time_without_sprint: bool


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    plan_code: str
    status: str
    created_at: datetime
    settings: TenantSettingsOut


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    plan_code: str | None = Field(default=None, min_length=2, max_length=24)


class TenantSettingsUpdate(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    week_start: str | None = None
    locale: str | None = Field(default=None, max_length=16)
    screenshot_interval_min: int | None = Field(default=None, ge=1, le=120)
    screenshot_interval_max: int | None = Field(default=None, ge=1, le=240)
    privacy_window_hours: int | None = Field(default=None, ge=1, le=72)
    retention_days: int | None = Field(default=None, ge=1, le=365)
    aggregation_threshold: int | None = Field(default=None, ge=0, le=100)
    domain_auto_join: bool | None = None
    allow_time_without_sprint: bool | None = None

    @field_validator("week_start")
    @classmethod
    def _week_start(cls, value: str | None) -> str | None:
        if value is not None and value not in {"monday", "sunday"}:
            raise ValueError("week_start must be monday or sunday")
        return value


class ApplicationOut(BaseModel):
    code: str
    name: str
    description: str | None
    is_global: bool


class TenantApplicationOut(BaseModel):
    application_code: str
    name: str
    enabled: bool
    enabled_at: datetime | None
    disabled_at: datetime | None


class ProvisionTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    plan_code: str = "TEAM"
    modules: list[str] = Field(
        default_factory=lambda: ["TASK_MGMT", "MONITORING", "REPORTS"]
    )
    settings: dict[str, Any] = Field(default_factory=dict)
