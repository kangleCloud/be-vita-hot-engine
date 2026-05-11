"""Adapter unit tests with mocked upstream responses."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Tuple, Type

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.errors import UpstreamFetchError
from app.schemas.hot import HotSourceSnapshot
from app.sources.baidu import BaiduHotSource
from app.sources.base import HotSourceAdapter
from app.sources.bilibili import BilibiliHotSource
from app.sources.hot36kr import Kr36HotSource
from app.sources.ithome import ITHomeHotSource
from app.sources.juejin import JuejinHotSource
from app.sources.sspai import SSPaiHotSource
from app.sources.weibo import WeiboHotSource
from app.sources.zhihu import ZhihuHotSource

AdapterCase = Tuple[str, Type[HotSourceAdapter], str, str, Dict[str, Any], Callable[[HotSourceSnapshot], None]]


def assert_ranked_snapshot(snapshot: HotSourceSnapshot, source_code: str, source_name: str) -> None:
    assert snapshot.sourceCode == source_code
    assert snapshot.sourceName == source_name
    assert snapshot.fetchedAt.tzinfo is not None
    assert snapshot.items
    assert snapshot.items[0].rank == 1
    assert snapshot.items[0].title
    assert snapshot.items[0].url.startswith("https://")


SUCCESS_CASES: List[AdapterCase] = [
    (
        "weibo",
        WeiboHotSource,
        "GET",
        "https://weibo.com/ajax/side/hotSearch",
        {
            "json": {
                "data": {
                    "realtime": [
                        {
                            "word": "微博热搜一",
                            "num": 123456,
                            "word_scheme": "#微博热搜一#",
                            "onboard_time": 1715400000,
                        }
                    ]
                }
            }
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "weibo", "微博热搜"),
    ),
    (
        "zhihu",
        ZhihuHotSource,
        "GET",
        r"^https://api\.zhihu\.com/topstory/hot-lists/total\?limit=50$",
        {
            "json": {
                "data": [
                    {
                        "detail_text": "1234 万热度",
                        "target": {
                            "id": 1001,
                            "title": "知乎问题一",
                            "excerpt": "问题摘要",
                            "created": 1715400000,
                            "children": [{"thumbnail": "https://img.zhimg.com/1.jpg"}],
                        },
                    }
                ]
            }
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "zhihu", "知乎热榜"),
    ),
    (
        "baidu",
        BaiduHotSource,
        "GET",
        "https://top.baidu.com/board?tab=realtime",
        {
            "text": """
                <html>
                <!--s-data:{"data":{"cards":[{"component":"hotList","content":[{"word":"百度热搜一","query":"百度热搜一","rawUrl":"https://www.baidu.com/s?wd=test","hotScore":"987654","desc":"摘要"}]}]}}-->
                </html>
            """,
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "baidu", "百度热搜"),
    ),
    (
        "bilibili",
        BilibiliHotSource,
        "GET",
        r"^https://api\.bilibili\.com/x/web-interface/ranking\?rid=0&type=all&jsonp=jsonp$",
        {
            "json": {
                "data": {
                    "list": [
                        {
                            "bvid": "BV1xx411c7mD",
                            "title": "B站热门视频",
                            "video_review": 45678,
                            "desc": "视频简介",
                            "pic": "https://i0.hdslb.com/test.jpg",
                            "pubdate": 1715400000,
                        }
                    ]
                }
            }
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "bilibili", "哔哩哔哩"),
    ),
    (
        "juejin",
        JuejinHotSource,
        "GET",
        r"^https://api\.juejin\.cn/content_api/v1/content/article_rank\?category_id=1&type=hot$",
        {
            "json": {
                "data": [
                    {
                        "content": {
                            "content_id": "1234567890",
                            "title": "掘金热门文章",
                            "ctime": 1715400000,
                        },
                        "content_counter": {"hot_rank": 8888},
                    }
                ]
            }
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "juejin", "稀土掘金"),
    ),
    (
        "ithome",
        ITHomeHotSource,
        "GET",
        "https://m.ithome.com/rankm/",
        {
            "text": """
                <div class="rank-box">
                  <div class="placeholder">
                    <a href="/html/123456.htm"></a>
                    <span class="plc-title">IT之家热门</span>
                    <span class="review-num">评论 999</span>
                    <img data-original="https://img.ithome.com/test.jpg" />
                  </div>
                </div>
            """,
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "ithome", "IT之家"),
    ),
    (
        "36kr",
        Kr36HotSource,
        "POST",
        "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot",
        {
            "json": {
                "data": {
                    "hotRankList": [
                        {
                            "templateMaterial": {
                                "itemId": 123456,
                                "widgetTitle": "36氪热门",
                                "statCollect": 2468,
                                "widgetImage": "https://img.36krcdn.com/test.jpg",
                                "summary": "摘要",
                                "publishTime": "2026-05-11T12:00:00Z",
                            }
                        }
                    ]
                }
            }
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "36kr", "36氪"),
    ),
    (
        "sspai",
        SSPaiHotSource,
        "GET",
        r"^https://sspai\.com/api/v1/article/tag/page/get\?limit=50&tag=%E7%83%AD%E9%97%A8%E6%96%87%E7%AB%A0$",
        {
            "json": {
                "data": [
                    {
                        "id": 10086,
                        "title": "少数派热门文章",
                        "like_count": 2333,
                        "banner": "https://cdn.sspai.com/banner.jpg",
                        "summary": "文章摘要",
                        "released_time": 1715400000,
                    }
                ]
            }
        },
        lambda snapshot: assert_ranked_snapshot(snapshot, "sspai", "少数派"),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", SUCCESS_CASES, ids=[case[0] for case in SUCCESS_CASES])
async def test_each_adapter_can_normalize_success_response(case: AdapterCase, settings: Settings) -> None:
    name, adapter_class, method, url_pattern, response_payload, assertion = case
    adapter = adapter_class(settings)
    route_pattern = re.compile(url_pattern) if url_pattern.startswith("^") else url_pattern
    with respx.mock(assert_all_called=True) as router:
        router.route(method=method, url=route_pattern).mock(return_value=build_response(response_payload))
        snapshot = await adapter.fetch()
    assertion(snapshot)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", SUCCESS_CASES, ids=[case[0] for case in SUCCESS_CASES])
async def test_each_adapter_raises_upstream_error_on_http_failure(case: AdapterCase, settings: Settings) -> None:
    name, adapter_class, method, url_pattern, _, _ = case
    adapter = adapter_class(settings)
    route_pattern = re.compile(url_pattern) if url_pattern.startswith("^") else url_pattern
    with respx.mock(assert_all_called=True) as router:
        router.route(method=method, url=route_pattern).mock(return_value=httpx.Response(500, text="boom"))
        with pytest.raises(UpstreamFetchError) as exc_info:
            await adapter.fetch()
    assert exc_info.value.error_code == "upstream_fetch_failed"
    assert exc_info.value.source_code == name


def build_response(payload: Dict[str, Any]) -> httpx.Response:
    if "json" in payload:
        return httpx.Response(200, json=payload["json"])
    return httpx.Response(200, text=payload["text"])
