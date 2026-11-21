"""Core tenancy, plans and module endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from neatsprint_lib.auth import Principal, require_permission
from neatsprint_lib.db import get_session
from neatsprint_lib.errors import ApiError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neatsprint_core.api.responses import envelope
from neatsprint_core.api.schemas import (
    ApplicationOut,
    TenantApplicationOut,
    TenantOut,
    TenantSettingsOut,
    TenantSettingsUpdate,
    TenantUpdate,
)
from neatsprint_core.db.models import (
    Application,
    Plan,
    Tenant,
    TenantApplication,
    TenantSettings,
)

router = APIRouter(prefix="/core", tags=["tenancy"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ReadPrincipal = Annotated[Principal, Depends(require_permission("core:tenant:read"))]
UpdatePrincipal = Annotated[Principal, Depends(require_permission("core:tenant:update"))]


async def _tenant_payload(session: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise ApiError(404, "not_found", "Tenant not found.")
    settings = await session.get(TenantSettings, tenant_id)
    if settings is None:
        settings = TenantSettings(tenant_id=tenant_id)
        session.add(settings)
        await session.flush()
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan_code=tenant.plan_code,
        status=tenant.status,
        created_at=tenant.created_at,
        settings=TenantSettingsOut(
            timezone=settings.timezone,
            week_start=settings.week_start,
            locale=settings.locale,
            screenshot_interval_min=settings.screenshot_interval_min,
            screenshot_interval_max=settings.screenshot_interval_max,
            privacy_window_hours=settings.privacy_window_hours,
            retention_days=settings.retention_days,
            aggregation_threshold=settings.aggregation_threshold,
            domain_auto_join=settings.domain_auto_join,
        ),
    ).model_dump(mode="json")


@router.get("/tenants/current", summary="Current tenant")
async def current_tenant(
    principal: ReadPrincipal, request: Request, session: SessionDep
) -> JSONResponse:
    return JSONResponse(envelope(request, await _tenant_payload(session, principal.tenant_id)))


@router.patch("/tenants/current", summary="Update tenant")
async def update_tenant(
    payload: TenantUpdate,
    principal: UpdatePrincipal,
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    tenant = await session.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise ApiError(404, "not_found", "Tenant not found.")
    if payload.name is not None:
        tenant.name = payload.name
    if payload.plan_code is not None:
        plan = await session.get(Plan, payload.plan_code)
        if plan is None:
            raise ApiError(422, "invalid_plan", "Unknown plan.")
        tenant.plan_code = plan.code
    await session.commit()
    return JSONResponse(envelope(request, await _tenant_payload(session, principal.tenant_id)))


@router.get("/tenants/current/settings", summary="Tenant settings")
async def get_settings(
    principal: ReadPrincipal, request: Request, session: SessionDep
) -> JSONResponse:
    payload = await _tenant_payload(session, principal.tenant_id)
    return JSONResponse(envelope(request, payload["settings"]))


@router.patch("/tenants/current/settings", summary="Update tenant settings")
async def update_settings(
    payload: TenantSettingsUpdate,
    principal: UpdatePrincipal,
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    settings = await session.get(TenantSettings, principal.tenant_id)
    if settings is None:
        settings = TenantSettings(tenant_id=principal.tenant_id)
        session.add(settings)

    data = payload.model_dump(exclude_none=True)
    low = data.get("screenshot_interval_min", settings.screenshot_interval_min)
    high = data.get("screenshot_interval_max", settings.screenshot_interval_max)
    if low > high:
        raise ApiError(
            422, "validation_failed", "screenshot_interval_min must not exceed the maximum."
        )
    for field, value in data.items():
        setattr(settings, field, value)
    await session.commit()
    return JSONResponse(
        envelope(request, (await _tenant_payload(session, principal.tenant_id))["settings"])
    )


@router.get("/applications", summary="Application registry")
async def list_applications(
    principal: ReadPrincipal, request: Request, session: SessionDep
) -> JSONResponse:
    rows = (await session.execute(select(Application).order_by(Application.code))).scalars()
    return JSONResponse(
        envelope(
            request,
            [ApplicationOut(
                code=row.code,
                name=row.name,
                description=row.description,
                is_global=row.is_global,
            ).model_dump(mode="json") for row in rows],
        )
    )


@router.get("/tenant-applications", summary="Modules enabled for this tenant")
async def list_tenant_applications(
    principal: ReadPrincipal, request: Request, session: SessionDep
) -> JSONResponse:
    rows = (
        await session.execute(
            select(TenantApplication, Application)
            .join(Application, Application.code == TenantApplication.application_code)
            .where(TenantApplication.tenant_id == principal.tenant_id)
            .order_by(Application.code)
        )
    ).all()
    data = [
        TenantApplicationOut(
            application_code=tenant_app.application_code,
            name=app.name,
            enabled=tenant_app.enabled,
            enabled_at=tenant_app.enabled_at,
            disabled_at=tenant_app.disabled_at,
        ).model_dump(mode="json")
        for tenant_app, app in rows
    ]
    return JSONResponse(envelope(request, data))


@router.put("/tenant-applications/{code}", summary="Enable or disable a module")
async def set_tenant_application(
    code: str,
    enabled: bool,
    principal: UpdatePrincipal,
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    app = await session.get(Application, code)
    if app is None:
        raise ApiError(404, "not_found", "Application not found.")
    row = await session.get(TenantApplication, (principal.tenant_id, code))
    if row is None:
        row = TenantApplication(
            tenant_id=principal.tenant_id, application_code=code, enabled=enabled
        )
        session.add(row)
    else:
        row.enabled = enabled
    await session.commit()
    return JSONResponse(
        envelope(
            request,
            {
                "application_code": code,
                "name": app.name,
                "enabled": enabled,
            },
        )
    )
