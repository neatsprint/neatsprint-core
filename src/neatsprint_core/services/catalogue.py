"""Plan and application catalogue, seeded idempotently at startup."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from neatsprint_lib.errors import ApiError
from neatsprint_lib.ids import new_id
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from neatsprint_core.db.models import Application, Plan, Tenant, TenantApplication, TenantSettings

PLANS = [
    {
        "code": "FREE",
        "name": "Free",
        "max_users": 5,
        "max_projects": 3,
        "retention_days": 7,
        "features": {},
    },
    {
        "code": "TEAM",
        "name": "Team",
        "max_users": 25,
        "max_projects": 20,
        "retention_days": 30,
        "features": {},
    },
    {
        "code": "BUSINESS",
        "name": "Business",
        "max_users": 100,
        "max_projects": 100,
        "retention_days": 90,
        "features": {},
    },
    {
        "code": "ENTERPRISE",
        "name": "Enterprise",
        "max_users": 1000,
        "max_projects": 1000,
        "retention_days": 365,
        "features": {"ai": True, "sso": True, "audit_archive": True},
    },
]

APPLICATIONS = [
    {
        "code": "TASK_MGMT",
        "name": "Task Management",
        "description": "Projects, backlog, sprints and boards",
    },
    {
        "code": "MONITORING",
        "name": "Monitoring",
        "description": "Privacy-first screenshots and activity",
    },
    {
        "code": "REPORTS",
        "name": "Reports",
        "description": "Productivity, agile and compliance reporting",
    },
    {
        "code": "CHAT",
        "name": "Chat",
        "description": "Team channels and presence (Phase 2)",
    },
    {
        "code": "AI_ASSISTANT",
        "name": "AI Assistant",
        "description": "Summaries and project Q&A (Phase 3)",
    },
]


async def ensure_catalogue(session: AsyncSession) -> None:
    await session.execute(
        pg_insert(Plan).values(PLANS).on_conflict_do_update(
            index_elements=[Plan.code],
            set_={
                "name": pg_insert(Plan).excluded.name,
                "max_users": pg_insert(Plan).excluded.max_users,
                "max_projects": pg_insert(Plan).excluded.max_projects,
                "retention_days": pg_insert(Plan).excluded.retention_days,
                "features": pg_insert(Plan).excluded.features,
            },
        )
    )
    await session.execute(
        pg_insert(Application)
        .values(APPLICATIONS)
        .on_conflict_do_update(
            index_elements=[Application.code],
            set_={
                "name": pg_insert(Application).excluded.name,
                "description": pg_insert(Application).excluded.description,
            },
        )
    )
    await session.commit()


async def provision_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    plan_code: str,
    modules: list[str],
    settings: dict[str, Any],
) -> Tenant:
    plan = await session.get(Plan, plan_code)
    if plan is None:
        raise ApiError(422, "invalid_plan", "Unknown plan.")
    existing = await session.execute(select(Tenant.id).where(Tenant.slug == slug))
    if existing.first() is not None:
        raise ApiError(409, "duplicate_key", "That workspace slug is already in use.")

    tenant = Tenant(
        id=new_id(),
        name=name,
        slug=slug,
        plan_code=plan.code,
        status="ACTIVE",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    session.add(tenant)
    await session.flush()

    session.add(
        TenantSettings(
            tenant_id=tenant.id,
            retention_days=plan.retention_days,
            privacy_window_hours=int(settings.get("privacy_window_hours", 24)),
            screenshot_interval_min=int(settings.get("screenshot_interval_min", 5)),
            screenshot_interval_max=int(settings.get("screenshot_interval_max", 10)),
            timezone=str(settings.get("timezone", "UTC")),
            locale=str(settings.get("locale", "en")),
        )
    )

    valid_modules = set((await session.execute(select(Application.code))).scalars().all())
    for code in modules:
        if code not in valid_modules:
            raise ApiError(422, "invalid_module", f"Unknown module '{code}'.")
        session.add(
            TenantApplication(tenant_id=tenant.id, application_code=code, enabled=True)
        )

    await session.commit()
    return tenant
