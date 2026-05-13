"""API contract tests for hot endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import SourceNotFoundError
from app.main import create_app
from app.schemas.hot import HotItem, HotSourceInfo, HotSourceSnapshot, HotSourcesResponse
from app.services.hot_service import HotService, get_hot_service


class StubHotService:
    """Minimal stub service for API tests."""

    def list_sources(self) -> HotSourcesResponse:
        return HotSourcesResponse(
            sources=[
                HotSourceInfo(
                    sourceCode="weibo",
                    routeCode="weibo",
                    iconKey="weibo",
                    sourceName="微博",
                    sourceType="热搜榜",
                    description="实时热点，每分钟更新一次",
                    enabled=True,
                    defaultVisible=True,
                ),
                HotSourceInfo(
                    sourceCode="github__weekly",
                    routeCode="github",
                    iconKey="github",
                    sourceName="GitHub 趋势",
                    sourceType="周榜",
                    description="",
                    enabled=True,
                    defaultVisible=False,
                ),
            ]
        )

    async def get_source_snapshot(self, source_code: str) -> HotSourceSnapshot:
        if source_code != "weibo":
            raise SourceNotFoundError(source_code)
        return HotSourceSnapshot(
            sourceCode="weibo",
            routeCode="weibo",
            sourceName="微博热搜",
            sourceType="热搜榜",
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


def build_hostloc_guide_html(title: str) -> str:
    return """
    <table class="dt">
      <tr>
        <th><a href="thread-123-1-1.html">{0}</a></th>
        <td class="by">
          <a href="forum-45-1.html">美国VPS综合讨论</a>
          <cite><a href="space-uid-1.html">米唐</a></cite>
          <em>2 小时前</em>
        </td>
        <td class="num">
          <a href="thread-123-1-1.html">6</a>
          <em>290</em>
        </td>
        <td class="by">
          <cite><a href="space-uid-2.html">rqp</a></cite>
          <em>2 分钟前</em>
        </td>
      </tr>
    </table>
    """.format(title)


def build_producthunt_feed(title: str) -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Product Hunt</title>
      <entry>
        <id>tag:www.producthunt.com,2005:/posts/example</id>
        <title>{0}</title>
        <link href="https://www.producthunt.com/posts/example"/>
        <updated>2026-05-12T00:01:00-07:00</updated>
        <author><name>OpenAI</name></author>
        <summary type="html">&lt;p&gt;Product summary&lt;/p&gt;</summary>
      </entry>
    </feed>
    """.format(title)


def mock_regression_source(router: respx.MockRouter, source_code: str) -> str:
    if source_code == "douyin":
        router.get("https://www.douyin.com/passport/general/login_guiding_strategy/?aid=6383").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"error_code": 4031}},
            )
        )
        router.get(
            "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "word_list": [
                            {
                                "sentence_id": "1001",
                                "word": "抖音热榜测试",
                                "event_time": "1715400000",
                                "hot_value": 987654,
                            }
                        ]
                    }
                },
            )
        )
        return "抖音热榜测试"
    hostloc_sources = {
        "hostloc": ("hot", "Hostloc 热门测试"),
        "hostloc__digest": ("digest", "Hostloc 精华测试"),
        "hostloc__new": ("new", "Hostloc 最新回复测试"),
        "hostloc__newthread": ("newthread", "Hostloc 最新发布测试"),
    }
    if source_code in hostloc_sources:
        rank_type, title = hostloc_sources[source_code]
        router.get("https://hostloc.com/forum.php?mod=guide&view={0}".format(rank_type)).mock(
            return_value=httpx.Response(200, text=build_hostloc_guide_html(title))
        )
        return title
    if source_code == "producthunt":
        router.get("https://www.producthunt.com/feed").mock(
            return_value=httpx.Response(200, text=build_producthunt_feed("Product Hunt 测试"))
        )
        return "Product Hunt 测试"
    if source_code == "toutiao":
        router.get("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "ClusterIdStr": "7450000000000000001",
                            "Title": "今日头条热点测试",
                            "HotValue": 654321,
                            "Image": {"url": "https://img.example.com/toutiao.jpg"},
                        }
                    ]
                },
            )
        )
        return "今日头条热点测试"
    miyoushe_source = {
        "genshin": ("2", "genshin 新闻测试"),
        "honkai": ("1", "honkai 新闻测试"),
        "starrail": ("6", "starrail 新闻测试"),
    }
    if source_code not in miyoushe_source:
        raise AssertionError("unsupported regression source: {0}".format(source_code))
    game_id, title = miyoushe_source[source_code]
    router.get(
        "https://bbs-api-static.miyoushe.com/painter/wapi/getNewsList?client_type=4&gids={0}&last_id=&page_size=20&type=1".format(
            game_id
        )
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "list": [
                        {
                            "post": {
                                "post_id": "9988",
                                "subject": title,
                                "content": "正文摘要",
                                "cover": "https://img.example.com/{0}.jpg".format(source_code),
                                "created_at": 1715400000,
                                "view_status": 12345,
                            },
                            "user": {"nickname": "米游社用户"},
                        }
                    ]
                }
            },
        )
    )
    return title


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
            {
                "sourceCode": "weibo",
                "routeCode": "weibo",
                "iconKey": "weibo",
                "sourceName": "微博",
                "sourceType": "热搜榜",
                "description": "实时热点，每分钟更新一次",
                "enabled": True,
                "defaultVisible": True,
            },
            {
                "sourceCode": "github__weekly",
                "routeCode": "github",
                "iconKey": "github",
                "sourceName": "GitHub 趋势",
                "sourceType": "周榜",
                "description": "",
                "enabled": True,
                "defaultVisible": False,
            },
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
    assert body["routeCode"] == "weibo"
    assert body["sourceName"] == "微博热搜"
    assert body["sourceType"] == "热搜榜"
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


