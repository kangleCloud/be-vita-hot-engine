"""Hot source API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.security import verify_bearer_token
from app.schemas.hot import HealthResponse, HotSourceSnapshot, HotSourcesResponse
from app.services.hot_service import HotService, get_hot_service

router = APIRouter(prefix="/api/v1", tags=["hot"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return service health information."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get(
    "/hot/sources",
    response_model=HotSourcesResponse,
    dependencies=[Depends(verify_bearer_token)],
)
async def list_sources(service: HotService = Depends(get_hot_service)) -> HotSourcesResponse:
    """List enabled hot source definitions."""

    return service.list_sources()


@router.get(
    "/hot/{source_code}",
    response_model=HotSourceSnapshot,
    dependencies=[Depends(verify_bearer_token)],
)
async def get_source(
    source_code: str,
    service: HotService = Depends(get_hot_service),
) -> HotSourceSnapshot:
    """Fetch a normalized snapshot for one source."""

    return await service.get_source_snapshot(source_code)
