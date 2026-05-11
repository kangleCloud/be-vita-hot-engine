"""36Kr hot-rank adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter


class Kr36HotSource(HotSourceAdapter):
    """Fetch 36Kr hot ranking via the public gateway."""

    source_code = "36kr"
    source_name = "36氪"
    endpoint = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"

    async def fetch(self) -> HotSourceSnapshot:
        payload = await self.request_json(
            self.endpoint,
            method="POST",
            headers={"Content-Type": "application/json"},
            json_body={
                "partner_id": "wap",
                "param": {"siteId": 1, "platformId": 2},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            },
        )
        try:
            entries = payload.get("data", {}).get("hotRankList", [])
            items: List[HotItem] = []
            for index, entry in enumerate(entries[: self.max_items], start=1):
                material = entry.get("templateMaterial") or {}
                item_id = material.get("itemId") or entry.get("itemId")
                title = self.stringify(material.get("widgetTitle"))
                if not item_id or not title:
                    continue
                items.append(
                    HotItem(
                        rank=index,
                        title=title,
                        url="https://www.36kr.com/p/{0}".format(item_id),
                        hotValue=self.stringify(material.get("statCollect")),
                        cover=self.normalize_url(self.stringify(material.get("widgetImage"))),
                        summary=self.stringify(material.get("summary")),
                        publishedAt=self.parse_timestamp(material.get("publishTime")),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc
