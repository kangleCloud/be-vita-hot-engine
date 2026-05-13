"""Compatibility exports for the legacy mirror adapter path."""

from app.sources.route_source import CatalogRouteSource

DailyHotMirrorSource = CatalogRouteSource

__all__ = ["CatalogRouteSource", "DailyHotMirrorSource"]
