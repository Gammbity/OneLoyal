from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.common.pagination import PaginationParams
from app.common.redaction import redact_sensitive_data
from app.core.errors import NotFoundError
from app.modules.audit.context import AuditContext
from app.modules.events.models import DomainEvent, DomainEventStatus


class DomainEventService:
    async def emit(
        self,
        session: AsyncSession,
        *,
        company_id: UUID | None,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID | None = None,
        customer_id: UUID | None = None,
        campaign_id: UUID | None = None,
        gift_tier_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        actor_customer_id: UUID | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        payload_json: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
        context: AuditContext | None = None,
    ) -> DomainEvent:
        event = self._build_event(
            company_id=company_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            customer_id=customer_id,
            campaign_id=campaign_id,
            gift_tier_id=gift_tier_id,
            actor_user_id=actor_user_id,
            actor_customer_id=actor_customer_id,
            correlation_id=correlation_id,
            request_id=request_id,
            payload_json=payload_json,
            occurred_at=occurred_at,
            context=context,
        )
        session.add(event)
        await session.flush()
        return event

    async def emit_many(
        self,
        session: AsyncSession,
        *,
        events: list[dict[str, Any]],
        context: AuditContext | None = None,
    ) -> list[DomainEvent]:
        records: list[DomainEvent] = []
        for event in events:
            records.append(
                self._build_event(
                    company_id=event.get("company_id"),
                    event_type=event["event_type"],
                    aggregate_type=event["aggregate_type"],
                    aggregate_id=event.get("aggregate_id"),
                    customer_id=event.get("customer_id"),
                    campaign_id=event.get("campaign_id"),
                    gift_tier_id=event.get("gift_tier_id"),
                    actor_user_id=event.get("actor_user_id"),
                    actor_customer_id=event.get("actor_customer_id"),
                    correlation_id=event.get("correlation_id"),
                    request_id=event.get("request_id"),
                    payload_json=event.get("payload_json"),
                    occurred_at=event.get("occurred_at"),
                    context=context,
                )
            )
        session.add_all(records)
        await session.flush()
        return records

    def _build_event(
        self,
        *,
        company_id: UUID | None,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID | None,
        customer_id: UUID | None,
        campaign_id: UUID | None,
        gift_tier_id: UUID | None,
        actor_user_id: UUID | None,
        actor_customer_id: UUID | None,
        correlation_id: str | None,
        request_id: str | None,
        payload_json: dict[str, Any] | None,
        occurred_at: datetime | None,
        context: AuditContext | None,
    ) -> DomainEvent:
        return DomainEvent(
            company_id=company_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            customer_id=customer_id,
            campaign_id=campaign_id,
            gift_tier_id=gift_tier_id,
            actor_user_id=actor_user_id or (context.actor_user_id if context else None),
            actor_customer_id=actor_customer_id
            or (context.actor_customer_id if context else None),
            correlation_id=correlation_id,
            request_id=request_id or (context.request_id if context else None),
            payload_json=redact_sensitive_data(payload_json or {}),
            status=DomainEventStatus.PENDING.value,
            attempts=0,
            last_error=None,
            occurred_at=occurred_at or utc_now(),
        )

    async def list_events(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        event_type: str | None = None,
        status: str | None = None,
        aggregate_type: str | None = None,
        customer_id: UUID | None = None,
        campaign_id: UUID | None = None,
        occurred_at_from: datetime | None = None,
        occurred_at_to: datetime | None = None,
    ) -> tuple[list[DomainEvent], int]:
        filters = [DomainEvent.company_id == company_id]
        if event_type is not None:
            filters.append(DomainEvent.event_type == event_type)
        if status is not None:
            filters.append(DomainEvent.status == status)
        if aggregate_type is not None:
            filters.append(DomainEvent.aggregate_type == aggregate_type)
        if customer_id is not None:
            filters.append(DomainEvent.customer_id == customer_id)
        if campaign_id is not None:
            filters.append(DomainEvent.campaign_id == campaign_id)
        if occurred_at_from is not None:
            filters.append(DomainEvent.occurred_at >= occurred_at_from)
        if occurred_at_to is not None:
            filters.append(DomainEvent.occurred_at <= occurred_at_to)

        query: Select[tuple[DomainEvent]] = select(DomainEvent).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(
                select(DomainEvent.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            query.order_by(DomainEvent.occurred_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_event(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        event_id: UUID,
    ) -> DomainEvent:
        result = await session.execute(
            select(DomainEvent).where(
                DomainEvent.id == event_id,
                DomainEvent.company_id == company_id,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise NotFoundError("Domain event not found.")
        return event

    async def mark_processing(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        event_id: UUID,
    ) -> DomainEvent:
        event = await self.get_event(session, company_id=company_id, event_id=event_id)
        event.status = DomainEventStatus.PROCESSING.value
        event.attempts += 1
        await session.flush()
        return event

    async def mark_processed(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        event_id: UUID,
    ) -> DomainEvent:
        event = await self.get_event(session, company_id=company_id, event_id=event_id)
        event.status = DomainEventStatus.PROCESSED.value
        event.last_error = None
        event.processed_at = utc_now()
        await session.flush()
        return event

    async def mark_failed(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        event_id: UUID,
        error: str | None = None,
    ) -> DomainEvent:
        event = await self.get_event(session, company_id=company_id, event_id=event_id)
        event.status = DomainEventStatus.FAILED.value
        if error:
            event.last_error = error
        await session.flush()
        return event


domain_event_service = DomainEventService()
