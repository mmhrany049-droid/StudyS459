"""FastAPI application factory.

URL paths follow `study_system_v1_docs/14_API_CONTRACT_V1.md` VERBATIM
(no /api/v1 prefix in the URL) so frontend and contract always agree.
Code is still organized under `app/api/v1/` for future versioning.
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1 import v1_router
from app.config import get_settings
from app.errors import AppError, error_envelope
from app.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: D103, ARG001
    settings = get_settings()
    logger.info(
        "starting %s v%s env=%s tz=%s",
        settings.APP_NAME,
        __version__,
        settings.ENV,
        settings.TIMEZONE,
    )
    yield
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_context(request: Request, call_next):  # noqa: D103
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error request_id=%s %s %s", request_id, request.method, request.url.path)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.1fms) request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:  # noqa: D103, ARG001
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # noqa: D103, ARG001
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: D103, ARG001
        return JSONResponse(
            status_code=422,
            content=error_envelope("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: D103, ARG001
        logger.exception("unexpected error: %r", exc)
        detail = str(exc) if settings.DEBUG else None
        return JSONResponse(
            status_code=500,
            content=error_envelope("internal_error", "Unexpected server error", detail),
        )

    # No URL prefix: contract paths (14_API_CONTRACT_V1.md) are served as-is.
    app.include_router(v1_router)

    return app


app = create_app()
