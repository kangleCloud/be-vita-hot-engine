"""Adapter unit tests with mocked native upstream responses."""

from __future__ import annotations

import re

import httpx
import pytest
import respx

from app.core.config import Settings, get_settings
from app.core.errors import UpstreamFetchError
from app.sources import base as base_module
from app.sources.catalog import SourcePreset
from app.sources.mirror import DailyHotMirrorSource


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


def build_preset(
    source_code: str = "weibo",
    route_code: str = "weibo",
    source_name: str = "微博",
    source_type: str = "热搜榜",
    params: dict[str, str] | None = None,
) -> SourcePreset:
    return SourcePreset(
        source_code=source_code,
        route_code=route_code,
        icon_key=route_code,
        source_name=source_name,
        source_type=source_type,
        description="",
        default_visible=True,
        params=params or {},
    )


@pytest.mark.asyncio
async def test_request_client_disables_system_proxy_env(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured.update(kwargs)

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def request(self, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                200,
                json={"ok": True},
                request=httpx.Request("GET", str(kwargs["url"])),
            )

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setattr(base_module.httpx, "AsyncClient", DummyAsyncClient)

    adapter = DailyHotMirrorSource(settings, build_preset())
    await adapter.request("https://example.com/api")

    assert captured["trust_env"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_code", "rank_type", "payload_key"),
    [
        ("36kr", "hot", "hotRankList"),
        ("36kr__video", "video", "videoList"),
        ("36kr__comment", "comment", "remarkList"),
        ("36kr__collect", "collect", "collectList"),
    ],
)
async def test_local_adapter_normalizes_36kr_variants(
    settings: Settings,
    source_code: str,
    rank_type: str,
    payload_key: str,
) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code=source_code,
            route_code="36kr",
            source_name="36氪",
            source_type="测试榜",
            params={"type": rank_type},
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.post(f"https://gateway.36kr.com/api/mis/nav/home/nav/rank/{rank_type}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        payload_key: [
                            {
                                "itemId": "12345",
                                "publishTime": "2026-05-11T12:00:00Z",
                                "templateMaterial": {
                                    "widgetTitle": f"36kr {rank_type}",
                                    "widgetImage": "https://img.example.com/kr.jpg",
                                    "authorName": "kr",
                                    "statCollect": 42,
                                },
                            }
                        ]
                    }
                },
            )
        )
        snapshot = await adapter.fetch()

    assert snapshot.routeCode == "36kr"
    assert snapshot.items[0].title == f"36kr {rank_type}"
    assert snapshot.items[0].url == "https://www.36kr.com/p/12345"
    assert snapshot.items[0].hotValue == "42"


@pytest.mark.asyncio
async def test_local_adapter_normalizes_html_route_snapshot(settings: Settings) -> None:
    preset = build_preset(
        source_code="github__weekly",
        route_code="github",
        source_name="GitHub 趋势",
        source_type="周榜",
        params={"type": "weekly"},
    )
    adapter = DailyHotMirrorSource(settings, preset)
    html = """
    <article class="Box-row">
      <h2><a href="/example/repo"> example / repo </a></h2>
      <p class="col-9 color-fg-muted">Weekly trending repository</p>
      <a href="/example/repo/stargazers">12,345</a>
      <a href="/example/repo/forks">321</a>
    </article>
    """
    with respx.mock(assert_all_called=True) as router:
        router.get("https://github.com/trending?since=weekly").mock(
            return_value=httpx.Response(200, text=html)
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "github__weekly"
    assert snapshot.items[0].title == "repo"
    assert snapshot.items[0].url == "https://github.com/example/repo"
    assert snapshot.items[0].summary == "Weekly trending repository"


@pytest.mark.asyncio
async def test_local_adapter_normalizes_special_route_snapshot(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="bilibili",
            route_code="bilibili",
            source_name="哔哩哔哩",
            source_type="热榜 · 全站",
            params={"type": "0"},
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get("https://api.bilibili.com/x/web-interface/nav").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "wbi_img": {
                            "img_url": "https://i0.hdslb.com/bfs/wbi/abcdef.png",
                            "sub_url": "https://i0.hdslb.com/bfs/wbi/ghijkl.png",
                        }
                    }
                },
            )
        )
        router.get(re.compile(r"https://api\.bilibili\.com/x/web-interface/ranking/v2\?rid=0&type=all&.*")).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "list": [
                            {
                                "bvid": "BV1xx411c7mD",
                                "title": "示例视频",
                                "desc": "视频简介",
                                "pic": "http://img.example.com/bili.jpg",
                                "owner": {"name": "up"},
                                "pubdate": 1715400000,
                                "stat": {"view": 8888},
                                "short_link_v2": "https://b23.tv/example",
                            }
                        ]
                    }
                },
            )
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "bilibili"
    assert snapshot.items[0].url == "https://b23.tv/example"
    assert snapshot.items[0].cover == "https://img.example.com/bili.jpg"
    assert snapshot.items[0].hotValue == "8888"


