"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.hot import router as hot_router
from app.core.config import get_settings
from app.core.errors import HotEngineError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Internal hot source aggregation service for be-vita.",
    )
    application.include_router(hot_router)
    register_exception_handlers(application)
    return application


def register_exception_handlers(application: FastAPI) -> None:
    """Register unified JSON error handlers."""

    @application.exception_handler(HotEngineError)
    async def handle_hot_engine_error(_: Request, exc: HotEngineError) -> JSONResponse:
        content: Dict[str, Any] = {
            "code": exc.error_code,
            "detail": exc.detail,
        }
        if exc.source_code:
            content["sourceCode"] = exc.source_code
        if exc.extra:
            content.update(exc.extra)
        return JSONResponse(status_code=exc.status_code, content=content)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_server_error",
                "detail": "internal server error",
            },
        )


app = create_app()
