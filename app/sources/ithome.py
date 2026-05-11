"""ITHome mobile hot-rank adapter."""

from __future__ import annotations

import re
from typing import List, Optional

from selectolax.parser import HTMLParser

from app.schemas.hot import HotItem, HotSourceSnapshot
from app.sources.base import HotSourceAdapter

ITHOME_ARTICLE_PATTERN = re.compile(r"(?:html|live)/(\d+)\.htm")


class ITHomeHotSource(HotSourceAdapter):
    """Fetch ITHome hot-rank data from the mobile page."""

    source_code = "ithome"
    source_name = "IT之家"
    endpoint = "https://m.ithome.com/rankm/"

    async def fetch(self) -> HotSourceSnapshot:
        html = await self.request_text(self.endpoint)
        try:
            parser = HTMLParser(html)
            nodes = parser.css(".rank-box .placeholder")
            items: List[HotItem] = []
            for index, node in enumerate(nodes[: self.max_items], start=1):
                title_node = node.css_first(".plc-title")
                link_node = node.css_first("a")
                if not title_node or not link_node:
                    continue
                title = title_node.text(strip=True)
                href = link_node.attributes.get("href", "")
                cover_node = node.css_first("img")
                review_node = node.css_first(".review-num")
                items.append(
                    HotItem(
                        rank=index,
                        title=title,
                        url=self.build_public_url(href),
                        hotValue=self.extract_digits(review_node.text(strip=True) if review_node else ""),
                        cover=self.normalize_url(
                            self.stringify(
                                (cover_node.attributes.get("data-original") if cover_node else None)
                                or (cover_node.attributes.get("src") if cover_node else None)
                            )
                        ),
                    )
                )
            return self.build_snapshot(items)
        except Exception as exc:
            raise self.upstream_error() from exc

    def build_public_url(self, href: str) -> str:
        article_id = self.extract_article_id(href)
        if not article_id:
            return self.endpoint
        if len(article_id) <= 3:
            return "https://www.ithome.com/{0}.htm".format(article_id)
        return "https://www.ithome.com/0/{0}/{1}.htm".format(article_id[:3], article_id[3:])

    @staticmethod
    def extract_article_id(href: str) -> Optional[str]:
        matched = ITHOME_ARTICLE_PATTERN.search(href or "")
        if not matched:
            return None
        return matched.group(1)

    @staticmethod
    def extract_digits(text: str) -> Optional[str]:
        digits = "".join(char for char in text if char.isdigit())
        return digits or None
