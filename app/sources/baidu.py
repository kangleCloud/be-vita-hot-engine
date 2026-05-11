"""Baidu hot-search adapter."""

from __future__ import annotations

import json
import re
from typing import List
from urllib.parse import quote

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter

BAIDU_DATA_PATTERN = re.compile(r"<!--\s*s-data:(.*?)-->", re.S)


class BaiduHotSource(HotSourceAdapter):
    """Fetch Baidu realtime hot-list data."""

    source_code = "baidu"
    source_name = "百度热搜"
    endpoint = "https://top.baidu.com/board?tab=realtime"

    async def fetch(self) -> HotSourceSnapshot:
        html = await self.request_text(self.endpoint)
        try:
            matched = BAIDU_DATA_PATTERN.search(html)
            if not matched:
                raise ValueError("baidu payload not found")
            payload = json.loads(matched.group(1))
            card_data = payload.get("data", {}).get("cards", [])
            entries = []
            for card in card_data:
                if card.get("component") == "hotList":
                    entries = card.get("content", [])
                    break
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                title = self.stringify(entry.get("word") or entry.get("query"))
                if not title:
                    continue
                query = self.stringify(entry.get("query")) or title
                raw_url = self.stringify(entry.get("rawUrl"))
                cover = entry.get("img")
                if not cover:
                    cover = (entry.get("imgInfo") or {}).get("img")
                items.append(
                    HotItem(
                        rank=index,
                        title=title,
                        url=raw_url or "https://www.baidu.com/s?wd={0}".format(quote(query)),
                        hotValue=self.stringify(entry.get("hotScore") or entry.get("hotTag")),
                        cover=self.normalize_url(self.stringify(cover)),
                        summary=self.stringify(entry.get("desc")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
