"""Service layer for source discovery and snapshot fetching."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

from app.core.config import get_settings
from app.core.errors import SourceNotFoundError
from app.schemas.hot import HotSourceInfo, HotSourceSnapshot, HotSourcesResponse
from app.sources.base import HotSourceAdapter
from app.sources.catalog import SourcePreset
from app.sources.registry import build_source_registry


class HotService:
    """Coordinate source lookup and adapter dispatch."""

    def __init__(self, adapters: Dict[str, HotSourceAdapter], presets: List[SourcePreset]) -> None:
        self.adapters = adapters
        self.presets = presets

    def list_sources(self) -> HotSourcesResponse:
        # 源列表接口只暴露 catalog 元数据，避免为了列表页触发批量上游抓取。
        return HotSourcesResponse(
            sources=[
                HotSourceInfo(
                    sourceCode=preset.source_code,
                    routeCode=preset.route_code,
                    iconKey=preset.icon_key,
                    sourceName=preset.source_name,
                    sourceType=preset.source_type,
                    description=preset.description,
                    enabled=preset.enabled,
                    defaultVisible=preset.default_visible,
                )
                for preset in self.presets
            ]
        )

    async def get_source_snapshot(self, source_code: str) -> HotSourceSnapshot:
        # 快照接口按物化后的 source_code 精确分发，兼容默认榜单别名和参数变体编码。
        adapter = self.adapters.get(source_code)
        if adapter is None:
            raise SourceNotFoundError(source_code)
        return await adapter.fetch()


@lru_cache(maxsize=1)
def get_hot_service() -> HotService:
    """Return a cached service instance."""

    settings = get_settings()
    adapters, presets = build_source_registry(settings)
    return HotService(adapters, presets)