@pytest.mark.asyncio
async def test_local_adapter_normalizes_rss_route_snapshot(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="52pojie",
            route_code="52pojie",
            source_name="吾爱破解",
            source_type="最新精华",
            params={"type": "digest"},
        ),
    )
    rss = """<?xml version="1.0" encoding="gbk"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>latest digest</title>
          <link>https://www.52pojie.cn/thread-1-1-1.html</link>
          <guid>thread-1</guid>
          <pubDate>Tue, 11 May 2026 12:00:00 GMT</pubDate>
          <description>digest content</description>
        </item>
      </channel>
    </rss>
    """
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.52pojie.cn/forum.php?mod=guide&view=digest&rss=1").mock(
            return_value=httpx.Response(200, content=rss.encode("gbk", errors="ignore"))
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "52pojie"
    assert snapshot.items[0].title == "latest digest"
    assert snapshot.items[0].summary == "digest content"
    assert snapshot.items[0].publishedAt is not None


@pytest.mark.asyncio
async def test_local_adapter_normalizes_douyin_snapshot(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="douyin",
            route_code="douyin",
            source_name="抖音",
            source_type="热榜",
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.douyin.com/passport/general/login_guiding_strategy/?aid=6383").mock(
            return_value=httpx.Response(
                200,
                headers=[
                    ("set-cookie", "ttwid=abc; Path=/; HttpOnly"),
                    ("set-cookie", "passport_csrf_token=csrf-token; Path=/; HttpOnly"),
                ],
                json={"status_code": 0},
            )
        )
        hot_route = router.get(
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
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "douyin"
    assert snapshot.items[0].title == "抖音热榜测试"
    assert snapshot.items[0].url == "https://www.douyin.com/hot/1001"
    assert snapshot.items[0].hotValue == "987654"
    assert hot_route.calls[0].request.headers["Referer"] == "https://www.douyin.com/"
    assert hot_route.calls[0].request.headers["Cookie"] == "passport_csrf_token=csrf-token"


@pytest.mark.asyncio
async def test_local_adapter_normalizes_douyin_snapshot_without_cookie_token(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="douyin",
            route_code="douyin",
            source_name="抖音",
            source_type="热榜",
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.douyin.com/passport/general/login_guiding_strategy/?aid=6383").mock(
            return_value=httpx.Response(200, json={"data": {"error_code": 4031}})
        )
        hot_route = router.get(
            "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "word_list": [
                            {
                                "sentence_id": "1002",
                                "word": "抖音降级热榜测试",
                                "event_time": "1715400001",
                                "hot_value": 123456,
                            }
                        ]
                    }
                },
            )
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "douyin"
    assert snapshot.items[0].title == "抖音降级热榜测试"
    assert snapshot.items[0].hotValue == "123456"
    assert hot_route.calls[0].request.headers["Referer"] == "https://www.douyin.com/"
    assert "Cookie" not in hot_route.calls[0].request.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_code", "rank_type", "title"),
    [
        ("hostloc", "hot", "Hostloc 热门测试"),
        ("hostloc__digest", "digest", "Hostloc 精华测试"),
        ("hostloc__new", "new", "Hostloc 最新回复测试"),
        ("hostloc__newthread", "newthread", "Hostloc 最新发布测试"),
    ],
)
async def test_local_adapter_normalizes_hostloc_variants(
    settings: Settings,
    source_code: str,
    rank_type: str,
    title: str,
) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code=source_code,
            route_code="hostloc",
            source_name="Hostloc",
            source_type="测试榜",
            params={"type": rank_type},
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get("https://hostloc.com/forum.php?mod=guide&view={0}".format(rank_type)).mock(
            return_value=httpx.Response(200, text=build_hostloc_guide_html(title))
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == source_code
    assert snapshot.routeCode == "hostloc"
    assert snapshot.items[0].title == title
    assert snapshot.items[0].url == "https://hostloc.com/thread-123-1-1.html"
    assert snapshot.items[0].hotValue == "6"
    assert snapshot.items[0].summary is not None
    assert "版块：美国VPS综合讨论" in snapshot.items[0].summary
    assert "作者：米唐" in snapshot.items[0].summary
    assert "回复/查看：6/290" in snapshot.items[0].summary
    assert snapshot.items[0].publishedAt is not None


@pytest.mark.asyncio
async def test_local_adapter_normalizes_producthunt_feed(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="producthunt",
            route_code="producthunt",
            source_name="Product Hunt",
            source_type="新品",
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.producthunt.com/feed").mock(
            return_value=httpx.Response(200, text=build_producthunt_feed("Product Hunt 测试"))
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "producthunt"
    assert snapshot.items[0].title == "Product Hunt 测试"
    assert snapshot.items[0].url == "https://www.producthunt.com/posts/example"
    assert snapshot.items[0].summary == "Product summary"
    assert snapshot.items[0].hotValue is None
    assert snapshot.items[0].publishedAt is not None


@pytest.mark.asyncio
async def test_local_adapter_normalizes_toutiao_snapshot(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="toutiao",
            route_code="toutiao",
            source_name="今日头条",
            source_type="热榜",
        ),
    )
    with respx.mock(assert_all_called=True) as router:
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
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "toutiao"
    assert snapshot.items[0].title == "今日头条热点测试"
    assert snapshot.items[0].url == "https://www.toutiao.com/trending/7450000000000000001/"
    assert snapshot.items[0].cover == "https://img.example.com/toutiao.jpg"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_code", "route_code", "slug", "game_id"),
    [
        ("genshin", "genshin", "ys", "2"),
        ("honkai", "honkai", "bh3", "1"),
        ("starrail", "starrail", "sr", "6"),
    ],
)
async def test_local_adapter_normalizes_miyoushe_variants(
    settings: Settings,
    source_code: str,
    route_code: str,
    slug: str,
    game_id: str,
) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code=source_code,
            route_code=route_code,
            source_name=source_code,
            source_type="公告",
            params={"type": "1"},
        ),
    )
    route_url = (
        "https://bbs-api-static.miyoushe.com/painter/wapi/getNewsList"
        "?client_type=4&gids={0}&last_id=&page_size=20&type=1"
    ).format(game_id)
    with respx.mock(assert_all_called=True) as router:
        router.get(route_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "list": [
                            {
                                "post": {
                                    "post_id": "9988",
                                    "subject": "{0} 新闻测试".format(source_code),
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
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == source_code
    assert snapshot.items[0].title == "{0} 新闻测试".format(source_code)
    assert snapshot.items[0].url == "https://www.miyoushe.com/{0}/article/9988".format(slug)
    assert snapshot.items[0].hotValue == "12345"


@pytest.mark.asyncio
async def test_history_route_resolves_today_request_params(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="history",
            route_code="history",
            source_name="历史上的今天",
            source_type="今日",
            params={"month": "__today__", "day": "__today__"},
        ),
    )
    params = adapter.resolve_request_params()
    assert params["month"].isdigit()
    assert params["day"].isdigit()


@pytest.mark.asyncio
async def test_local_routes_do_not_depend_on_dailyhot_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOT_DAILYHOT_BASE_URL", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    adapter = DailyHotMirrorSource(settings, build_preset())
    with respx.mock(assert_all_called=True) as router:
        router.get("https://weibo.com/ajax/side/hotSearch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "realtime": [
                            {
                                "mid": "1",
                                "word": "微博热搜一",
                                "word_scheme": "#微博热搜一#",
                                "onboard_time": 1715400000,
                            }
                        ]
                    }
                },
            )
        )
        snapshot = await adapter.fetch()

    assert snapshot.sourceCode == "weibo"
    assert snapshot.items[0].title == "微博热搜一"


