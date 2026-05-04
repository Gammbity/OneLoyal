from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImportRowErrorPreview(BaseModel):
    row_number: int
    errors: list[str]
    raw_row_json: dict[str, Any]


class ImportPreviewResponse(BaseModel):
    import_batch_id: UUID
    total_rows: int
    valid_rows: int
    invalid_rows: int
    columns_detected: list[str]
    errors: list[ImportRowErrorPreview]
    stats_json: dict[str, Any]


class ImportBatchResponse(BaseModel):
    id: UUID
    company_id: UUID
    created_by_user_id: UUID | None
    source_type: str
    provider: str
    status: str
    original_filename: str | None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    committed_rows: int
    skipped_rows: int
    stats_json: dict[str, Any]
    error_summary: str | None
    committed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportRowResponse(BaseModel):
    id: UUID
    company_id: UUID
    import_batch_id: UUID
    row_number: int
    raw_row_json: dict[str, Any]
    normalized_row_json: dict[str, Any]
    status: str
    error_messages_json: list[str]
    idempotency_key: str | None
    customer_external_id: str | None
    sale_external_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportCommitResponse(BaseModel):
    import_batch: ImportBatchResponse
    stats_json: dict[str, Any]


class ImportCancelResponse(BaseModel):
    import_batch: ImportBatchResponse
