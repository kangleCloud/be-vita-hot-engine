"""Catalog tests for materialized source definitions."""

from __future__ import annotations

from app.sources.catalog import build_source_catalog
from app.sources.route_source import CatalogRouteSource
from app.sources.registry import build_source_registry


def test_source_catalog_contains_unique_source_codes() -> None:
    catalog = build_source_catalog()
    source_codes = [preset.source_code for preset in catalog]

    assert len(source_codes) == len(set(source_codes))
    assert "weibo" in source_codes
    assert "github__weekly" in source_codes
    assert "smzdm__7" in source_codes
    assert "genshin" in source_codes
    assert "honkai" in source_codes
    assert "douyin" in source_codes
    assert "hostloc__digest" in source_codes
    assert "producthunt" in source_codes
    assert "starrail__3" in source_codes
    assert not any(code.startswith("miyoushe") for code in source_codes)
    assert "coolapk" not in source_codes
    assert "earthquake" not in source_codes
    assert "gameres" not in source_codes
    assert "linuxdo" not in source_codes
    assert "nytimes" not in source_codes
    assert "nytimes__global" not in source_codes
    assert "nodeseek" not in source_codes
    assert "v2ex" not in source_codes
    assert "v2ex__latest" not in source_codes


def test_source_catalog_includes_required_metadata() -> None:
    catalog = build_source_catalog()
    first = next(preset for preset in catalog if preset.source_code == "bilibili")

    assert first.route_code == "bilibili"
    assert first.icon_key == "bilibili"
    assert first.source_name == "哔哩哔哩"
    assert first.source_type == "热榜 · 全站"
    assert first.default_visible is True


def test_source_registry_materializes_all_presets(settings) -> None:
    registry, presets = build_source_registry(settings)

    assert len(registry) == len(presets)
    assert set(registry.keys()) == {preset.source_code for preset in presets}
    assert all(isinstance(adapter, CatalogRouteSource) for adapter in registry.values())
    assert not any(source_code.startswith("miyoushe") for source_code in registry)
    assert "coolapk" not in registry
    assert "earthquake" not in registry
    assert "gameres" not in registry
    assert "linuxdo" not in registry
    assert "nytimes" not in registry
    assert "nytimes__global" not in registry
    assert "nodeseek" not in registry
    assert "v2ex" not in registry
    assert "v2ex__latest" not in registry
