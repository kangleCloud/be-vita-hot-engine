"""Base adapter utilities for upstream hot source fetchers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from app.core.config import Settings
from app.core.errors import UpstreamFetchError
from app.schemas.hot import HotItem, HotSourceSnapshot

if TYPE_CHECKING:
    from app.sources.catalog import SourcePreset

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


class HotSourceAdapter(ABC):
    """Common adapter behavior for upstream hot sources."""

    source_code: str = ""
    source_name: str = ""
    source_type: str = ""
    route_code: str = ""
    max_items: int = 50

    def __init__(self, settings: Settings, preset: Optional["SourcePreset"] = None) -> None:
        self.settings = settings
        self.preset = preset

    @abstractmethod
    async def fetch(self) -> HotSourceSnapshot:
        """Fetch and normalize a single source snapshot."""

    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        }

    def build_snapshot(
        self,
        items: List[HotItem],
        *,
        source_name: Optional[str] = None,
        fetched_at: Optional[datetime] = None,
        source_type: Optional[str] = None,
    ) -> HotSourceSnapshot:
        return HotSourceSnapshot(
            sourceCode=self.current_source_code,
            routeCode=self.current_route_code,
            sourceName=source_name or self.current_source_name,
            sourceType=source_type or self.current_source_type,
            fetchedAt=fetched_at or datetime.now(timezone.utc),
            items=items[: self.max_items],
        )

    def upstream_error(self) -> UpstreamFetchError:
        return UpstreamFetchError(self.current_source_code)

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        data_body: Optional[Any] = None,
    ) -> Any:
        response = await self.request(
            url,
            method=method,
            headers=headers,
            params=params,
            json_body=json_body,
            data_body=data_body,
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
        data_body: Optional[Any] = None,
    ) -> str:
        response = await self.request(
            url,
            method=method,
            headers=headers,
            params=params,
            json_body=json_body,
            data_body=data_body,
        )
        return response.text

    async def request_bytes(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        data_body: Optional[Any] = None,
    ) -> bytes:
        response = await self.request(
            url,
            method=method,
            headers=headers,
            params=params,
            json_body=json_body,
            data_body=data_body,
        )
        return response.content

    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        data_body: Optional[Any] = None,
    ) -> httpx.Response:
        # 所有上游请求都经过同一层封装，统一超时、重定向策略和异常语义。
        merged_headers = self.default_headers()
        if headers:
            merged_headers.update(headers)
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.hot_http_timeout,
                follow_redirects=True,
                headers=merged_headers,
                trust_env=False,
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    data=data_body,
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

    @property
    def current_source_code(self) -> str:
        # catalog 物化后的 preset 优先级高于适配器类上的默认元数据。
        if self.preset is not None:
            return self.preset.source_code
        return self.source_code

    @property
    def current_route_code(self) -> str:
        if self.preset is not None:
            return self.preset.route_code
        return self.route_code or self.source_code

    @property
    def current_source_name(self) -> str:
        if self.preset is not None:
            return self.preset.source_name
        return self.source_name

    @property
    def current_source_type(self) -> str:
        if self.preset is not None:
            return self.preset.source_type
        return self.source_type or self.source_name

    @staticmethod
    def stringify(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def parse_timestamp(value: Any) -> Optional[datetime]:
        # 兼容秒级/毫秒级时间戳，以及常见的 ISO、本地时间字符串格式。
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            raw_value = float(value)
            if raw_value > 10_000_000_000:
                raw_value = raw_value / 1000.0
            try:
                return datetime.fromtimestamp(raw_value, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                # 某些上游会把纯数字业务 ID 误当时间字段下发，这里回退为 None，避免整条榜单失败。
                return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.isdigit():
                return HotSourceAdapter.parse_timestamp(int(text))
            if text.count(":") == 1 and len(text) == 5:
                today = datetime.now().astimezone()
                hour, minute = text.split(":")
                return today.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0).astimezone(
                    timezone.utc
                )
            if text.startswith(("昨日 ", "昨天 ")):
                remainder = text.split(" ", 1)[1]
                parsed = HotSourceAdapter.parse_timestamp(remainder)
                if parsed is None:
                    return None
                return parsed - timedelta(days=1)
            if text.startswith("今天 "):
                return HotSourceAdapter.parse_timestamp(text.split(" ", 1)[1])
            matched = re.fullmatch(r"(\d+)\s*小时前", text)
            if matched:
                return datetime.now(timezone.utc) - timedelta(hours=int(matched.group(1)))
            matched = re.fullmatch(r"(\d+)\s*分钟前", text)
            if matched:
                return datetime.now(timezone.utc) - timedelta(minutes=int(matched.group(1)))
            matched = re.fullmatch(r"(\d{1,2})月(\d{1,2})日(?:\s+(\d{2}):(\d{2}))?", text)
            if matched:
                now = datetime.now().astimezone()
                hour = int(matched.group(3) or "0")
                minute = int(matched.group(4) or "0")
                return now.replace(
                    month=int(matched.group(1)),
                    day=int(matched.group(2)),
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                ).astimezone(timezone.utc)
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
                    hyphen_hour = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(\d{2})", text)
                    if hyphen_hour:
                        parsed = datetime.strptime(
                            "{0} {1}:00:00".format(hyphen_hour.group(1), hyphen_hour.group(2)),
                            "%Y-%m-%d %H:%M:%S",
                        )
                    else:
                        try:
                            parsed = parsedate_to_datetime(text)
                        except (TypeError, ValueError):
                            return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None
