from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.core.security import hash_password
from app.modules.audit.models import AuditActorType, AuditLog
from app.modules.billing.models import (
    CompanySubscription,
    CompanyUsageLimit,
    Plan,
    SubscriptionStatus,
    UsageCounter,
)
from app.modules.campaigns.models import Campaign, CampaignStatus, GiftTier, StockTrackingMode
from app.modules.claims.models import RewardClaim, RewardClaimStatus
from app.modules.companies.models import Company, CompanySettings, CompanyStatus
from app.modules.customers.models import (
    Customer,
    CustomerAssignment,
    CustomerExternalRef,
    CustomerStatus,
)
from app.modules.events.models import DomainEvent, DomainEventStatus
from app.modules.imports.models import ImportBatch, ImportBatchStatus, ImportRow, ImportRowStatus
from app.modules.integrations.models import (
    Integration,
    IntegrationCredential,
    IntegrationStatus,
)
from app.modules.notifications.models import (
    NotificationChannel,
    NotificationEvent,
    NotificationEventStatus,
    NotificationRecipientType,
    NotificationRule,
    NotificationTemplate,
)
from app.modules.sales.models import (
    PaymentStatus,
    SaleDocumentKind,
    SaleDocumentStatus,
    SaleRecord,
    SaleSourceType,
)
from app.modules.sync.models import SyncError, SyncErrorSeverity, SyncRun, SyncRunStatus, SyncType
from app.modules.users.models import User, UserRole, UserStatus


