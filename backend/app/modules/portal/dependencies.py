from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.db.session import get_db
from app.modules.portal.service import PortalContext, portal_service

portal_bearer_scheme = HTTPBearer(auto_error=False)


async def get_portal_context(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(portal_bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortalContext:
    if credentials is None:
        raise UnauthorizedError("Portal authentication required.")
    return await portal_service.get_portal_context(
        session,
        portal_access_token=credentials.credentials,
    )

