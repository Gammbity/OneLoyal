"""Import SQLAlchemy models so Alembic can discover metadata."""

from app.modules.audit.models import AuditLog
from app.modules.auth.models import UserSession
from app.modules.billing.models import (
    CompanySubscription,
    CompanyUsageLimit,
    Plan,
    UsageCounter,
)
from app.modules.campaigns.models import Campaign, GiftTier
from app.modules.claims.models import RewardClaim
from app.modules.companies.models import Company, CompanySettings
from app.modules.customers.models import (
    Customer,
    CustomerAssignment,
    CustomerExternalRef,
)
from app.modules.events.models import DomainEvent
from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.integrations.models import Integration, IntegrationCredential
from app.modules.portal.models import MagicLinkToken
from app.modules.progress.models import CustomerCampaignProgress
from app.modules.sales.models import SaleRecord
from app.modules.sync.models import SyncError, SyncRun
from app.modules.users.models import User

__all__ = [
    "Campaign",
    "Company",
    "CompanySettings",
    "CompanySubscription",
    "CompanyUsageLimit",
    "AuditLog",
    "Customer",
    "CustomerAssignment",
    "CustomerCampaignProgress",
    "CustomerExternalRef",
    "DomainEvent",
    "GiftTier",
    "ImportBatch",
    "ImportRow",
    "Integration",
    "IntegrationCredential",
    "MagicLinkToken",
    "Plan",
    "RewardClaim",
    "SaleRecord",
    "SyncError",
    "SyncRun",
    "UsageCounter",
    "User",
    "UserSession",
]
