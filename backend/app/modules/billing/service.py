from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import CompanySubscription, Plan, SubscriptionStatus


class BillingService:
    DEFAULT_PLAN_CODE = "free"

    async def get_default_plan(self, session: AsyncSession) -> Plan | None:
        result = await session.execute(
            select(Plan).where(Plan.code == self.DEFAULT_PLAN_CODE)
        )
        return result.scalar_one_or_none()

    async def create_default_plan_if_needed(self, session: AsyncSession) -> Plan:
        plan = await self.get_default_plan(session)
        if plan is not None:
            return plan

        plan = Plan(
            code=self.DEFAULT_PLAN_CODE,
            name="Free",
            description="Default free plan for newly registered companies.",
            limits_json={
                "max_customers": 100,
                "max_active_campaigns": 1,
                "max_integrations": 1,
                "max_team_members": 3,
            },
            features_json={"portal_branding": False, "scheduled_sync": False},
            is_active=True,
        )
        session.add(plan)
        await session.flush()
        return plan

    async def assign_default_plan_to_company(
        self,
        session: AsyncSession,
        *,
        company_id,
    ) -> CompanySubscription:
        plan = await self.create_default_plan_if_needed(session)
        subscription = CompanySubscription(
            company_id=company_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        session.add(subscription)
        await session.flush()
        return subscription


billing_service = BillingService()

