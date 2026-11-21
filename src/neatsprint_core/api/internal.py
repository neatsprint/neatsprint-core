from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from neatsprint_lib.db import get_session
from neatsprint_lib.errors import ApiError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neatsprint_core.api.responses import envelope
from neatsprint_core.api.schemas import ProvisionTenantRequest
from neatsprint_core.db.models import Tenant
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
