"""Catalog-backed local route adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

from app.core.config import Settings
from app.core.errors import UpstreamFetchError
from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter
from app.sources.catalog import SourcePreset
from app.sources.routes import RouteFetcher, build_route_fetchers


class CatalogRouteSource(HotSourceAdapter):
    """Fetch normalized data from locally ported DailyHot routes."""

    def __init__(
        self,
        settings: Settings,
        preset: SourcePreset,
        route_fetchers: Mapping[str, RouteFetcher] | None = None,
    ) -> None:
        super().__init__(settings, preset)
        self.route_fetchers = route_fetchers or build_route_fetchers()

    async def fetch(self) -> HotSourceSnapshot:
        if self.preset is None:
            raise self.upstream_error()
        fetcher = self.route_fetchers.get(self.preset.route_code)
        if fetcher is None:
            raise self.upstream_error()

        try:
            route_result = await fetcher(self, self.resolve_request_params())
            items = self.normalize_items(route_result.data)
            fetched_at = route_result.update_time.astimezone(timezone.utc)
            return self.build_snapshot(
                items,
                source_name=route_result.title or self.preset.source_name,
                fetched_at=fetched_at,
                source_type=route_result.source_type or self.preset.source_type,
            )
        except UpstreamFetchError:
            raise
        except Exception as exc:  # pragma: no cover - normalized into upstream error
            raise self.upstream_error() from exc

    def normalize_items(self, upstream_items: List[Dict[str, Any]]) -> List[HotItem]:
        normalized: List[HotItem] = []
        for index, item in enumerate(upstream_items[: self.max_items], start=1):
            title = self.stringify(item.get("title"))
            if not title:
                continue
            url = self.normalize_url(item.get("url")) or self.normalize_url(item.get("mobileUrl"))
            if not url:
                continue
            normalized.append(
                HotItem(
                    rank=index,
                    title=title,
                    url=url,
                    hotValue=self.stringify(item.get("hot") or item.get("hotValue")),
                    cover=self.normalize_url(item.get("cover") or item.get("pic") or item.get("banner")),
                    summary=self.stringify(item.get("desc") or item.get("summary") or item.get("contentSnippet")),
                    publishedAt=self.parse_timestamp(
                        item.get("timestamp")
                        or item.get("publishedAt")
                        or item.get("pubDate")
                        or item.get("publishTime")
                    ),
                )
            )

        if self.preset.route_code == "weibo" and self.settings.hot_filter_weibo_advertisement:
            normalized = [item for item in normalized if not looks_like_weibo_advertisement(item)]

        return normalized

    def resolve_request_params(self) -> Dict[str, str]:
        if self.preset is None:
            return {}
        params = dict(self.preset.params)
        if self.preset.route_code == "history":
            now = datetime.now(timezone.utc).astimezone()
            params["month"] = str(now.month)
            params["day"] = str(now.day)
        return params

    def upstream_error(self) -> UpstreamFetchError:
        return UpstreamFetchError(self.preset.source_code if self.preset else self.source_code)


def looks_like_weibo_advertisement(item: HotItem) -> bool:
    """Apply a conservative ad filter when the feature flag is enabled."""

    text = "{0} {1}".format(item.title or "", item.summary or "").lower()
    return "广告" in text or "ad " in text or text.startswith("ad:")
