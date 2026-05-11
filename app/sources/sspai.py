"""SSPai hot article adapter."""

from __future__ import annotations

from typing import List

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter


class SSPaiHotSource(HotSourceAdapter):
    """Fetch SSPai popular articles."""

    source_code = "sspai"
    source_name = "少数派"
    endpoint = "https://sspai.com/api/v1/article/tag/page/get"

    async def fetch(self) -> HotSourceSnapshot:
        payload = await self.request_json(
            self.endpoint,
            params={"limit": self.max_items, "tag": "热门文章"},
        )
        try:
            entries = payload.get("data", [])
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                article_id = entry.get("id")
                title = self.stringify(entry.get("title"))
                if not article_id or not title:
                    continue
                items.append(
                    HotItem(
                        rank=index,
                        title=title,
                        url="https://sspai.com/post/{0}".format(article_id),
                        hotValue=self.stringify(entry.get("like_count")),
                        cover=self.normalize_url(self.stringify(entry.get("banner"))),
                        summary=self.stringify(entry.get("summary")),
                        publishedAt=self.parse_timestamp(entry.get("released_time")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
