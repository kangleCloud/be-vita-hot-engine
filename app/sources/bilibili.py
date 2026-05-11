"""Bilibili ranking adapter."""

from __future__ import annotations

from typing import List

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter


class BilibiliHotSource(HotSourceAdapter):
    """Fetch Bilibili all-site ranking data."""

    source_code = "bilibili"
    source_name = "哔哩哔哩"
    endpoint = "https://api.bilibili.com/x/web-interface/ranking"

    async def fetch(self) -> HotSourceSnapshot:
        headers = {"Referer": "https://www.bilibili.com/v/popular/rank/all"}
        payload = await self.request_json(
            self.endpoint,
            headers=headers,
            params={"rid": 0, "type": "all", "jsonp": "jsonp"},
        )
        try:
            entries = payload.get("data", {}).get("list", [])
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                bvid = self.stringify(entry.get("bvid"))
                if not bvid:
                    continue
                items.append(
                    HotItem(
                        rank=index,
                        title=self.stringify(entry.get("title")) or "哔哩哔哩热门",
                        url="https://www.bilibili.com/video/{0}".format(bvid),
                        hotValue=self.stringify(
                            entry.get("video_review")
                            or (entry.get("stat") or {}).get("view")
                        ),
                        cover=self.normalize_url(self.stringify(entry.get("pic"))),
                        summary=self.stringify(entry.get("desc")),
                        publishedAt=self.parse_timestamp(entry.get("pubdate")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
