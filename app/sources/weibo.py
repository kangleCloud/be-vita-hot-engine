"""Weibo hot-search adapter."""

from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter


class WeiboHotSource(HotSourceAdapter):
    """Fetch Weibo realtime hot-search data."""

    source_code = "weibo"
    source_name = "微博热搜"
    endpoint = "https://weibo.com/ajax/side/hotSearch"

    async def fetch(self) -> HotSourceSnapshot:
        headers = {
            "Referer": "https://s.weibo.com/top/summary",
            "Accept": "application/json, text/plain, */*",
        }
        payload = await self.request_json(self.endpoint, headers=headers)
        try:
            entries = payload.get("data", {}).get("realtime", [])
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                title = self.stringify(entry.get("word") or entry.get("note"))
                if not title:
                    continue
                url = "https://s.weibo.com/weibo?q={0}".format(quote(title))
                items.append(
                    HotItem(
                        rank=index,
                        title=title,
                        url=url,
                        hotValue=self.stringify(entry.get("num")),
                        summary=self.stringify(entry.get("word_scheme")),
                        publishedAt=self.parse_timestamp(entry.get("onboard_time")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
