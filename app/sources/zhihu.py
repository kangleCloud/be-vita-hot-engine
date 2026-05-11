"""Zhihu hot-list adapter."""

from __future__ import annotations

from typing import List

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter


class ZhihuHotSource(HotSourceAdapter):
    """Fetch Zhihu hot-list data."""

    source_code = "zhihu"
    source_name = "知乎热榜"
    endpoint = "https://api.zhihu.com/topstory/hot-lists/total"

    async def fetch(self) -> HotSourceSnapshot:
        payload = await self.request_json(self.endpoint, params={"limit": self.max_items})
        try:
            entries = payload.get("data", [])
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                target = entry.get("target", {})
                question_id = target.get("id")
                if not question_id:
                    continue
                children = target.get("children", [])
                thumbnail = None
                if children and isinstance(children[0], dict):
                    thumbnail = children[0].get("thumbnail")
                items.append(
                    HotItem(
                        rank=index,
                        title=self.stringify(target.get("title")) or "知乎热榜",
                        url="https://www.zhihu.com/question/{0}".format(question_id),
                        hotValue=self.stringify(entry.get("detail_text")),
                        cover=self.normalize_url(self.stringify(thumbnail)),
                        summary=self.stringify(target.get("excerpt")),
                        publishedAt=self.parse_timestamp(target.get("created")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
