from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.companies.router import router as companies_router
from app.modules.customers.router import router as customers_router
from app.modules.imports.router import router as imports_router
from app.modules.integrations.router import router as integrations_router
from app.modules.portal.router import router as portal_router
from app.modules.progress.router import router as progress_router
from app.modules.sales.router import router as sale_records_router
from app.modules.sync.router import router as sync_runs_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(users_router)
api_router.include_router(campaigns_router)
api_router.include_router(customers_router)
api_router.include_router(sale_records_router)
api_router.include_router(progress_router)
api_router.include_router(portal_router)
api_router.include_router(integrations_router)
api_router.include_router(sync_runs_router)
api_router.include_router(imports_router)
