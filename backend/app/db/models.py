"""Import SQLAlchemy models so Alembic can discover metadata."""

from app.modules.auth.models import UserSession
from app.modules.billing.models import (
    CompanySubscription,
    CompanyUsageLimit,
    Plan,
    UsageCounter,
)
from app.modules.campaigns.models import Campaign, GiftTier
from app.modules.companies.models import Company, CompanySettings
from app.modules.customers.models import (
    Customer,
    CustomerAssignment,
    CustomerExternalRef,
)
from app.modules.progress.models import CustomerCampaignProgress
from app.modules.sales.models import SaleRecord
from app.modules.users.models import User

__all__ = [
    "Campaign",
    "Company",
    "CompanySettings",
    "CompanySubscription",
    "CompanyUsageLimit",
    "Customer",
    "CustomerAssignment",
    "CustomerCampaignProgress",
    "CustomerExternalRef",
    "GiftTier",
    "Plan",
    "SaleRecord",
    "UsageCounter",
    "User",
    "UserSession",
]
