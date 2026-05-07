import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.common.pagination import PaginationParams
from app.core.errors import NotFoundError, ValidationAppError
from app.modules.customers.models import Customer
from app.modules.events.models import DomainEvent, DomainEventStatus
from app.modules.notifications.models import (
    NotificationChannel,
    NotificationEvent,
    NotificationEventStatus,
    NotificationRecipientType,
    NotificationRule,
    NotificationTemplate,
)
from app.modules.notifications.schemas import (
    NotificationRuleCreateRequest,
    NotificationRuleUpdateRequest,
    NotificationTemplateCreateRequest,
    NotificationTemplateUpdateRequest,
    ProcessPendingDomainEventsResponse,
    ProcessPendingNotificationsResponse,
)
from app.modules.users.models import User, UserRole, UserStatus

PLACEHOLDER_PATTERN = re.compile(r"{([a-zA-Z0-9_.]+)}")


@dataclass(frozen=True)
class NotificationRecipient:
    customer_id: UUID | None
    user_id: UUID | None
    identifier: str | None


class TemplateRenderError(ValueError):
    pass


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _event_context(event: DomainEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
        "customer_id": str(event.customer_id) if event.customer_id else None,
        "campaign_id": str(event.campaign_id) if event.campaign_id else None,
        "gift_tier_id": str(event.gift_tier_id) if event.gift_tier_id else None,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "actor_customer_id": str(event.actor_customer_id)
        if event.actor_customer_id
        else None,
        "payload": event.payload_json or {},
    }