def test_real_sources_list_reflects_removed_routes(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.delenv("HOT_DAILYHOT_BASE_URL", raising=False)
    get_settings.cache_clear()
    get_hot_service.cache_clear()
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/api/v1/hot/sources", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert all(source["routeCode"] != "miyoushe" for source in body["sources"])
    assert all(not source["sourceCode"].startswith("miyoushe") for source in body["sources"])
    assert all(source["sourceCode"] != "coolapk" for source in body["sources"])
    assert all(source["sourceCode"] != "earthquake" for source in body["sources"])
    assert all(source["sourceCode"] != "gameres" for source in body["sources"])
    assert all(source["sourceCode"] != "linuxdo" for source in body["sources"])
    assert all(not source["sourceCode"].startswith("nytimes") for source in body["sources"])
    assert all(source["sourceCode"] != "nodeseek" for source in body["sources"])
    assert all(not source["sourceCode"].startswith("v2ex") for source in body["sources"])
    assert any(source["sourceCode"] == "douyin" for source in body["sources"])
    assert any(source["sourceCode"] == "genshin" for source in body["sources"])
    assert any(source["sourceCode"] == "honkai" for source in body["sources"])
    assert any(source["sourceCode"] == "hostloc" for source in body["sources"])
    assert any(source["sourceCode"] == "hostloc__digest" for source in body["sources"])
    assert any(source["sourceCode"] == "hostloc__new" for source in body["sources"])
    assert any(source["sourceCode"] == "hostloc__newthread" for source in body["sources"])
    assert any(source["sourceCode"] == "producthunt" for source in body["sources"])
    assert any(source["sourceCode"] == "starrail__3" for source in body["sources"])


@pytest.mark.parametrize("source_code", ["miyoushe", "miyoushe__5__1", "miyoushe__6__3"])
def test_removed_miyoushe_sources_return_404(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
    source_code: str,
) -> None:
    monkeypatch.delenv("HOT_DAILYHOT_BASE_URL", raising=False)
    get_settings.cache_clear()
    get_hot_service.cache_clear()
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/api/v1/hot/{0}".format(source_code), headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {
        "code": "source_not_found",
        "detail": "source not found: {0}".format(source_code),
        "sourceCode": source_code,
    }


@pytest.mark.parametrize(
    "source_code",
    [
        "coolapk",
        "earthquake",
        "gameres",
        "linuxdo",
        "nodeseek",
        "nytimes",
        "nytimes__global",
        "v2ex",
        "v2ex__latest",
    ],
)
def test_removed_unstable_sources_return_404(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
    source_code: str,
) -> None:
    monkeypatch.delenv("HOT_DAILYHOT_BASE_URL", raising=False)
    get_settings.cache_clear()
    get_hot_service.cache_clear()
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/api/v1/hot/{0}".format(source_code), headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {
        "code": "source_not_found",
        "detail": "source not found: {0}".format(source_code),
        "sourceCode": source_code,
    }


@pytest.mark.parametrize(
    ("source_code", "expected_route_code"),
    [
        ("douyin", "douyin"),
        ("hostloc", "hostloc"),
        ("hostloc__digest", "hostloc"),
        ("hostloc__new", "hostloc"),
        ("hostloc__newthread", "hostloc"),
        ("producthunt", "producthunt"),
        ("toutiao", "toutiao"),
        ("genshin", "genshin"),
        ("honkai", "honkai"),
        ("starrail", "starrail"),
    ],
)
def test_get_source_regression_routes_work_without_dailyhot_mirror(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
    source_code: str,
    expected_route_code: str,
) -> None:
    monkeypatch.delenv("HOT_DAILYHOT_BASE_URL", raising=False)
    get_settings.cache_clear()
    get_hot_service.cache_clear()
    application = create_app()

    with TestClient(application) as client:
        with respx.mock(assert_all_called=True) as router:
            expected_title = mock_regression_source(router, source_code)
            response = client.get("/api/v1/hot/{0}".format(source_code), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sourceCode"] == source_code
    assert body["routeCode"] == expected_route_code
    assert body["fetchedAt"].endswith("Z")
    assert body["items"][0]["rank"] == 1
    assert body["items"][0]["title"] == expected_title


def test_get_source_returns_502_for_invalid_upstream_payload(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.delenv("HOT_DAILYHOT_BASE_URL", raising=False)
    get_settings.cache_clear()
    get_hot_service.cache_clear()
    application = create_app()

    with TestClient(application) as client:
        with respx.mock(assert_all_called=True) as router:
            router.get("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc").mock(
                return_value=httpx.Response(200, json={"data": {}})
            )
            response = client.get("/api/v1/hot/toutiao", headers=auth_headers)

    assert response.status_code == 502
    assert response.json() == {
        "code": "upstream_fetch_failed",
        "detail": "failed to fetch source toutiao",
        "sourceCode": "toutiao",
    }
