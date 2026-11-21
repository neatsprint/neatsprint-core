"""Core platform database models: tenants, plans, applications and settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from neatsprint_lib.db import Base, TimestampMixin
from neatsprint_lib.events import OutboxEvent as OutboxEvent  # noqa: F401 - register table
from neatsprint_lib.ids import new_id
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_projects: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_id
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(24), nullable=False, default="TEAM")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    week_start: Mapped[str] = mapped_column(String(8), nullable=False, default="monday")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    screenshot_interval_min: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    screenshot_interval_max: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    privacy_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    aggregation_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    domain_auto_join: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Application(Base):
    __tablename__ = "applications"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ApplicationFeature(Base):
    __tablename__ = "application_features"

    application_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("applications.code", ondelete="CASCADE"), primary_key=True
    )
    feature_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class TenantApplication(Base):
    __tablename__ = "tenant_applications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    application_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("applications.code", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
