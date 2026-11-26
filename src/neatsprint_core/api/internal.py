from __future__ import annotations

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from neatsprint_lib.db import get_session
from neatsprint_lib.errors import ApiError
from neatsprint_lib.events import enqueue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neatsprint_core.api.responses import envelope
from neatsprint_core.api.schemas import ProvisionTenantRequest
from neatsprint_core.db.models import Plan, Tenant, TenantSettings
from neatsprint_core.services.catalogue import provision_tenant

router = APIRouter(prefix="/internal", tags=["internal"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_bootstrap(
    request: Request,
    x_bootstrap_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = request.app.state.settings.bootstrap_token
    if not expected:
        raise ApiError(404, "not_found", "Not found.")
    if not x_bootstrap_token or not secrets.compare_digest(x_bootstrap_token, expected):
        raise ApiError(403, "permission_denied", "Invalid bootstrap token.")


BootstrapDep = Annotated[None, Depends(require_bootstrap)]


@router.get("/tenants/by-slug/{slug}", summary="Look up a tenant by slug")
async def tenant_by_slug(
    slug: str, _: BootstrapDep, request: Request, session: SessionDep
) -> JSONResponse:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if tenant is None:
        raise ApiError(404, "not_found", "Tenant not found.")
    return JSONResponse(
        envelope(
            request,
            {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "plan_code": tenant.plan_code,
                "status": tenant.status,
            },
        )
    )


@router.get("/tenants/{tenant_id}/time-policy", summary="Time logging policy for a tenant")
async def tenant_time_policy(
    tenant_id: UUID, _: BootstrapDep, request: Request, session: SessionDep
) -> JSONResponse:
    settings = await session.get(TenantSettings, tenant_id)
    allow = settings.allow_time_without_sprint if settings is not None else True
    return JSONResponse(envelope(request, {"allow_time_without_sprint": allow}))


@router.get("/tenants/{tenant_id}/limits", summary="Plan limits for a tenant")
async def tenant_limits(
    tenant_id: str, _: BootstrapDep, request: Request, session: SessionDep
) -> JSONResponse:
    from uuid import UUID

    try:
        parsed = UUID(tenant_id)
    except ValueError as exc:
        raise ApiError(422, "validation_failed", "Invalid tenant id.") from exc
    tenant = await session.get(Tenant, parsed)
    if tenant is None:
        raise ApiError(404, "not_found", "Tenant not found.")
    plan = await session.get(Plan, tenant.plan_code)
    if plan is None:
        raise ApiError(404, "not_found", "Plan not found.")
    return JSONResponse(
        envelope(
            request,
            {
                "plan_code": plan.code,
                "max_users": plan.max_users,
                "max_projects": plan.max_projects,
                "retention_days": plan.retention_days,
            },
        )
    )


@router.post("/tenants", status_code=201, summary="Provision a tenant")
async def create_tenant(
    payload: ProvisionTenantRequest,
    _: BootstrapDep,
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    tenant = await provision_tenant(
        session,
        name=payload.name,
        slug=payload.slug,
        plan_code=payload.plan_code,
        modules=payload.modules,
        settings=payload.settings,
    )
    enqueue(
        session,
        event_type="tenant.created",
        tenant_id=tenant.id,
        payload={"tenant_id": str(tenant.id), "slug": tenant.slug, "plan": tenant.plan_code},
    )
    await session.commit()
    return JSONResponse(
        envelope(
            request,
            {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "plan_code": tenant.plan_code,
                "status": tenant.status,
            },
        ),
        status_code=201,
    )
