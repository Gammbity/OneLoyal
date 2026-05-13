from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.common.i18n import get_localized_value
from app.modules.audit.context import audit_context_from_request
from app.modules.audit.service import audit_log_service
from app.modules.auth.dependencies import require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.integrations.schemas import (
    IntegrationCreateRequest,
    IntegrationResponse,
    IntegrationTestResponse,
    IntegrationUpdateRequest,
    IntegrationTranslationsUpdateRequest,
)
from app.modules.integrations.service import integration_service
from app.modules.sync.schemas import SyncEnqueueResponse
from app.modules.sync.service import sync_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


async def _integration_response(
    session: AsyncSession,
    integration,
    locale: str = "en",
) -> IntegrationResponse:
    integration.name = get_localized_value(integration.name_i18n, locale) or integration.name
    response = IntegrationResponse.model_validate(integration)
    return response.model_copy(
        update={
            "has_active_credentials": await integration_service.has_active_credentials(
                session,
                integration_id=integration.id,
            )
        }
    )


@router.post("", response_model=IntegrationResponse, status_code=201)
async def create_integration(
    data: IntegrationCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> IntegrationResponse:
    integration = await integration_service.create_integration(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="integration.created",
        entity_type="integration",
        entity_id=integration.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={
            "provider": integration.provider,
            "name": integration.name,
            "status": integration.status,
        },
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    return await _integration_response(session, integration, locale)


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> list[IntegrationResponse]:
    integrations = await integration_service.list_integrations(
        session,
        company_id=current_user.user.company_id,
    )
    locale = getattr(request.state, "locale", "en")
    return [await _integration_response(session, integration, locale) for integration in integrations]


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> IntegrationResponse:
    integration = await integration_service.get_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    locale = getattr(request.state, "locale", "en")
    return await _integration_response(session, integration, locale)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> IntegrationResponse:
    before = await integration_service.get_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    before_json = {
        "name": before.name,
        "status": before.status,
    }
    integration = await integration_service.update_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="integration.updated",
        entity_type="integration",
        entity_id=integration.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json=before_json,
        after_json={
            "name": integration.name,
            "status": integration.status,
        },
        metadata_json={
            "credentials_updated": data.credentials_json is not None,
        },
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    return await _integration_response(session, integration, locale)


@router.patch("/{integration_id}/translations", response_model=IntegrationResponse)
async def update_integration_translations(
    integration_id: UUID,
    data: IntegrationTranslationsUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> IntegrationResponse:
    before = await integration_service.get_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    updated = await integration_service.update_integration_translations(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="integration.translations.updated",
        entity_type="integration",
        entity_id=updated.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json={"name": before.name, "name_i18n": before.name_i18n},
        after_json={"name": updated.name, "name_i18n": updated.name_i18n},
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    return await _integration_response(session, updated, locale)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> Response:
    integration = await integration_service.delete_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="integration.deleted",
        entity_type="integration",
        entity_id=integration.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={
            "name": integration.name,
            "status": integration.status,
        },
    )
    await session.commit()
    return Response(status_code=204)


@router.post("/{integration_id}/test", response_model=IntegrationTestResponse)
async def test_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> IntegrationTestResponse:
    result = await integration_service.test_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="integration.tested",
        entity_type="integration",
        entity_id=integration_id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        metadata_json={"ok": result.ok},
    )
    return IntegrationTestResponse(
        ok=result.ok,
        message=result.message,
        details=result.details,
    )


@router.post("/{integration_id}/sync", response_model=SyncEnqueueResponse)
async def sync_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> SyncEnqueueResponse:
    sync_run = await sync_service.create_sync_run(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
        created_by_user_id=current_user.user.id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="sync.queued",
        entity_type="sync_run",
        entity_id=sync_run.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        metadata_json={
            "integration_id": str(integration_id),
            "sync_type": sync_run.sync_type,
            "task_id": sync_run.task_id,
        },
    )
    await session.commit()
    task_id = sync_service.publish_sync_run(sync_run.id, task_id=sync_run.task_id)
    if sync_run.task_id != task_id:
        sync_run.task_id = task_id
        await session.commit()
    return SyncEnqueueResponse(
        sync_run_id=sync_run.id,
        task_id=sync_run.task_id,
        status=sync_run.status,
    )
