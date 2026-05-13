"""Source adapter registry."""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.core.config import Settings
from app.sources.base import HotSourceAdapter
from app.sources.catalog import SourcePreset, build_source_catalog
from app.sources.route_source import CatalogRouteSource
from app.sources.routes import build_route_fetchers


def build_source_registry(settings: Settings) -> Tuple[Dict[str, HotSourceAdapter], List[SourcePreset]]:
    """Instantiate the full source registry."""

    presets = build_source_catalog()
    route_fetchers = build_route_fetchers()
    registry: Dict[str, HotSourceAdapter] = {}
    for preset in presets:
        registry[preset.source_code] = CatalogRouteSource(settings, preset, route_fetchers)
    return registry, presets
