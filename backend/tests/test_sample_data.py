from app.modules.billing.models import SubscriptionStatus
from app.modules.campaigns.models import CampaignStatus, StockTrackingMode
from app.modules.claims.models import RewardClaimStatus
from app.modules.companies.models import CompanyStatus
from app.modules.customers.models import CustomerStatus
from app.modules.events.models import DomainEventStatus
from app.modules.imports.models import ImportBatchStatus, ImportRowStatus
from app.modules.integrations.models import IntegrationStatus
from app.modules.notifications.models import NotificationEventStatus
from app.modules.sales.models import PaymentStatus, SaleDocumentKind, SaleDocumentStatus
from app.modules.sync.models import SyncErrorSeverity, SyncRunStatus
from app.modules.users.models import UserRole, UserStatus


def test_sample_data_covers_stateful_models(sample_data) -> None:
    assert sample_data["companies"]["active"].status == CompanyStatus.ACTIVE.value
    assert sample_data["companies"]["suspended"].status == CompanyStatus.SUSPENDED.value
    assert sample_data["companies"]["archived"].status == CompanyStatus.ARCHIVED.value

    assert sample_data["users"]["owner"].role == UserRole.OWNER.value
    assert sample_data["users"]["admin"].status == UserStatus.INVITED.value
    assert sample_data["users"]["sales_manager"].status == UserStatus.DISABLED.value

    assert {campaign.status for campaign in sample_data["campaigns"].values()} == {
        CampaignStatus.DRAFT.value,
        CampaignStatus.ACTIVE.value,
        CampaignStatus.PAUSED.value,
        CampaignStatus.COMPLETED.value,
        CampaignStatus.ARCHIVED.value,
    }
    assert {tier.stock_tracking_mode for tier in sample_data["gift_tiers"].values()} == {
        StockTrackingMode.NONE.value,
        StockTrackingMode.SOFT.value,
        StockTrackingMode.STRICT.value,
    }

    assert {customer.status for customer in sample_data["customers"].values()} == {
        CustomerStatus.ACTIVE.value,
        CustomerStatus.ARCHIVED.value,
        CustomerStatus.BLOCKED.value,
    }
    assert {integration.status for integration in sample_data["integrations"].values()} == {
        IntegrationStatus.DRAFT.value,
        IntegrationStatus.ACTIVE.value,
        IntegrationStatus.DISABLED.value,
        IntegrationStatus.ERROR.value,
    }

    assert {sale.document_kind for sale in sample_data["sales"].values()} == {
        SaleDocumentKind.SALE.value,
        SaleDocumentKind.RETURN.value,
        SaleDocumentKind.REFUND.value,
        SaleDocumentKind.ADJUSTMENT.value,
        SaleDocumentKind.CORRECTION.value,
    }
    assert {sale.payment_status for sale in sample_data["sales"].values()} == {
        PaymentStatus.PAID.value,
        PaymentStatus.UNPAID.value,
        PaymentStatus.PARTIAL.value,
        PaymentStatus.OVERPAID.value,
        PaymentStatus.UNKNOWN.value,
    }
    assert {sale.document_status for sale in sample_data["sales"].values()} == {
        SaleDocumentStatus.POSTED.value,
        SaleDocumentStatus.DRAFT.value,
        SaleDocumentStatus.CANCELLED.value,
        SaleDocumentStatus.DELETED.value,
        SaleDocumentStatus.UNKNOWN.value,
    }

    assert {event.status for event in sample_data["domain_events"].values()} == {
        DomainEventStatus.PENDING.value,
        DomainEventStatus.PROCESSING.value,
        DomainEventStatus.PROCESSED.value,
        DomainEventStatus.FAILED.value,
    }
    assert {event.status for event in sample_data["notification_events"].values()} == {
        NotificationEventStatus.PENDING.value,
        NotificationEventStatus.SENT.value,
        NotificationEventStatus.FAILED.value,
        NotificationEventStatus.SKIPPED.value,
    }
    assert {claim.status for claim in sample_data["reward_claims"].values()} == {
        RewardClaimStatus.PENDING.value,
        RewardClaimStatus.APPROVED.value,
        RewardClaimStatus.REJECTED.value,
        RewardClaimStatus.FULFILLED.value,
        RewardClaimStatus.CANCELLED.value,
    }

    assert {batch.status for batch in sample_data["import_batches"].values()} == {
        ImportBatchStatus.DRAFT.value,
        ImportBatchStatus.PREVIEWED.value,
        ImportBatchStatus.COMMITTED.value,
        ImportBatchStatus.FAILED.value,
        ImportBatchStatus.CANCELLED.value,
    }
    assert {row.status for row in sample_data["import_rows"].values()} == {
        ImportRowStatus.VALID.value,
        ImportRowStatus.INVALID.value,
        ImportRowStatus.COMMITTED.value,
        ImportRowStatus.SKIPPED.value,
    }

    assert {sync_run.status for sync_run in sample_data["sync_runs"].values()} == {
        SyncRunStatus.QUEUED.value,
        SyncRunStatus.RUNNING.value,
        SyncRunStatus.SUCCESS.value,
        SyncRunStatus.FAILED.value,
        SyncRunStatus.PARTIALLY_FAILED.value,
    }
    assert {error.severity for error in sample_data["sync_errors"].values()} == {
        SyncErrorSeverity.WARNING.value,
        SyncErrorSeverity.ERROR.value,
    }

    assert {subscription.status for subscription in sample_data["billing"]["subscriptions"].values()} == {
        SubscriptionStatus.TRIALING.value,
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.CANCELLED.value,
        SubscriptionStatus.EXPIRED.value,
    }