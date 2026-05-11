"""Juejin article rank adapter."""

from __future__ import annotations

from typing import List

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter


class JuejinHotSource(HotSourceAdapter):
    """Fetch Juejin hot article ranking."""

    source_code = "juejin"
    source_name = "稀土掘金"
    endpoint = "https://api.juejin.cn/content_api/v1/content/article_rank"

    async def fetch(self) -> HotSourceSnapshot:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://juejin.cn/hot/articles",
        }
        payload = await self.request_json(
            self.endpoint,
            headers=headers,
            params={"category_id": 1, "type": "hot"},
        )
        try:
            entries = payload.get("data", [])
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                content = entry.get("content", {})
                content_id = self.stringify(content.get("content_id"))
                title = self.stringify(content.get("title"))
                if not content_id or not title:
                    continue
                items.append(
                    HotItem(
                        rank=index,
                        title=title,
                        url="https://juejin.cn/post/{0}".format(content_id),
                        hotValue=self.stringify((entry.get("content_counter") or {}).get("hot_rank")),
                        summary=self.stringify((entry.get("content_info") or {}).get("brief_content")),
                        publishedAt=self.parse_timestamp(content.get("ctime")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