def _resolve_path(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(path)
    return current


def _render_template(template: str | None, context: dict[str, Any]) -> str | None:
    if template is None:
        return None

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        try:
            value = _resolve_path(context, key)
        except KeyError as exc:
            raise TemplateRenderError(f"Missing template value: {key}") from exc
        return "" if value is None else str(value)

    return PLACEHOLDER_PATTERN.sub(replace, template)


def _conditions_match(condition_json: dict[str, Any], context: dict[str, Any]) -> bool:
    for key, expected in condition_json.items():
        try:
            actual = _resolve_path(context, key)
        except KeyError:
            return False
        if actual != expected:
            return False
    return True


class NotificationService:
    async def create_template(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: NotificationTemplateCreateRequest,
    ) -> NotificationTemplate:
        template = NotificationTemplate(
            company_id=company_id,
            name=data.name.strip(),
            channel=data.channel.value,
            subject_template=data.subject_template,
            body_template=data.body_template,
            locale=data.locale.strip().lower(),
            is_active=data.is_active,
            metadata_json=data.metadata_json or {},
        )
        session.add(template)
        await session.flush()
        return template

    async def list_templates(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        channel: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[NotificationTemplate], int]:
        filters = [NotificationTemplate.company_id == company_id]
        if channel is not None:
            filters.append(NotificationTemplate.channel == channel)
        if is_active is not None:
            filters.append(NotificationTemplate.is_active.is_(is_active))

        total_result = await session.execute(
            select(func.count()).select_from(
                select(NotificationTemplate.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            select(NotificationTemplate)
            .where(*filters)
            .order_by(NotificationTemplate.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_template(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        template_id: UUID,
    ) -> NotificationTemplate:
        result = await session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.id == template_id,
                NotificationTemplate.company_id == company_id,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise NotFoundError("Notification template not found.")
        return template

    async def update_template(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        template_id: UUID,
        data: NotificationTemplateUpdateRequest,
    ) -> NotificationTemplate:
        template = await self.get_template(
            session,
            company_id=company_id,
            template_id=template_id,
        )
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "channel" and value is not None:
                value = value.value
            if field == "name" and value is not None:
                value = value.strip()
            if field == "locale" and value is not None:
                value = value.strip().lower()
            if field == "metadata_json" and value is None:
                value = {}
            setattr(template, field, value)
        await session.flush()
        return template

    async def create_rule(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: NotificationRuleCreateRequest,
    ) -> NotificationRule:
        template = await self.get_template(
            session,
            company_id=company_id,
            template_id=data.template_id,
        )
        channel = data.channel.value if data.channel is not None else template.channel
        self._ensure_channel_matches_template(channel, template)
        rule = NotificationRule(
            company_id=company_id,
            event_type=data.event_type.strip(),
            template_id=template.id,
            channel=channel,
            recipient_type=data.recipient_type.value,
            condition_json=data.condition_json or {},
            is_active=data.is_active,
            metadata_json=data.metadata_json or {},
        )
        session.add(rule)
        await session.flush()
        return rule

    async def list_rules(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        event_type: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[NotificationRule], int]:
        filters = [NotificationRule.company_id == company_id]
        if event_type is not None:
            filters.append(NotificationRule.event_type == event_type)
        if is_active is not None:
            filters.append(NotificationRule.is_active.is_(is_active))

        total_result = await session.execute(
            select(func.count()).select_from(
                select(NotificationRule.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            select(NotificationRule)
            .where(*filters)
            .order_by(NotificationRule.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_rule(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        rule_id: UUID,
    ) -> NotificationRule:
        result = await session.execute(
            select(NotificationRule).where(
                NotificationRule.id == rule_id,
                NotificationRule.company_id == company_id,
            )
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise NotFoundError("Notification rule not found.")
        return rule

    async def update_rule(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        rule_id: UUID,
        data: NotificationRuleUpdateRequest,
    ) -> NotificationRule:
        rule = await self.get_rule(session, company_id=company_id, rule_id=rule_id)
        update_data = data.model_dump(exclude_unset=True)
        new_template = await self.get_template(
            session,
            company_id=company_id,
            template_id=rule.template_id,
        )
        if "template_id" in update_data and update_data["template_id"] is not None:
            new_template = await self.get_template(
                session,
                company_id=company_id,
                template_id=update_data["template_id"],
            )
        new_channel = update_data.get("channel")
        channel = _enum_value(new_channel) if new_channel is not None else rule.channel
        self._ensure_channel_matches_template(channel, new_template)

        for field, value in update_data.items():
            if field == "event_type" and value is not None:
                value = value.strip()
            if field in {"channel", "recipient_type"} and value is not None:
                value = value.value
            if field in {"condition_json", "metadata_json"} and value is None:
                value = {}
            setattr(rule, field, value)
        await session.flush()
        return rule

    def _ensure_channel_matches_template(
        self,
        channel: str,
        template: NotificationTemplate,
    ) -> None:
        if channel != template.channel:
            raise ValidationAppError(
                "Notification rule channel must match its template channel.",
                details={"field": "channel"},
            )

    async def list_notification_events(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        status: str | None = None,
        channel: str | None = None,
        domain_event_id: UUID | None = None,
        customer_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[NotificationEvent], int]:
        filters = [NotificationEvent.company_id == company_id]
        if status is not None:
            filters.append(NotificationEvent.status == status)
        if channel is not None:
            filters.append(NotificationEvent.channel == channel)
        if domain_event_id is not None:
            filters.append(NotificationEvent.domain_event_id == domain_event_id)
        if customer_id is not None:
            filters.append(NotificationEvent.customer_id == customer_id)
        if user_id is not None:
            filters.append(NotificationEvent.user_id == user_id)

        total_result = await session.execute(
            select(func.count()).select_from(
                select(NotificationEvent.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            select(NotificationEvent)
            .where(*filters)
            .order_by(NotificationEvent.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_notification_event(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        notification_event_id: UUID,
    ) -> NotificationEvent:
        result = await session.execute(
            select(NotificationEvent).where(
                NotificationEvent.id == notification_event_id,
                NotificationEvent.company_id == company_id,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise NotFoundError("Notification event not found.")
        return event

    async def mark_notification_event_sent(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        notification_event_id: UUID,
    ) -> NotificationEvent:
        event = await self.get_notification_event(
            session,
            company_id=company_id,
            notification_event_id=notification_event_id,
        )
        event.status = NotificationEventStatus.SENT.value
        event.attempts += 1
        event.last_error = None
        event.skipped_reason = None
        event.sent_at = utc_now()
        await session.flush()
        return event

    async def mark_notification_event_failed(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        notification_event_id: UUID,
        error: str | None = None,
    ) -> NotificationEvent:
        event = await self.get_notification_event(
            session,
            company_id=company_id,
            notification_event_id=notification_event_id,
        )
        event.status = NotificationEventStatus.FAILED.value
        event.attempts += 1
        event.last_error = error
        event.failed_at = utc_now()
        await session.flush()
        return event

    async def mark_notification_event_skipped(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        notification_event_id: UUID,
        skipped_reason: str | None = None,
    ) -> NotificationEvent:
        event = await self.get_notification_event(
            session,
            company_id=company_id,
            notification_event_id=notification_event_id,
        )
        event.status = NotificationEventStatus.SKIPPED.value
        event.skipped_reason = skipped_reason
        event.last_error = None
        await session.flush()
        return event

    async def process_pending_domain_events(
        self,
        session: AsyncSession,
        *,
        company_id: UUID | None = None,
        limit: int = 100,
    ) -> ProcessPendingDomainEventsResponse:
        filters = [DomainEvent.status == DomainEventStatus.PENDING.value]
        if company_id is not None:
            filters.append(DomainEvent.company_id == company_id)
        result = await session.execute(
            select(DomainEvent)
            .where(*filters)
            .order_by(DomainEvent.occurred_at.asc())
            .limit(limit)
        )
        events = list(result.scalars().all())
        stats = {
            "checked_events": len(events),
            "processed_events": 0,
            "failed_events": 0,
            "events_without_company": 0,
            "events_without_rules": 0,
            "generated_notifications": 0,
            "skipped_notifications": 0,
            "failed_notifications": 0,
        }

        for event in events:
            try:
                await self._process_domain_event(session, event=event, stats=stats)
                stats["processed_events"] += 1
            except Exception as exc:
                event.status = DomainEventStatus.FAILED.value
                event.last_error = str(exc) or exc.__class__.__name__
                stats["failed_events"] += 1
            await session.flush()

        return ProcessPendingDomainEventsResponse(**stats)

    async def _process_domain_event(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        stats: dict[str, int],
    ) -> None:
        event.status = DomainEventStatus.PROCESSING.value
        event.attempts += 1
        await session.flush()

        if event.company_id is None:
            stats["events_without_company"] += 1
            self._mark_domain_event_processed(event)
            return

        rules = await self._rules_for_event(session, event=event)
        if not rules:
            stats["events_without_rules"] += 1
            self._mark_domain_event_processed(event)
            return

        context = _event_context(event)
        for rule in rules:
            await self._process_rule_for_event(
                session,
                event=event,
                rule=rule,
                context=context,
                stats=stats,
            )
        self._mark_domain_event_processed(event)

    def _mark_domain_event_processed(self, event: DomainEvent) -> None:
        event.status = DomainEventStatus.PROCESSED.value
        event.last_error = None
        event.processed_at = utc_now()

    async def _rules_for_event(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
    ) -> list[NotificationRule]:
        result = await session.execute(
            select(NotificationRule).where(
                NotificationRule.company_id == event.company_id,
                NotificationRule.event_type == event.event_type,
                NotificationRule.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _process_rule_for_event(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        rule: NotificationRule,
        context: dict[str, Any],
        stats: dict[str, int],
    ) -> None:
        template = await self.get_template(
            session,
            company_id=rule.company_id,
            template_id=rule.template_id,
        )
        if not template.is_active:
            await self._create_skipped_event_once(
                session,
                event=event,
                rule=rule,
                template=template,
                reason="template_inactive",
            )
            stats["skipped_notifications"] += 1
            return
        if not _conditions_match(rule.condition_json or {}, context):
            await self._create_skipped_event_once(
                session,
                event=event,
                rule=rule,
                template=template,
                reason="condition_not_matched",
            )
            stats["skipped_notifications"] += 1
            return

        try:
            subject = _render_template(template.subject_template, context)
            body = _render_template(template.body_template, context)
        except TemplateRenderError as exc:
            await self._create_failed_event_once(
                session,
                event=event,
                rule=rule,
                template=template,
                error=str(exc),
            )
            stats["failed_notifications"] += 1
            return

        recipients = await self._recipients_for_event(
            session,
            event=event,
            rule=rule,
        )
        if not recipients:
            await self._create_skipped_event_once(
                session,
                event=event,
                rule=rule,
                template=template,
                reason="recipient_unavailable",
            )
            stats["skipped_notifications"] += 1
            return

        for recipient in recipients:
            created = await self._create_pending_event_once(
                session,
                event=event,
                rule=rule,
                template=template,
                recipient=recipient,
                subject=subject,
                body=body,
            )
            if created:
                stats["generated_notifications"] += 1

    async def _recipients_for_event(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        rule: NotificationRule,
    ) -> list[NotificationRecipient]:
        recipient_type = rule.recipient_type
        if recipient_type == NotificationRecipientType.CUSTOMER.value:
            customer_id = event.customer_id or event.actor_customer_id
            if customer_id is None:
                return []
            customer = await session.get(Customer, customer_id)
            if customer is None or customer.company_id != event.company_id:
                return []
            identifier = self._customer_identifier(customer, rule.channel)
            return [
                NotificationRecipient(
                    customer_id=customer.id,
                    user_id=None,
                    identifier=identifier,
                )
            ] if identifier else []

        if recipient_type == NotificationRecipientType.COMPANY_ADMIN.value:
            result = await session.execute(
                select(User).where(
                    User.company_id == event.company_id,
                    User.role.in_({UserRole.OWNER.value, UserRole.ADMIN.value}),
                    User.status == UserStatus.ACTIVE.value,
                )
            )
            users = list(result.scalars().all())
            return [
                NotificationRecipient(
                    customer_id=None,
                    user_id=user.id,
                    identifier=self._user_identifier(user, rule.channel),
                )
                for user in users
                if self._user_identifier(user, rule.channel)
            ]

        if recipient_type == NotificationRecipientType.SALES_MANAGER.value:
            if event.customer_id is None:
                return []
            from app.modules.customers.models import CustomerAssignment

            result = await session.execute(
                select(User)
                .join(
                    CustomerAssignment,
                    CustomerAssignment.sales_manager_user_id == User.id,
                )
                .where(
                    CustomerAssignment.company_id == event.company_id,
                    CustomerAssignment.customer_id == event.customer_id,
                    User.status == UserStatus.ACTIVE.value,
                )
            )
            users = list(result.scalars().all())
            return [
                NotificationRecipient(
                    customer_id=None,
                    user_id=user.id,
                    identifier=self._user_identifier(user, rule.channel),
                )
                for user in users
                if self._user_identifier(user, rule.channel)
            ]

        return []

    def _customer_identifier(self, customer: Customer, channel: str) -> str | None:
        if channel == NotificationChannel.EMAIL.value:
            return customer.email
        if channel in {
            NotificationChannel.SMS.value,
            NotificationChannel.TELEGRAM.value,
        }:
            return customer.phone
        if channel == NotificationChannel.IN_APP.value:
            return str(customer.id)
        return None

    def _user_identifier(self, user: User, channel: str) -> str | None:
        if channel == NotificationChannel.EMAIL.value:
            return user.email
        if channel == NotificationChannel.IN_APP.value:
            return str(user.id)
        return None

    async def _notification_exists(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        rule: NotificationRule,
        recipient: NotificationRecipient | None = None,
    ) -> bool:
        filters = [
            NotificationEvent.domain_event_id == event.id,
            NotificationEvent.notification_rule_id == rule.id,
        ]
        if recipient is not None:
            if recipient.customer_id is None:
                filters.append(NotificationEvent.customer_id.is_(None))
            else:
                filters.append(NotificationEvent.customer_id == recipient.customer_id)
            if recipient.user_id is None:
                filters.append(NotificationEvent.user_id.is_(None))
            else:
                filters.append(NotificationEvent.user_id == recipient.user_id)
        result = await session.execute(select(NotificationEvent.id).where(*filters))
        return result.scalar_one_or_none() is not None

    async def _create_pending_event_once(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        rule: NotificationRule,
        template: NotificationTemplate,
        recipient: NotificationRecipient,
        subject: str | None,
        body: str | None,
    ) -> bool:
        if await self._notification_exists(
            session,
            event=event,
            rule=rule,
            recipient=recipient,
        ):
            return False
        session.add(
            NotificationEvent(
                company_id=rule.company_id,
                domain_event_id=event.id,
                notification_rule_id=rule.id,
                notification_template_id=template.id,
                channel=rule.channel,
                recipient_type=rule.recipient_type,
                customer_id=recipient.customer_id,
                user_id=recipient.user_id,
                recipient_identifier=recipient.identifier,
                subject=subject,
                body=body,
                status=NotificationEventStatus.PENDING.value,
                scheduled_at=utc_now(),
            )
        )
        await session.flush()
        return True

    async def _create_skipped_event_once(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        rule: NotificationRule,
        template: NotificationTemplate,
        reason: str,
    ) -> bool:
        if await self._notification_exists(session, event=event, rule=rule):
            return False
        session.add(
            NotificationEvent(
                company_id=rule.company_id,
                domain_event_id=event.id,
                notification_rule_id=rule.id,
                notification_template_id=template.id,
                channel=rule.channel,
                recipient_type=rule.recipient_type,
                status=NotificationEventStatus.SKIPPED.value,
                skipped_reason=reason,
            )
        )
        await session.flush()
        return True

    async def _create_failed_event_once(
        self,
        session: AsyncSession,
        *,
        event: DomainEvent,
        rule: NotificationRule,
        template: NotificationTemplate,
        error: str,
    ) -> bool:
        if await self._notification_exists(session, event=event, rule=rule):
            return False
        session.add(
            NotificationEvent(
                company_id=rule.company_id,
                domain_event_id=event.id,
                notification_rule_id=rule.id,
                notification_template_id=template.id,
                channel=rule.channel,
                recipient_type=rule.recipient_type,
                status=NotificationEventStatus.FAILED.value,
                last_error=error,
                failed_at=utc_now(),
            )
        )
        await session.flush()
        return True

    async def send_pending_notifications(
        self,
        session: AsyncSession,
        *,
        company_id: UUID | None = None,
        limit: int = 100,
    ) -> ProcessPendingNotificationsResponse:
        filters = [NotificationEvent.status == NotificationEventStatus.PENDING.value]
        if company_id is not None:
            filters.append(NotificationEvent.company_id == company_id)

        result = await session.execute(
            select(NotificationEvent)
            .where(*filters)
            .order_by(NotificationEvent.created_at.asc())
            .limit(limit)
        )
        notifications = list(result.scalars().all())
        stats = {
            "checked_notifications": len(notifications),
            "sent_notifications": 0,
            "failed_notifications": 0,
        }

        for notification in notifications:
            notification.attempts += 1
            try:
                await self._send_notification(session, notification=notification)
                stats["sent_notifications"] += 1
            except Exception as exc:
                notification.status = NotificationEventStatus.FAILED.value
                notification.last_error = str(exc) or exc.__class__.__name__
                notification.failed_at = utc_now()
                stats["failed_notifications"] += 1
            await session.flush()

        return ProcessPendingNotificationsResponse(**stats)

    async def _send_notification(
        self,
        session: AsyncSession,
        *,
        notification: NotificationEvent,
    ) -> None:
        # In a real system, here we would call the actual provider (Email, SMS, etc.)
        # For now, we simulate success for demonstration purposes.
        # To simulate failure for testing, check recipient_identifier.
        if notification.recipient_identifier == "fail-me@example.com":
            raise ValueError("Simulated delivery failure")

        notification.status = NotificationEventStatus.SENT.value
        notification.sent_at = utc_now()
        notification.last_error = None
        notification.failed_at = None
        await session.flush()


notification_service = NotificationService()
