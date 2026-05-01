from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.companies.schemas import CompanyResponse
from app.modules.customers.schemas import CustomerResponse
from app.modules.portal.dependencies import get_portal_context
from app.modules.portal.schemas import (
    PortalCampaignResponse,
    PortalGiftTierResponse,
    PortalMeResponse,
    PortalProgressResponse,
    PortalPurchaseHistoryItem,
    PortalSessionRequest,
    PortalSessionResponse,
)
from app.modules.portal.service import PortalContext, portal_service

router = APIRouter(prefix="/portal", tags=["portal"])


@router.post("/session", response_model=PortalSessionResponse)
async def create_portal_session(
    data: PortalSessionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortalSessionResponse:
    portal_access_token, expires_in, customer, company = (
        await portal_service.create_portal_session(
            session,
            raw_token=data.token,
        )
    )
    return PortalSessionResponse(
        portal_access_token=portal_access_token,
        expires_in=expires_in,
        customer=CustomerResponse.model_validate(customer),
        company=CompanyResponse.model_validate(company),
    )


@router.get("/me", response_model=PortalMeResponse)
async def get_portal_me(
    context: Annotated[PortalContext, Depends(get_portal_context)],
) -> PortalMeResponse:
    return PortalMeResponse(
        customer=CustomerResponse.model_validate(context.customer),
        company=CompanyResponse.model_validate(context.company),
    )


@router.get("/campaigns", response_model=list[PortalCampaignResponse])
async def list_portal_campaigns(
    context: Annotated[PortalContext, Depends(get_portal_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PortalCampaignResponse]:
    campaigns = await portal_service.list_portal_campaigns(session, context=context)
    return [PortalCampaignResponse.model_validate(campaign) for campaign in campaigns]


@router.get("/campaigns/{campaign_id}/progress", response_model=PortalProgressResponse)
async def get_portal_campaign_progress(
    campaign_id: UUID,
    context: Annotated[PortalContext, Depends(get_portal_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortalProgressResponse:
    campaign = await portal_service.get_portal_campaign(
        session,
        context=context,
        campaign_id=campaign_id,
    )
    gift_tiers = await portal_service.list_campaign_tiers(
        session,
        context=context,
        campaign_id=campaign.id,
    )
    progress = await portal_service.get_progress_snapshot(
        session,
        context=context,
        campaign=campaign,
        gift_tiers=gift_tiers,
    )
    return PortalProgressResponse(
        campaign=PortalCampaignResponse.model_validate(campaign),
        customer=CustomerResponse.model_validate(context.customer),
        progress=progress,
        gift_tiers=[
            PortalGiftTierResponse.model_validate(tier) for tier in gift_tiers
        ],
    )


@router.get(
    "/campaigns/{campaign_id}/purchase-history",
    response_model=list[PortalPurchaseHistoryItem],
)
async def list_portal_purchase_history(
    campaign_id: UUID,
    context: Annotated[PortalContext, Depends(get_portal_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PortalPurchaseHistoryItem]:
    campaign = await portal_service.get_portal_campaign(
        session,
        context=context,
        campaign_id=campaign_id,
    )
    sale_records = await portal_service.list_purchase_history(
        session,
        context=context,
        campaign=campaign,
    )
    return [
        PortalPurchaseHistoryItem.model_validate(sale_record)
        for sale_record in sale_records
    ]
