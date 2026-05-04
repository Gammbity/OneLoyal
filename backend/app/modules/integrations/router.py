from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.integrations.schemas import (
    IntegrationCreateRequest,
    IntegrationResponse,
    IntegrationTestResponse,
    IntegrationUpdateRequest,
)
from app.modules.integrations.service import integration_service
from app.modules.sync.schemas import SyncEnqueueResponse
from app.modules.sync.service import sync_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


async def _integration_response(
    session: AsyncSession,
    integration,
) -> IntegrationResponse:
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
) -> IntegrationResponse:
    integration = await integration_service.create_integration(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return await _integration_response(session, integration)


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[IntegrationResponse]:
    integrations = await integration_service.list_integrations(
        session,
        company_id=current_user.user.company_id,
    )
    return [
        await _integration_response(session, integration)
        for integration in integrations
    ]


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationResponse:
    integration = await integration_service.get_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    return await _integration_response(session, integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationResponse:
    integration = await integration_service.update_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
        data=data,
    )
    await session.commit()
    return await _integration_response(session, integration)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await integration_service.delete_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
    )
    await session.commit()
    return Response(status_code=204)


@router.post("/{integration_id}/test", response_model=IntegrationTestResponse)
async def test_integration(
    integration_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationTestResponse:
    result = await integration_service.test_integration(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
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
) -> SyncEnqueueResponse:
    sync_run = await sync_service.create_sync_run(
        session,
        company_id=current_user.user.company_id,
        integration_id=integration_id,
        created_by_user_id=current_user.user.id,
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
