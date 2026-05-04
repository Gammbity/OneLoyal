from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.audit.context import audit_context_from_request
from app.modules.audit.service import audit_log_service
from app.modules.auth.dependencies import require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.imports.schemas import (
    ImportBatchResponse,
    ImportCancelResponse,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportRowErrorPreview,
    ImportRowResponse,
)
from app.modules.imports.service import import_service

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/csv/preview", response_model=ImportPreviewResponse, status_code=201)
async def preview_csv_import(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    file: Annotated[UploadFile, File()],
) -> ImportPreviewResponse:
    batch = await import_service.preview_csv(
        session,
        company_id=current_user.user.company_id,
        created_by_user_id=current_user.user.id,
        filename=file.filename,
        content=await file.read(),
    )
    errors = await import_service.preview_errors(session, batch=batch)
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="import.previewed",
        entity_type="import_batch",
        entity_id=batch.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={
            "status": batch.status,
            "total_rows": batch.total_rows,
            "valid_rows": batch.valid_rows,
            "invalid_rows": batch.invalid_rows,
        },
        metadata_json={"filename": file.filename},
    )
    await session.commit()
    return ImportPreviewResponse(
        import_batch_id=batch.id,
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        invalid_rows=batch.invalid_rows,
        columns_detected=batch.stats_json.get("columns_detected", []),
        errors=[
            ImportRowErrorPreview(
                row_number=row.row_number,
                errors=row.error_messages_json,
                raw_row_json=row.raw_row_json,
            )
            for row in errors
        ],
        stats_json=batch.stats_json,
    )


@router.get("", response_model=PaginatedResponse[ImportBatchResponse])
async def list_import_batches(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    status: Annotated[str | None, Query(max_length=32)] = None,
    created_at_from: Annotated[datetime | None, Query()] = None,
    created_at_to: Annotated[datetime | None, Query()] = None,
) -> PaginatedResponse[ImportBatchResponse]:
    batches, total = await import_service.list_batches(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        status=status,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    return create_paginated_response(
        items=[ImportBatchResponse.model_validate(batch) for batch in batches],
        params=pagination,
        total=total,
    )


@router.get("/{import_batch_id}", response_model=ImportBatchResponse)
async def get_import_batch(
    import_batch_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ImportBatchResponse:
    batch = await import_service.get_batch(
        session,
        company_id=current_user.user.company_id,
        import_batch_id=import_batch_id,
    )
    return ImportBatchResponse.model_validate(batch)


@router.get(
    "/{import_batch_id}/rows",
    response_model=PaginatedResponse[ImportRowResponse],
)
async def list_import_rows(
    import_batch_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    status: Annotated[str | None, Query(max_length=32)] = None,
) -> PaginatedResponse[ImportRowResponse]:
    rows, total = await import_service.list_rows(
        session,
        company_id=current_user.user.company_id,
        import_batch_id=import_batch_id,
        pagination=pagination,
        status=status,
    )
    return create_paginated_response(
        items=[ImportRowResponse.model_validate(row) for row in rows],
        params=pagination,
        total=total,
    )


@router.post("/{import_batch_id}/commit", response_model=ImportCommitResponse)
async def commit_import_batch(
    import_batch_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> ImportCommitResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    batch = await import_service.commit_batch(
        session,
        company_id=current_user.user.company_id,
        import_batch_id=import_batch_id,
        event_context=event_context,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="import.committed",
        entity_type="import_batch",
        entity_id=batch.id,
        context=event_context,
        after_json={
            "status": batch.status,
            "committed_rows": batch.committed_rows,
            "skipped_rows": batch.skipped_rows,
        },
        metadata_json={"stats": batch.stats_json.get("commit", {})},
    )
    await session.commit()
    return ImportCommitResponse(
        import_batch=ImportBatchResponse.model_validate(batch),
        stats_json=batch.stats_json.get("commit", {}),
    )


@router.post("/{import_batch_id}/cancel", response_model=ImportCancelResponse)
async def cancel_import_batch(
    import_batch_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> ImportCancelResponse:
    batch = await import_service.cancel_batch(
        session,
        company_id=current_user.user.company_id,
        import_batch_id=import_batch_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="import.cancelled",
        entity_type="import_batch",
        entity_id=batch.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={"status": batch.status},
    )
    await session.commit()
    return ImportCancelResponse(import_batch=ImportBatchResponse.model_validate(batch))
