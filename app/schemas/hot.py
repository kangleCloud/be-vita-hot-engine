"""Schema models for hot source responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_serializer


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
    service: str
    environment: str


class HotItem(BaseModel):
    """Single hot-list item."""

    rank: int = Field(ge=1)
    title: str
    url: str
    hotValue: Optional[str] = None
    cover: Optional[str] = None
    summary: Optional[str] = None
    publishedAt: Optional[datetime] = None

    @field_serializer("publishedAt", when_used="json")
    def serialize_published_at(self, value: Optional[datetime]) -> Optional[str]:
        return _serialize_datetime(value)


class HotSourceSnapshot(BaseModel):
    """Normalized hot source snapshot."""

    sourceCode: str
    routeCode: str
    sourceName: str
    sourceType: str
    fetchedAt: datetime
    items: List[HotItem]

    @field_serializer("fetchedAt", when_used="json")
    def serialize_fetched_at(self, value: datetime) -> str:
        serialized = _serialize_datetime(value)
        return serialized or ""


class HotSourceInfo(BaseModel):
    """Source metadata."""

    sourceCode: str
    routeCode: str
    iconKey: str
    sourceName: str
    sourceType: str
    description: str = ""
    enabled: bool = True
    defaultVisible: bool = False


class HotSourcesResponse(BaseModel):
    """Enabled source list."""

    sources: List[HotSourceInfo]