@pytest.mark.asyncio
async def test_local_adapter_raises_upstream_error_on_non_json_toutiao_response(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="toutiao",
            route_code="toutiao",
            source_name="今日头条",
            source_type="热榜",
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc").mock(
            return_value=httpx.Response(200, text="<html>oops</html>")
        )
        with pytest.raises(UpstreamFetchError) as exc_info:
            await adapter.fetch()

    assert exc_info.value.error_code == "upstream_fetch_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_code", "route_code", "params", "responses"),
    [
        (
            "douyin",
            "douyin",
            {},
            [
                (
                    "https://www.douyin.com/passport/general/login_guiding_strategy/?aid=6383",
                    httpx.Response(
                        200,
                        headers=[("set-cookie", "passport_csrf_token=csrf-token; Path=/; HttpOnly")],
                        json={"status_code": 0},
                    ),
                ),
                (
                    "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1",
                    httpx.Response(200, json={"data": {"word_list": {}}}),
                ),
            ],
        ),
        (
            "toutiao",
            "toutiao",
            {},
            [
                (
                    "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
                    httpx.Response(200, json={"data": {}}),
                )
            ],
        ),
        (
            "genshin",
            "genshin",
            {"type": "1"},
            [
                (
                    "https://bbs-api-static.miyoushe.com/painter/wapi/getNewsList?client_type=4&gids=2&last_id=&page_size=20&type=1",
                    httpx.Response(200, json={"data": {"list": {}}}),
                )
            ],
        ),
        (
            "honkai",
            "honkai",
            {"type": "1"},
            [
                (
                    "https://bbs-api-static.miyoushe.com/painter/wapi/getNewsList?client_type=4&gids=1&last_id=&page_size=20&type=1",
                    httpx.Response(200, json={"data": {"list": {}}}),
                )
            ],
        ),
        (
            "starrail",
            "starrail",
            {"type": "1"},
            [
                (
                    "https://bbs-api-static.miyoushe.com/painter/wapi/getNewsList?client_type=4&gids=6&last_id=&page_size=20&type=1",
                    httpx.Response(200, json={"data": {"list": {}}}),
                )
            ],
        ),
    ],
)
async def test_local_adapter_raises_upstream_error_on_missing_expected_collections(
    settings: Settings,
    source_code: str,
    route_code: str,
    params: dict[str, str],
    responses: list[tuple[str, httpx.Response]],
) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code=source_code,
            route_code=route_code,
            source_name=source_code,
            source_type="测试榜",
            params=params,
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        for url, response in responses:
            router.get(url).mock(return_value=response)
        with pytest.raises(UpstreamFetchError) as exc_info:
            await adapter.fetch()

    assert exc_info.value.error_code == "upstream_fetch_failed"


@pytest.mark.asyncio
async def test_local_adapter_raises_upstream_error_on_invalid_response(settings: Settings) -> None:
    adapter = DailyHotMirrorSource(
        settings,
        build_preset(
            source_code="36kr",
            route_code="36kr",
            source_name="36氪",
            source_type="人气榜",
            params={"type": "hot"},
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        router.post("https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot").mock(
            return_value=httpx.Response(500, json={"message": "boom"})
        )
        with pytest.raises(UpstreamFetchError) as exc_info:
            await adapter.fetch()

    assert exc_info.value.error_code == "upstream_fetch_failed"
    assert exc_info.value.source_code == "36kr"