async def seed_sample_data(session: AsyncSession) -> dict[str, Any]:
    now = utc_now()

    active_company = Company(
        name="Acme Active LLC",
        slug="acme-active",
        status=CompanyStatus.ACTIVE.value,
        base_currency="UZS",
    )
    active_company.settings = CompanySettings(
        fiscal_year_start_month=1,
        fiscal_year_start_day=1,
        sync_frequency_minutes=30,
        reward_claim_enabled_default=True,
    )
    suspended_company = Company(
        name="Acme Suspended LLC",
        slug="acme-suspended",
        status=CompanyStatus.SUSPENDED.value,
        base_currency="UZS",
    )
    archived_company = Company(
        name="Acme Archived LLC",
        slug="acme-archived",
        status=CompanyStatus.ARCHIVED.value,
        base_currency="UZS",
    )
    suspended_company.settings = CompanySettings()
    archived_company.settings = CompanySettings()

    plan = Plan(
        code="starter",
        name="Starter",
        limits_json={"users": 10, "campaigns": 5},
        features_json={"sync": True, "notifications": True},
    )

    session.add_all([active_company, suspended_company, archived_company, plan])
    await session.flush()

    users = {
        "owner": User(
            company_id=active_company.id,
            email="owner@acme.example",
            full_name="Acme Owner",
            password_hash=hash_password("super-secret-password"),
            role=UserRole.OWNER.value,
            status=UserStatus.ACTIVE.value,
        ),
        "admin": User(
            company_id=active_company.id,
            email="admin@acme.example",
            full_name="Acme Admin",
            password_hash=hash_password("super-secret-password"),
            role=UserRole.ADMIN.value,
            status=UserStatus.INVITED.value,
        ),
        "sales_manager": User(
            company_id=active_company.id,
            email="sales@acme.example",
            full_name="Acme Sales Manager",
            password_hash=hash_password("super-secret-password"),
            role=UserRole.SALES_MANAGER.value,
            status=UserStatus.DISABLED.value,
        ),
        "platform_admin": User(
            company_id=None,
            email="platform@acme.example",
            full_name="Platform Admin",
            password_hash=hash_password("super-secret-password"),
            role=UserRole.PLATFORM_ADMIN.value,
            status=UserStatus.ACTIVE.value,
        ),
    }
    session.add_all(users.values())
    await session.flush()

    customers = {
        "active": Customer(
            company_id=active_company.id,
            name="Active Customer",
            phone="+998901000001",
            email="active.customer@example.com",
            tax_id="TAX-ACTIVE",
            status=CustomerStatus.ACTIVE.value,
            metadata_json={"segment": "vip"},
        ),
        "archived": Customer(
            company_id=active_company.id,
            name="Archived Customer",
            phone="+998901000002",
            email="archived.customer@example.com",
            tax_id="TAX-ARCHIVED",
            status=CustomerStatus.ARCHIVED.value,
            metadata_json={"segment": "inactive"},
        ),
        "blocked": Customer(
            company_id=active_company.id,
            name="Blocked Customer",
            phone="+998901000003",
            email="blocked.customer@example.com",
            tax_id="TAX-BLOCKED",
            status=CustomerStatus.BLOCKED.value,
            metadata_json={"segment": "restricted"},
        ),
    }
    session.add_all(customers.values())
    await session.flush()

    campaigns = {
        "draft": Campaign(
            company_id=active_company.id,
            title="Draft Campaign",
            description="Draft state campaign",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=CampaignStatus.DRAFT.value,
            currency="UZS",
            allow_claims=True,
        ),
        "active": Campaign(
            company_id=active_company.id,
            title="Active Campaign",
            description="Active state campaign",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=CampaignStatus.ACTIVE.value,
            currency="UZS",
            allow_claims=True,
        ),
        "paused": Campaign(
            company_id=active_company.id,
            title="Paused Campaign",
            description="Paused state campaign",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=CampaignStatus.PAUSED.value,
            currency="UZS",
            allow_claims=True,
        ),
        "completed": Campaign(
            company_id=active_company.id,
            title="Completed Campaign",
            description="Completed state campaign",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=CampaignStatus.COMPLETED.value,
            currency="UZS",
            allow_claims=True,
        ),
        "archived": Campaign(
            company_id=active_company.id,
            title="Archived Campaign",
            description="Archived state campaign",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=CampaignStatus.ARCHIVED.value,
            currency="UZS",
            allow_claims=False,
        ),
    }
    session.add_all(campaigns.values())
    await session.flush()

    gift_tiers = {
        "none": GiftTier(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            title="No Stock Tier",
            required_amount_minor=10_000_000,
            currency="UZS",
            stock_tracking_mode=StockTrackingMode.NONE.value,
            stock_quantity=None,
        ),
        "soft": GiftTier(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            title="Soft Stock Tier",
            required_amount_minor=20_000_000,
            currency="UZS",
            stock_tracking_mode=StockTrackingMode.SOFT.value,
            stock_quantity=10,
        ),
        "strict": GiftTier(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            title="Strict Stock Tier",
            required_amount_minor=30_000_000,
            currency="UZS",
            stock_tracking_mode=StockTrackingMode.STRICT.value,
            stock_quantity=5,
        ),
    }
    session.add_all(gift_tiers.values())
    await session.flush()

    integrations = {
        "draft": Integration(
            company_id=active_company.id,
            provider="fake",
            name="Draft Integration",
            status=IntegrationStatus.DRAFT.value,
            settings_json={"mode": "draft"},
        ),
        "active": Integration(
            company_id=active_company.id,
            provider="fake",
            name="Active Integration",
            status=IntegrationStatus.ACTIVE.value,
            settings_json={"mode": "active"},
        ),
        "disabled": Integration(
            company_id=active_company.id,
            provider="fake",
            name="Disabled Integration",
            status=IntegrationStatus.DISABLED.value,
            settings_json={"mode": "disabled"},
        ),
        "error": Integration(
            company_id=active_company.id,
            provider="fake",
            name="Errored Integration",
            status=IntegrationStatus.ERROR.value,
            settings_json={"mode": "error"},
        ),
    }
    session.add_all(integrations.values())
    await session.flush()

    integration_credentials = [
        IntegrationCredential(
            company_id=active_company.id,
            integration_id=integrations["active"].id,
            encrypted_credentials="encrypted:active",
            credential_version=1,
            is_active=True,
        ),
        IntegrationCredential(
            company_id=active_company.id,
            integration_id=integrations["disabled"].id,
            encrypted_credentials="encrypted:disabled",
            credential_version=1,
            is_active=False,
        ),
    ]
    session.add_all(integration_credentials)
    await session.flush()

    customer_external_ref = CustomerExternalRef(
        company_id=active_company.id,
        customer_id=customers["active"].id,
        integration_id=integrations["active"].id,
        provider="fake",
        external_id="cust-active-1",
        external_name="Active Customer",
        external_phone="+998901000001",
        external_email="active.customer@example.com",
        raw_payload_json={"source": "fixture"},
        last_seen_at=now,
    )
    customer_assignment = CustomerAssignment(
        company_id=active_company.id,
        customer_id=customers["active"].id,
        sales_manager_user_id=users["sales_manager"].id,
    )

    session.add_all([customer_external_ref, customer_assignment])
    await session.flush()

    sales = {
        "sale": SaleRecord(
            company_id=active_company.id,
            customer_id=customers["active"].id,
            integration_id=integrations["active"].id,
            source_type=SaleSourceType.MANUAL.value,
            source_key="sale-1",
            provider="manual",
            document_kind=SaleDocumentKind.SALE.value,
            external_document_number="INV-001",
            document_date=date(2026, 6, 1),
            effective_date=date(2026, 6, 1),
            gross_amount_minor=10_000_000,
            amount_sign=1,
            currency="UZS",
            currency_scale=0,
            payment_status=PaymentStatus.PAID.value,
            document_status=SaleDocumentStatus.POSTED.value,
            raw_payload_json={"kind": "sale"},
        ),
        "return": SaleRecord(
            company_id=active_company.id,
            customer_id=customers["active"].id,
            integration_id=integrations["active"].id,
            source_type=SaleSourceType.MANUAL.value,
            source_key="sale-2",
            provider="manual",
            document_kind=SaleDocumentKind.RETURN.value,
            external_document_number="INV-002",
            document_date=date(2026, 6, 2),
            effective_date=date(2026, 6, 2),
            gross_amount_minor=5_000_000,
            amount_sign=-1,
            currency="UZS",
            currency_scale=0,
            payment_status=PaymentStatus.UNPAID.value,
            document_status=SaleDocumentStatus.DRAFT.value,
            raw_payload_json={"kind": "return"},
        ),
        "refund": SaleRecord(
            company_id=active_company.id,
            customer_id=customers["active"].id,
            source_type=SaleSourceType.CSV.value,
            source_key="sale-3",
            provider="csv",
            document_kind=SaleDocumentKind.REFUND.value,
            external_document_number="INV-003",
            document_date=date(2026, 6, 3),
            effective_date=date(2026, 6, 3),
            gross_amount_minor=2_500_000,
            amount_sign=-1,
            currency="UZS",
            currency_scale=0,
            payment_status=PaymentStatus.PARTIAL.value,
            document_status=SaleDocumentStatus.CANCELLED.value,
            raw_payload_json={"kind": "refund"},
        ),
        "adjustment": SaleRecord(
            company_id=active_company.id,
            customer_id=customers["active"].id,
            source_type=SaleSourceType.ERP.value,
            source_key="sale-4",
            provider="erp",
            document_kind=SaleDocumentKind.ADJUSTMENT.value,
            external_document_number="INV-004",
            document_date=date(2026, 6, 4),
            effective_date=date(2026, 6, 4),
            gross_amount_minor=1_500_000,
            amount_sign=1,
            currency="UZS",
            currency_scale=0,
            payment_status=PaymentStatus.OVERPAID.value,
            document_status=SaleDocumentStatus.DELETED.value,
            raw_payload_json={"kind": "adjustment"},
        ),
        "correction": SaleRecord(
            company_id=active_company.id,
            customer_id=customers["active"].id,
            source_type=SaleSourceType.MANUAL.value,
            source_key="sale-5",
            provider="manual",
            document_kind=SaleDocumentKind.CORRECTION.value,
            external_document_number="INV-005",
            document_date=date(2026, 6, 5),
            effective_date=date(2026, 6, 5),
            gross_amount_minor=750_000,
            amount_sign=1,
            currency="UZS",
            currency_scale=0,
            payment_status=PaymentStatus.UNKNOWN.value,
            document_status=SaleDocumentStatus.UNKNOWN.value,
            raw_payload_json={"kind": "correction"},
        ),
    }
    session.add_all(sales.values())
    await session.flush()

    domain_events = {
        "pending": DomainEvent(
            company_id=active_company.id,
            event_type="customer.created",
            aggregate_type="customer",
            aggregate_id=customers["active"].id,
            customer_id=customers["active"].id,
            status=DomainEventStatus.PENDING.value,
            payload_json={"status": "pending"},
        ),
        "processing": DomainEvent(
            company_id=active_company.id,
            event_type="customer.updated",
            aggregate_type="customer",
            aggregate_id=customers["blocked"].id,
            customer_id=customers["blocked"].id,
            status=DomainEventStatus.PROCESSING.value,
            payload_json={"status": "processing"},
        ),
        "processed": DomainEvent(
            company_id=active_company.id,
            event_type="campaign.created",
            aggregate_type="campaign",
            aggregate_id=campaigns["active"].id,
            campaign_id=campaigns["active"].id,
            status=DomainEventStatus.PROCESSED.value,
            payload_json={"status": "processed"},
        ),
        "failed": DomainEvent(
            company_id=active_company.id,
            event_type="reward_claim.created",
            aggregate_type="reward_claim",
            aggregate_id=None,
            status=DomainEventStatus.FAILED.value,
            last_error="fixture failure",
            payload_json={"status": "failed"},
        ),
    }
    session.add_all(domain_events.values())
    await session.flush()

    template = NotificationTemplate(
        company_id=active_company.id,
        name="Welcome",
        channel=NotificationChannel.EMAIL.value,
        subject_template="Welcome {payload.name}",
        body_template="Hello {payload.name}",
        locale="en",
        metadata_json={"fixture": True},
    )
    session.add(template)
    await session.flush()

    rule = NotificationRule(
        company_id=active_company.id,
        event_type="customer.created",
        template_id=template.id,
        channel=NotificationChannel.EMAIL.value,
        recipient_type=NotificationRecipientType.CUSTOMER.value,
        condition_json={},
        metadata_json={"fixture": True},
    )
    session.add(rule)
    await session.flush()

    notification_events = {
        "pending": NotificationEvent(
            company_id=active_company.id,
            domain_event_id=domain_events["pending"].id,
            notification_rule_id=rule.id,
            notification_template_id=template.id,
            channel=NotificationChannel.EMAIL.value,
            recipient_type=NotificationRecipientType.CUSTOMER.value,
            customer_id=customers["active"].id,
            recipient_identifier=customers["active"].email,
            subject="Pending notification",
            body="Pending body",
            status=NotificationEventStatus.PENDING.value,
        ),
        "sent": NotificationEvent(
            company_id=active_company.id,
            domain_event_id=domain_events["processing"].id,
            notification_rule_id=rule.id,
            notification_template_id=template.id,
            channel=NotificationChannel.EMAIL.value,
            recipient_type=NotificationRecipientType.CUSTOMER.value,
            customer_id=customers["active"].id,
            recipient_identifier=customers["active"].email,
            subject="Sent notification",
            body="Sent body",
            status=NotificationEventStatus.SENT.value,
        ),
        "failed": NotificationEvent(
            company_id=active_company.id,
            domain_event_id=domain_events["processed"].id,
            notification_rule_id=rule.id,
            notification_template_id=template.id,
            channel=NotificationChannel.EMAIL.value,
            recipient_type=NotificationRecipientType.COMPANY_ADMIN.value,
            user_id=users["admin"].id,
            recipient_identifier=users["admin"].email,
            subject="Failed notification",
            body="Failed body",
            status=NotificationEventStatus.FAILED.value,
            last_error="fixture failure",
        ),
        "skipped": NotificationEvent(
            company_id=active_company.id,
            domain_event_id=domain_events["failed"].id,
            notification_rule_id=rule.id,
            notification_template_id=template.id,
            channel=NotificationChannel.EMAIL.value,
            recipient_type=NotificationRecipientType.SALES_MANAGER.value,
            user_id=users["sales_manager"].id,
            recipient_identifier=users["sales_manager"].email,
            subject="Skipped notification",
            body="Skipped body",
            status=NotificationEventStatus.SKIPPED.value,
            skipped_reason="fixture skipped",
        ),
    }
    session.add_all(notification_events.values())
    await session.flush()

    reward_claims = {
        "pending": RewardClaim(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            customer_id=customers["active"].id,
            gift_tier_id=gift_tiers["soft"].id,
            status=RewardClaimStatus.PENDING.value,
            customer_comment="Pending claim",
        ),
        "approved": RewardClaim(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            customer_id=customers["active"].id,
            gift_tier_id=gift_tiers["soft"].id,
            status=RewardClaimStatus.APPROVED.value,
            admin_comment="Approved claim",
            decided_by_user_id=users["admin"].id,
            decided_at=now,
        ),
        "rejected": RewardClaim(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            customer_id=customers["blocked"].id,
            gift_tier_id=gift_tiers["strict"].id,
            status=RewardClaimStatus.REJECTED.value,
            admin_comment="Rejected claim",
            decided_by_user_id=users["admin"].id,
            decided_at=now,
        ),
        "fulfilled": RewardClaim(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            customer_id=customers["active"].id,
            gift_tier_id=gift_tiers["soft"].id,
            status=RewardClaimStatus.FULFILLED.value,
            fulfilled_by_user_id=users["sales_manager"].id,
            fulfilled_at=now,
        ),
        "cancelled": RewardClaim(
            company_id=active_company.id,
            campaign_id=campaigns["active"].id,
            customer_id=customers["archived"].id,
            gift_tier_id=gift_tiers["none"].id,
            status=RewardClaimStatus.CANCELLED.value,
            cancelled_by_user_id=users["owner"].id,
            cancelled_at=now,
        ),
    }
    session.add_all(reward_claims.values())
    await session.flush()

    import_batches = {
        "draft": ImportBatch(
            company_id=active_company.id,
            created_by_user_id=users["owner"].id,
            source_type="csv",
            provider="csv",
            status=ImportBatchStatus.DRAFT.value,
            original_filename="customers.csv",
            total_rows=1,
            valid_rows=1,
            stats_json={"status": "draft"},
        ),
        "previewed": ImportBatch(
            company_id=active_company.id,
            created_by_user_id=users["owner"].id,
            source_type="csv",
            provider="csv",
            status=ImportBatchStatus.PREVIEWED.value,
            original_filename="customers-preview.csv",
            total_rows=1,
            valid_rows=1,
            stats_json={"status": "previewed"},
        ),
        "committed": ImportBatch(
            company_id=active_company.id,
            created_by_user_id=users["owner"].id,
            source_type="csv",
            provider="csv",
            status=ImportBatchStatus.COMMITTED.value,
            original_filename="customers-committed.csv",
            total_rows=1,
            valid_rows=1,
            committed_rows=1,
            committed_at=now,
            stats_json={"status": "committed"},
        ),
        "failed": ImportBatch(
            company_id=active_company.id,
            created_by_user_id=users["owner"].id,
            source_type="csv",
            provider="csv",
            status=ImportBatchStatus.FAILED.value,
            original_filename="customers-failed.csv",
            total_rows=1,
            invalid_rows=1,
            error_summary="fixture failure",
            stats_json={"status": "failed"},
        ),
        "cancelled": ImportBatch(
            company_id=active_company.id,
            created_by_user_id=users["owner"].id,
            source_type="csv",
            provider="csv",
            status=ImportBatchStatus.CANCELLED.value,
            original_filename="customers-cancelled.csv",
            total_rows=1,
            skipped_rows=1,
            stats_json={"status": "cancelled"},
        ),
    }
    session.add_all(import_batches.values())
    await session.flush()

    import_rows = {
        "valid": ImportRow(
            company_id=active_company.id,
            import_batch_id=import_batches["draft"].id,
            row_number=1,
            raw_row_json={"name": "Valid Row"},
            normalized_row_json={"name": "Valid Row"},
            status=ImportRowStatus.VALID.value,
        ),
        "invalid": ImportRow(
            company_id=active_company.id,
            import_batch_id=import_batches["failed"].id,
            row_number=1,
            raw_row_json={"name": "Invalid Row"},
            normalized_row_json={"name": "Invalid Row"},
            status=ImportRowStatus.INVALID.value,
            error_messages_json=["missing email"],
        ),
        "committed": ImportRow(
            company_id=active_company.id,
            import_batch_id=import_batches["committed"].id,
            row_number=1,
            raw_row_json={"name": "Committed Row"},
            normalized_row_json={"name": "Committed Row"},
            status=ImportRowStatus.COMMITTED.value,
        ),
        "skipped": ImportRow(
            company_id=active_company.id,
            import_batch_id=import_batches["cancelled"].id,
            row_number=1,
            raw_row_json={"name": "Skipped Row"},
            normalized_row_json={"name": "Skipped Row"},
            status=ImportRowStatus.SKIPPED.value,
        ),
    }
    session.add_all(import_rows.values())
    await session.flush()

    sync_runs = {
        "queued": SyncRun(
            company_id=active_company.id,
            integration_id=integrations["active"].id,
            sync_type=SyncType.MANUAL.value,
            status=SyncRunStatus.QUEUED.value,
            task_id="task-queued",
            enqueued_at=now,
            created_by_user_id=users["owner"].id,
        ),
        "running": SyncRun(
            company_id=active_company.id,
            integration_id=integrations["active"].id,
            sync_type=SyncType.SCHEDULED.value,
            status=SyncRunStatus.RUNNING.value,
            task_id="task-running",
            enqueued_at=now - timedelta(minutes=5),
            started_at=now - timedelta(minutes=4),
            created_by_user_id=users["owner"].id,
        ),
        "success": SyncRun(
            company_id=active_company.id,
            integration_id=integrations["active"].id,
            sync_type=SyncType.FULL.value,
            status=SyncRunStatus.SUCCESS.value,
            task_id="task-success",
            enqueued_at=now - timedelta(hours=1),
            started_at=now - timedelta(hours=1, minutes=5),
            finished_at=now - timedelta(hours=1),
            created_by_user_id=users["owner"].id,
        ),
        "failed": SyncRun(
            company_id=active_company.id,
            integration_id=integrations["active"].id,
            sync_type=SyncType.INCREMENTAL.value,
            status=SyncRunStatus.FAILED.value,
            task_id="task-failed",
            enqueued_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2, minutes=5),
            finished_at=now - timedelta(hours=2),
            error_summary="fixture sync failure",
            created_by_user_id=users["owner"].id,
        ),
        "partially_failed": SyncRun(
            company_id=active_company.id,
            integration_id=integrations["active"].id,
            sync_type=SyncType.MANUAL.value,
            status=SyncRunStatus.PARTIALLY_FAILED.value,
            task_id="task-partial",
            enqueued_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=3, minutes=5),
            finished_at=now - timedelta(hours=3),
            error_summary="fixture partial failure",
            created_by_user_id=users["owner"].id,
        ),
    }
    session.add_all(sync_runs.values())
    await session.flush()

    sync_errors = {
        "warning": SyncError(
            company_id=active_company.id,
            sync_run_id=sync_runs["partially_failed"].id,
            entity_type="customer",
            external_id="cust-warning",
            severity=SyncErrorSeverity.WARNING.value,
            error_code="warning_code",
            message="Warning level sync issue",
            raw_payload_json={"warning": True},
        ),
        "error": SyncError(
            company_id=active_company.id,
            sync_run_id=sync_runs["failed"].id,
            entity_type="sale_record",
            external_id="sale-error",
            severity=SyncErrorSeverity.ERROR.value,
            error_code="error_code",
            message="Error level sync issue",
            raw_payload_json={"error": True},
        ),
    }
    session.add_all(sync_errors.values())
    await session.flush()

    subscriptions = {
        "trialing": CompanySubscription(
            company_id=active_company.id,
            plan_id=plan.id,
            status=SubscriptionStatus.TRIALING.value,
            trial_starts_at=now - timedelta(days=7),
            trial_ends_at=now + timedelta(days=7),
        ),
        "active": CompanySubscription(
            company_id=suspended_company.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            current_period_starts_at=now - timedelta(days=15),
            current_period_ends_at=now + timedelta(days=15),
        ),
        "past_due": CompanySubscription(
            company_id=archived_company.id,
            plan_id=plan.id,
            status=SubscriptionStatus.PAST_DUE.value,
            current_period_starts_at=now - timedelta(days=30),
            current_period_ends_at=now - timedelta(days=1),
        ),
        "cancelled": CompanySubscription(
            company_id=active_company.id,
            plan_id=plan.id,
            status=SubscriptionStatus.CANCELLED.value,
            current_period_starts_at=now - timedelta(days=90),
            current_period_ends_at=now - timedelta(days=60),
        ),
        "expired": CompanySubscription(
            company_id=active_company.id,
            plan_id=plan.id,
            status=SubscriptionStatus.EXPIRED.value,
            current_period_starts_at=now - timedelta(days=120),
            current_period_ends_at=now - timedelta(days=90),
        ),
    }
    session.add_all(subscriptions.values())

    company_usage_limit = CompanyUsageLimit(
        company_id=active_company.id,
        limit_key="campaigns",
        limit_value=5,
    )
    usage_counter = UsageCounter(
        company_id=active_company.id,
        metric="campaigns_created",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        value=3,
    )
    audit_logs = {
        "system": AuditLog(
            company_id=active_company.id,
            actor_type=AuditActorType.SYSTEM.value,
            action="seed.system",
            entity_type="system",
            entity_id=None,
            metadata_json={"fixture": True},
        ),
        "user": AuditLog(
            company_id=active_company.id,
            actor_user_id=users["owner"].id,
            actor_type=AuditActorType.USER.value,
            action="seed.user",
            entity_type="user",
            entity_id=users["owner"].id,
            metadata_json={"fixture": True},
        ),
        "customer": AuditLog(
            company_id=active_company.id,
            actor_customer_id=customers["active"].id,
            actor_type=AuditActorType.CUSTOMER.value,
            action="seed.customer",
            entity_type="customer",
            entity_id=customers["active"].id,
            metadata_json={"fixture": True},
        ),
        "task": AuditLog(
            company_id=active_company.id,
            actor_type=AuditActorType.TASK.value,
            action="seed.task",
            entity_type="task",
            entity_id=None,
            metadata_json={"fixture": True},
        ),
    }

    session.add_all([company_usage_limit, usage_counter, *audit_logs.values()])
    await session.commit()

    return {
        "companies": {
            "active": active_company,
            "suspended": suspended_company,
            "archived": archived_company,
        },
        "users": users,
        "customers": customers,
        "campaigns": campaigns,
        "gift_tiers": gift_tiers,
        "integrations": integrations,
        "integration_credentials": integration_credentials,
        "customer_external_ref": customer_external_ref,
        "customer_assignment": customer_assignment,
        "sales": sales,
        "domain_events": domain_events,
        "notification_template": template,
        "notification_rule": rule,
        "notification_events": notification_events,
        "reward_claims": reward_claims,
        "import_batches": import_batches,
        "import_rows": import_rows,
        "sync_runs": sync_runs,
        "sync_errors": sync_errors,
        "billing": {
            "plan": plan,
            "subscriptions": subscriptions,
            "usage_limit": company_usage_limit,
            "usage_counter": usage_counter,
        },
        "audit_logs": audit_logs,
    }