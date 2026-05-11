"""Base adapter utilities for upstream hot source fetchers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import Settings
from app.core.errors import UpstreamFetchError
from app.schemas.hot import HotItem, HotSourceSnapshot

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


class HotSourceAdapter(ABC):
    """Common adapter behavior for upstream hot sources."""

    source_code: str = ""
    source_name: str = ""
    max_items: int = 50

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def fetch(self) -> HotSourceSnapshot:
        """Fetch and normalize a single source snapshot."""

    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        }

    def build_snapshot(self, items: List[HotItem]) -> HotSourceSnapshot:
        return HotSourceSnapshot(
            sourceCode=self.source_code,
            sourceName=self.source_name,
            fetchedAt=datetime.now(timezone.utc),
            items=items[: self.max_items],
        )

    def upstream_error(self) -> UpstreamFetchError:
        return UpstreamFetchError(self.source_code)

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        response = await self.request(
            url,
            method=method,
            headers=headers,
            params=params,
            json_body=json_body,
        )
        try:
            return response.json()
        except ValueError as exc:
            raise self.upstream_error() from exc

    async def request_text(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> str:
        response = await self.request(
            url,
            method=method,
            headers=headers,
            params=params,
            json_body=json_body,
        )
        return response.text

    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        merged_headers = self.default_headers()
        if headers:
            merged_headers.update(headers)
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.hot_http_timeout,
                follow_redirects=True,
                headers=merged_headers,
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                )
                response.raise_for_status()
                return response
        except httpx.HTTPError as exc:
            raise self.upstream_error() from exc

    @staticmethod
    def normalize_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        if url.startswith("//"):
            return "https:{0}".format(url)
        return url

    @staticmethod
    def stringify(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def parse_timestamp(value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            raw_value = float(value)
            if raw_value > 10_000_000_000:
                raw_value = raw_value / 1000.0
            return datetime.fromtimestamp(raw_value, tz=timezone.utc)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.isdigit():
                return HotSourceAdapter.parse_timestamp(int(text))
            normalized = text.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
                    try:
                        parsed = datetime.strptime(text, fmt)
                        break
                    except ValueError:
                        parsed = None
                if parsed is None:
                    return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None
