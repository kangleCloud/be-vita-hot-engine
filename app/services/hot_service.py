"""Service layer for source discovery and snapshot fetching."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from app.core.config import get_settings
from app.core.errors import SourceNotFoundError
from app.schemas.hot import HotSourceInfo, HotSourceSnapshot, HotSourcesResponse
from app.sources.base import HotSourceAdapter
from app.sources.registry import build_source_registry


class HotService:
    """Coordinate source lookup and adapter dispatch."""

    def __init__(self, adapters: Dict[str, HotSourceAdapter]) -> None:
        self.adapters = adapters

    def list_sources(self) -> HotSourcesResponse:
        return HotSourcesResponse(
            sources=[
                HotSourceInfo(
                    sourceCode=adapter.source_code,
                    sourceName=adapter.source_name,
                    enabled=True,
                )
                for adapter in self.adapters.values()
            ]
        )

    async def get_source_snapshot(self, source_code: str) -> HotSourceSnapshot:
        adapter = self.adapters.get(source_code)
        if adapter is None:
            raise SourceNotFoundError(source_code)
        return await adapter.fetch()


@lru_cache(maxsize=1)
def get_hot_service() -> HotService:
    """Return a cached service instance."""

    settings = get_settings()
    return HotService(build_source_registry(settings))
