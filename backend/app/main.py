from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.redis import close_redis_client
from app.core.settings import Settings, get_settings
from app.db.session import dispose_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await close_redis_client()
    await dispose_db_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        # Locale middleware reads X-Locale or Accept-Language and sets request.state.locale
        __import__("app.core.middleware", fromlist=["LocaleMiddleware"]).LocaleMiddleware
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()

