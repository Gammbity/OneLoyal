from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.notifications.models import (
    NotificationChannel,
    NotificationRecipientType,
)


class NotificationTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    channel: NotificationChannel
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str = Field(min_length=1)
    locale: str = Field(default="en", min_length=2, max_length=16)
    is_active: bool = True
    metadata_json: dict[str, Any] | None = None


class NotificationTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    channel: NotificationChannel | None = None
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str | None = Field(default=None, min_length=1)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class NotificationTemplateResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    channel: str
    subject_template: str | None
    body_template: str
    locale: str
    is_active: bool
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationRuleCreateRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=120)
    template_id: UUID
    channel: NotificationChannel | None = None
    recipient_type: NotificationRecipientType = NotificationRecipientType.CUSTOMER
    condition_json: dict[str, Any] | None = None
    is_active: bool = True
    metadata_json: dict[str, Any] | None = None


class NotificationRuleUpdateRequest(BaseModel):
    event_type: str | None = Field(default=None, min_length=1, max_length=120)
    template_id: UUID | None = None
    channel: NotificationChannel | None = None
    recipient_type: NotificationRecipientType | None = None
    condition_json: dict[str, Any] | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class NotificationRuleResponse(BaseModel):
    id: UUID
    company_id: UUID
    event_type: str
    template_id: UUID
    channel: str
    recipient_type: str
    condition_json: dict[str, Any]
    is_active: bool
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationEventResponse(BaseModel):
    id: UUID
    company_id: UUID
    domain_event_id: UUID
    notification_rule_id: UUID | None
    notification_template_id: UUID | None
    channel: str
    recipient_type: str
    customer_id: UUID | None
    user_id: UUID | None
    recipient_identifier: str | None
    subject: str | None
    body: str | None
    status: str
    attempts: int
    last_error: str | None
    skipped_reason: str | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationEventStatusUpdateRequest(BaseModel):
    error: str | None = Field(default=None, max_length=5000)
    skipped_reason: str | None = Field(default=None, max_length=5000)


class ProcessPendingDomainEventsResponse(BaseModel):
    checked_events: int
    processed_events: int
    failed_events: int
    events_without_company: int
    events_without_rules: int
    generated_notifications: int
    skipped_notifications: int
    failed_notifications: int


class ProcessPendingNotificationsResponse(BaseModel):
    checked_notifications: int
    sent_notifications: int
    failed_notifications: int
