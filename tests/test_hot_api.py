"""API contract tests for hot endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import SourceNotFoundError
from app.schemas.hot import HotItem, HotSourceSnapshot, HotSourcesResponse, HotSourceInfo
from app.services.hot_service import HotService, get_hot_service


class StubHotService:
    """Minimal stub service for API tests."""

    def list_sources(self) -> HotSourcesResponse:
        return HotSourcesResponse(
            sources=[
                HotSourceInfo(sourceCode="weibo", sourceName="微博热搜", enabled=True),
                HotSourceInfo(sourceCode="zhihu", sourceName="知乎热榜", enabled=True),
            ]
        )

    async def get_source_snapshot(self, source_code: str) -> HotSourceSnapshot:
        if source_code != "weibo":
            raise SourceNotFoundError(source_code)
        return HotSourceSnapshot(
            sourceCode="weibo",
            sourceName="微博热搜",
            fetchedAt=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
            items=[
                HotItem(
                    rank=1,
                    title="示例标题",
                    url="https://example.com",
                    hotValue="123456",
                    cover=None,
                    summary=None,
                    publishedAt=None,
                )
            ],
        )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def stub_service() -> HotService:
    return StubHotService()  # type: ignore[return-value]


def test_list_sources_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/hot/sources")

    assert response.status_code == 401
    assert response.json() == {
        "code": "unauthorized",
        "detail": "invalid or missing bearer token",
    }


def test_get_source_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/hot/weibo")

    assert response.status_code == 401
    assert response.json() == {
        "code": "unauthorized",
        "detail": "invalid or missing bearer token",
    }


def test_list_sources_returns_fixed_contract(
    app: FastAPI,
    client: TestClient,
    auth_headers: dict[str, str],
    stub_service: HotService,
) -> None:
    app.dependency_overrides[get_hot_service] = lambda: stub_service

    response = client.get("/api/v1/hot/sources", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "sources": [
            {"sourceCode": "weibo", "sourceName": "微博热搜", "enabled": True},
            {"sourceCode": "zhihu", "sourceName": "知乎热榜", "enabled": True},
        ]
    }


def test_get_source_returns_snapshot_contract(
    app: FastAPI,
    client: TestClient,
    auth_headers: dict[str, str],
    stub_service: HotService,
) -> None:
    app.dependency_overrides[get_hot_service] = lambda: stub_service

    response = client.get("/api/v1/hot/weibo", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sourceCode"] == "weibo"
    assert body["sourceName"] == "微博热搜"
    assert body["fetchedAt"].endswith("Z")
    assert body["items"] == [
        {
            "rank": 1,
            "title": "示例标题",
            "url": "https://example.com",
            "hotValue": "123456",
            "cover": None,
            "summary": None,
            "publishedAt": None,
        }
    ]


def test_get_source_returns_404_for_unknown_source(
    app: FastAPI,
    client: TestClient,
    auth_headers: dict[str, str],
    stub_service: HotService,
) -> None:
    app.dependency_overrides[get_hot_service] = lambda: stub_service

    response = client.get("/api/v1/hot/unknown", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {
        "code": "source_not_found",
        "detail": "source not found: unknown",
        "sourceCode": "unknown",
    }
