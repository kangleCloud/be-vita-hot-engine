"""Local route fetchers ported from DailyHotApi."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence
from urllib.parse import quote, unquote, urljoin

import feedparser
from selectolax.parser import HTMLParser

if TYPE_CHECKING:
    from app.sources.base import HotSourceAdapter


RouteFetcher = Callable[["HotSourceAdapter", Mapping[str, str]], Awaitable["RouteResult"]]

DEFAULT_DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)
DEFAULT_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
)
BAIDU_SDATA_PATTERN = re.compile(r"<!--s-data:(.*?)-->", re.S)
SINA_NEWS_PATTERN = re.compile(r"^var data = (?P<body>\{.*\});\s*$", re.S)
APOLLO_STATE_PREFIX = "window.__APOLLO_STATE__="
BILIBILI_MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]
@dataclass
class RouteResult:
    """Route-level raw result aligned with DailyHotApi output."""

    data: List[Dict[str, Any]]
    title: Optional[str] = None
    source_type: Optional[str] = None
    update_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def build_route_result(
    data: List[Dict[str, Any]],
    *,
    title: Optional[str] = None,
    source_type: Optional[str] = None,
) -> RouteResult:
    return RouteResult(data=data, title=title, source_type=source_type)


def parse_rss_items(content: str) -> List[Dict[str, Any]]:
    feed = feedparser.parse(content)
    items: List[Dict[str, Any]] = []
    for entry in feed.entries:
        items.append(
            {
                "title": getattr(entry, "title", None),
                "link": getattr(entry, "link", None),
                "pubDate": getattr(entry, "published", None)
                or getattr(entry, "updated", None)
                or getattr(entry, "pubDate", None),
                "author": getattr(entry, "author", None) or getattr(entry, "creator", None),
                "content": _entry_content(entry),
                "contentSnippet": getattr(entry, "summary", None),
                "guid": getattr(entry, "id", None) or getattr(entry, "guid", None),
            }
        )
    return items


def _entry_content(entry: Any) -> Optional[str]:
    content = getattr(entry, "content", None)
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return first.get("value")
        return str(first)
    return getattr(entry, "summary_detail", {}).get("value") if hasattr(entry, "summary_detail") else None


def html_to_text(fragment: Optional[str]) -> str:
    if not fragment:
        return ""
    return HTMLParser(fragment).text(separator=" ", strip=True)


def extract_first_number(text: Optional[str], default: int = 0) -> int:
    if not text:
        return default
    matched = re.search(r"\d+", text)
    if not matched:
        return default
    return int(matched.group(0))


def extract_digits(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    digits = "".join(char for char in text if char.isdigit())
    return digits or None


def expect_object(value: Any, *, field: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid upstream payload: expected object at {0}".format(field))
    return value


def expect_list(value: Any, *, field: str) -> List[Any]:
    if not isinstance(value, list):
        raise ValueError("invalid upstream payload: expected list at {0}".format(field))
    return value


def parse_chinese_number(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    text = text.strip()
    units = {"亿": 100_000_000, "万": 10_000, "千": 1_000, "百": 100}
    for unit, multiplier in units.items():
        if unit in text:
            try:
                return int(float(text.replace(unit, "")) * multiplier)
            except ValueError:
                return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def build_51cto_sign(request_path: str, payload: Mapping[str, Any], timestamp: int, token: str) -> str:
    combined = dict(payload)
    combined["timestamp"] = timestamp
    combined["token"] = token
    sorted_params = ",".join(sorted(combined.keys()))
    return hashlib.md5(
        (
            hashlib.md5(request_path.encode("utf-8")).hexdigest()
            + hashlib.md5((sorted_params + hashlib.md5(token.encode("utf-8")).hexdigest() + str(timestamp)).encode("utf-8")).hexdigest()
        ).encode("utf-8")
    ).hexdigest()


def get_mixin_key(orig: str) -> str:
    return "".join(orig[index] for index in BILIBILI_MIXIN_KEY_ENC_TAB if index < len(orig))[:32]


def build_bilibili_wbi_query(params: Mapping[str, Any], img_key: str, sub_key: str) -> str:
    mutable = {key: value for key, value in params.items()}
    mutable["wts"] = round(datetime.now().timestamp())
    mixin_key = get_mixin_key(img_key + sub_key)
    cleaned = {}
    for key, value in mutable.items():
        cleaned[key] = re.sub(r"[!'()*]", "", str(value))
    query = "&".join(
        "{0}={1}".format(quote(str(key), safe=""), quote(str(cleaned[key]), safe=""))
        for key in sorted(cleaned)
    )
    w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return "{0}&w_rid={1}".format(query, w_rid)


def build_weread_detail_id(book_id: str) -> Optional[str]:
    try:
        digest = hashlib.md5(book_id.encode("utf-8")).hexdigest()
        prefix = digest[:3]
        if book_id.isdigit():
            chunks = [hex(int(book_id[index : index + 9]))[2:] for index in range(0, len(book_id), 9)]
            parts: Sequence[str] = ["3", *chunks]
        else:
            hex_text = "".join("{0:x}".format(ord(char)) for char in book_id)
            parts = ["4", hex_text]
        assembled = prefix + parts[0] + "2" + digest[-2:]
        for index, part in enumerate(parts[1:]):
            part_length = "{0:02x}".format(len(part))
            assembled += part_length + part
            if index < len(parts[1:]) - 1:
                assembled += "g"
        if len(assembled) < 20:
            assembled += digest[: 20 - len(assembled)]
        final_digest = hashlib.md5(assembled.encode("utf-8")).hexdigest()
        return assembled + final_digest[:3]
    except Exception:
        return None


def build_ithome_public_url(href: str) -> str:
    matched = re.search(r"(?:html|live)/(\d+)\.htm", href or "")
    if not matched:
        return href
    article_id = matched.group(1)
    if len(article_id) <= 3:
        return "https://www.ithome.com/{0}.htm".format(article_id)
    return "https://www.ithome.com/0/{0}/{1}.htm".format(article_id[:3], article_id[3:])


def build_ithome_xijiayi_mobile_url(href: str) -> str:
    matched = re.search(r"https://www\.ithome\.com/0/(\d+)/(\d+)\.htm", href or "")
    if not matched:
        return href
    return "https://m.ithome.com/html/{0}{1}.htm".format(matched.group(1), matched.group(2))


async def fetch_token_51cto(adapter: "HotSourceAdapter") -> str:
    payload = await adapter.request_json("https://api-media.51cto.com/api/token-get")
    return str(payload["data"]["data"]["token"])


async def fetch_douyin_cookie(adapter: "HotSourceAdapter") -> Optional[str]:
    try:
        response = await adapter.request(
            "https://www.douyin.com/passport/general/login_guiding_strategy/?aid=6383",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.douyin.com/",
                "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
            },
        )
    except Exception:
        return None
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        error_code = payload.get("data", {}).get("error_code")
        if error_code == 4031:
            return None
    cookie_headers = response.headers.get_list("set-cookie")
    if not cookie_headers:
        cookie_header = response.headers.get("set-cookie")
        if cookie_header:
            cookie_headers = [cookie_header]
    for cookie_header in cookie_headers:
        matched = re.search(r"passport_csrf_token=([^;]+)", cookie_header)
        if matched:
            return matched.group(1)
    return None


async def fetch_bilibili_wbi_query(adapter: "HotSourceAdapter") -> str:
    payload = await adapter.request_json(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={
            "Cookie": "SESSDATA=xxxxxx",
            "Referer": "https://www.bilibili.com/",
            "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
        },
    )
    wbi_img = payload.get("data", {}).get("wbi_img", {})
    img_url = str(wbi_img.get("img_url") or "")
    sub_url = str(wbi_img.get("sub_url") or "")
    img_key = img_url.rsplit("/", 1)[-1].split(".", 1)[0]
    sub_key = sub_url.rsplit("/", 1)[-1].split(".", 1)[0]
    return build_bilibili_wbi_query({"foo": "114", "bar": "514", "baz": 1919810}, img_key, sub_key)


async def fetch_rss_route(
    adapter: "HotSourceAdapter",
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    encoding: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if encoding:
        raw = await adapter.request_bytes(url, headers=headers)
        content = raw.decode(encoding, errors="ignore")
    else:
        content = await adapter.request_text(url, headers=headers)
    return parse_rss_items(content)


async def fetch_36kr(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "hot")
    payload = await adapter.request_json(
        "https://gateway.36kr.com/api/mis/nav/home/nav/rank/{0}".format(rank_type),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
        json_body={
            "partner_id": "wap",
            "param": {"siteId": 1, "platformId": 2},
            "timestamp": round(datetime.now().timestamp() * 1000),
        },
    )
    list_key = {
        "hot": "hotRankList",
        "video": "videoList",
        "comment": "remarkList",
        "collect": "collectList",
    }.get(rank_type, "hotRankList")
    entries = payload.get("data", {}).get(list_key, [])
    return build_route_result(
        [
            {
                "id": entry.get("itemId"),
                "title": entry.get("templateMaterial", {}).get("widgetTitle"),
                "cover": entry.get("templateMaterial", {}).get("widgetImage"),
                "author": entry.get("templateMaterial", {}).get("authorName"),
                "timestamp": entry.get("publishTime"),
                "hot": entry.get("templateMaterial", {}).get("statCollect"),
                "url": "https://www.36kr.com/p/{0}".format(entry.get("itemId")),
                "mobileUrl": "https://m.36kr.com/p/{0}".format(entry.get("itemId")),
            }
            for entry in entries
        ]
    )


async def fetch_51cto(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    base_params = {"page": 1, "page_size": 50, "limit_time": 0, "name_en": ""}
    timestamp = round(datetime.now().timestamp() * 1000)
    token = await fetch_token_51cto(adapter)
    payload = await adapter.request_json(
        "https://api-media.51cto.com/index/index/recommend",
        params={
            **base_params,
            "timestamp": timestamp,
            "token": token,
            "sign": build_51cto_sign("index/index/recommend", base_params, timestamp, token),
        },
    )
    entries = payload.get("data", {}).get("data", {}).get("list", [])
    return build_route_result(
        [
            {
                "id": entry.get("source_id"),
                "title": entry.get("title"),
                "cover": entry.get("cover"),
                "desc": entry.get("abstract"),
                "timestamp": entry.get("pubdate"),
                "url": entry.get("url"),
                "mobileUrl": entry.get("url"),
            }
            for entry in entries
        ]
    )


async def fetch_52pojie(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "digest")
    items = await fetch_rss_route(
        adapter,
        "https://www.52pojie.cn/forum.php?mod=guide&view={0}&rss=1".format(rank_type),
        headers={"User-Agent": DEFAULT_MOBILE_USER_AGENT},
        encoding="gbk",
    )
    return build_route_result(
        [
            {
                "id": item.get("guid") or index,
                "title": item.get("title"),
                "desc": (item.get("content") or "").strip(),
                "author": item.get("author"),
                "timestamp": item.get("pubDate"),
                "url": item.get("link"),
                "mobileUrl": item.get("link"),
            }
            for index, item in enumerate(items)
        ]
    )


async def fetch_acfun(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    category = params.get("type", "-1")
    period = params.get("range", "DAY")
    channel_id = "" if category == "-1" else category
    payload = await adapter.request_json(
        "https://www.acfun.cn/rest/pc-direct/rank/channel"
        "?channelId={0}&rankLimit=30&rankPeriod={1}".format(channel_id, period),
        headers={"Referer": "https://www.acfun.cn/rank/list/?cid=-1&pcid={0}&range={1}".format(category, period)},
    )
    entries = payload.get("rankList", [])
    return build_route_result(
        [
            {
                "id": entry.get("dougaId"),
                "title": entry.get("contentTitle"),
                "desc": entry.get("contentDesc"),
                "cover": entry.get("coverUrl"),
                "author": entry.get("userName"),
                "timestamp": entry.get("contributeTime"),
                "hot": entry.get("likeCount"),
                "url": "https://www.acfun.cn/v/ac{0}".format(entry.get("dougaId")),
                "mobileUrl": "https://m.acfun.cn/v/?ac={0}".format(entry.get("dougaId")),
            }
            for entry in entries
        ]
    )


async def fetch_baidu(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "realtime")
    html = await adapter.request_text(
        "https://top.baidu.com/board?tab={0}".format(rank_type),
        headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    matched = BAIDU_SDATA_PATTERN.search(html)
    if not matched:
        return build_route_result([])
    payload = json.loads(matched.group(1))
    content = payload.get("data", {}).get("cards", [{}])[0].get("content")
    if content is None:
        content = payload.get("cards", [{}])[0].get("content")
    entries = []
    if isinstance(content, list):
        if content and isinstance(content[0], dict) and isinstance(content[0].get("content"), list):
            entries = content[0]["content"]
        else:
            entries = content
    return build_route_result(
        [
            {
                "id": entry.get("index") or index + 1,
                "title": entry.get("word") or entry.get("title"),
                "desc": entry.get("desc") or "",
                "cover": entry.get("img") or entry.get("imgInfo", {}).get("src"),
                "author": entry.get("show") or "",
                "hot": int(str(entry.get("hotScore") or entry.get("hotTag") or "0").replace(",", "") or 0),
                "url": "https://www.baidu.com/s?wd={0}".format(quote(str(entry.get("query") or entry.get("word") or entry.get("title") or ""))),
                "mobileUrl": entry.get("rawUrl") or entry.get("url"),
            }
            for index, entry in enumerate(entries)
        ]
    )


async def fetch_csdn(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://blog.csdn.net/phoenix/web/blog/hot-rank?page=0&pageSize=30")
    entries = payload.get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("productId"),
                "title": entry.get("articleTitle"),
                "cover": (entry.get("picList") or [None])[0],
                "author": entry.get("nickName"),
                "timestamp": entry.get("period"),
                "hot": entry.get("hotRankScore"),
                "url": entry.get("articleDetailUrl"),
                "mobileUrl": entry.get("articleDetailUrl"),
            }
            for entry in entries
        ]
    )


async def fetch_dgtle(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://opser.api.dgtle.com/v2/news/index")
    entries = payload.get("items", [])
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title") or entry.get("content"),
                "desc": entry.get("content"),
                "cover": entry.get("cover"),
                "author": entry.get("from"),
                "timestamp": entry.get("created_at"),
                "hot": entry.get("membernum"),
                "url": "https://www.dgtle.com/news-{0}-{1}.html".format(entry.get("id"), entry.get("type")),
                "mobileUrl": "https://m.dgtle.com/news-details/{0}".format(entry.get("id")),
            }
            for entry in entries
        ]
    )


async def fetch_geekpark(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://mainssl.geekpark.net/api/v2")
    entries = payload.get("homepage_posts", [])
    return build_route_result(
        [
            {
                "id": entry.get("post", {}).get("id"),
                "title": entry.get("post", {}).get("title"),
                "desc": entry.get("post", {}).get("abstract"),
                "cover": entry.get("post", {}).get("cover_url"),
                "author": ((entry.get("post", {}).get("authors") or [{}])[0]).get("nickname"),
                "timestamp": entry.get("post", {}).get("published_timestamp"),
                "hot": entry.get("post", {}).get("views"),
                "url": "https://www.geekpark.net/news/{0}".format(entry.get("post", {}).get("id")),
                "mobileUrl": "https://www.geekpark.net/news/{0}".format(entry.get("post", {}).get("id")),
            }
            for entry in entries
        ]
    )


async def fetch_guokr(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    entries = await adapter.request_json(
        "https://www.guokr.com/beta/proxy/science_api/articles?limit=30",
        headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "desc": entry.get("summary"),
                "cover": entry.get("small_image"),
                "author": entry.get("author", {}).get("nickname"),
                "timestamp": entry.get("date_modified"),
                "url": "https://www.guokr.com/article/{0}".format(entry.get("id")),
                "mobileUrl": "https://m.guokr.com/article/{0}".format(entry.get("id")),
            }
            for entry in entries
        ]
    )


async def fetch_hellogithub(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    sort_by = params.get("sort", "featured")
    payload = await adapter.request_json("https://abroad.hellogithub.com/v1/?sort_by={0}&tid=&page=1".format(sort_by))
    entries = payload.get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("item_id"),
                "title": entry.get("title"),
                "desc": entry.get("summary"),
                "author": entry.get("author"),
                "timestamp": entry.get("updated_at"),
                "hot": entry.get("clicks_total"),
                "url": "https://hellogithub.com/repository/{0}".format(entry.get("item_id")),
                "mobileUrl": "https://hellogithub.com/repository/{0}".format(entry.get("item_id")),
            }
            for entry in entries
        ]
    )


async def fetch_hupu(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    topic_id = params.get("type", "1")
    payload = await adapter.request_json("https://m.hupu.com/api/v2/bbs/topicThreads?topicId={0}&page=1".format(topic_id))
    entries = payload.get("data", {}).get("topicThreads", [])
    return build_route_result(
        [
            {
                "id": entry.get("tid"),
                "title": entry.get("title"),
                "author": entry.get("username"),
                "hot": entry.get("replies"),
                "url": "https://bbs.hupu.com/{0}.html".format(entry.get("tid")),
                "mobileUrl": entry.get("url"),
            }
            for entry in entries
        ]
    )


async def fetch_huxiu(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json(
        "https://moment-api.huxiu.com/web-v3/moment/feed?platform=www",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.huxiu.com/moment/"},
    )
    entries = payload.get("data", {}).get("moment_list", {}).get("datalist", [])
    items = []
    for entry in entries:
        content = str(entry.get("content") or "").replace("<br/>", "\n").replace("<br>", "\n")
        lines = [part.strip() for part in content.split("\n") if part.strip()]
        title = (lines[0].rstrip("。") if lines else "") or None
        desc = "\n".join(lines[1:]) if len(lines) > 1 else None
        moment_id = entry.get("object_id")
        items.append(
            {
                "id": moment_id,
                "title": title,
                "desc": desc,
                "author": entry.get("user_info", {}).get("username"),
                "timestamp": entry.get("publish_time"),
                "hot": entry.get("count_info", {}).get("agree_num"),
                "url": "https://www.huxiu.com/moment/{0}.html".format(moment_id),
                "mobileUrl": "https://m.huxiu.com/moment/{0}.html".format(moment_id),
            }
        )
    return build_route_result(items)


async def fetch_ifanr(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://sso.ifanr.com/api/v5/wp/buzz/?limit=20&offset=0")
    entries = payload.get("objects", [])
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("post_title"),
                "desc": entry.get("post_content"),
                "timestamp": entry.get("created_at"),
                "hot": entry.get("like_count") or entry.get("comment_count"),
                "url": entry.get("buzz_original_url") or "https://www.ifanr.com/{0}".format(entry.get("post_id")),
                "mobileUrl": entry.get("buzz_original_url") or "https://www.ifanr.com/digest/{0}".format(entry.get("post_id")),
            }
            for entry in entries
        ]
    )


async def fetch_juejin(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    category_id = params.get("type", "1")
    headers = {
        "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
        "Referer": "https://juejin.cn/hot/articles",
        "Accept": "application/json, text/plain, */*",
    }
    payload = await adapter.request_json(
        "https://api.juejin.cn/content_api/v1/content/article_rank?category_id={0}&type=hot".format(category_id),
        headers=headers,
    )
    entries = payload.get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("content", {}).get("content_id"),
                "title": entry.get("content", {}).get("title"),
                "author": entry.get("author", {}).get("name"),
                "hot": entry.get("content_counter", {}).get("hot_rank"),
                "url": "https://juejin.cn/post/{0}".format(entry.get("content", {}).get("content_id")),
                "mobileUrl": "https://juejin.cn/post/{0}".format(entry.get("content", {}).get("content_id")),
            }
            for entry in entries
        ]
    )


async def fetch_kuaishou(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text(
        "https://www.kuaishou.com/?isHome=1",
        headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    start = html.find(APOLLO_STATE_PREFIX)
    if start == -1:
        raise ValueError("kuaishou apollo state not found")
    script_slice = html[start + len(APOLLO_STATE_PREFIX) :]
    sentinel_a = script_slice.find(";(function(")
    sentinel_b = script_slice.find("</script>")
    cut_index = min(index for index in (sentinel_a, sentinel_b) if index != -1)
    raw = script_slice[:cut_index].strip().rstrip(";")
    last_brace = raw.rfind("}")
    cleaned = raw[: last_brace + 1] if last_brace != -1 else raw
    state = json.loads(cleaned).get("defaultClient", {})
    items = (
        state.get('$ROOT_QUERY.visionHotRank({"page":"home"})', {}).get("items")
        or state.get('$ROOT_QUERY.visionHotRank({"page":"home","platform":"web"})', {}).get("items")
        or []
    )
    result = []
    for item in items:
        hot_item = state.get(item.get("id"))
        if not hot_item:
            continue
        photo_id = ((hot_item.get("photoIds") or {}).get("json") or [None])[0]
        result.append(
            {
                "id": hot_item.get("id"),
                "title": hot_item.get("name"),
                "cover": unquote(hot_item.get("poster")) if hot_item.get("poster") else None,
                "hot": parse_chinese_number(str(hot_item.get("hotValue") or "")),
                "url": "https://www.kuaishou.com/short-video/{0}".format(photo_id),
                "mobileUrl": "https://www.kuaishou.com/short-video/{0}".format(photo_id),
            }
        )
    return build_route_result(result)


async def fetch_lol(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json(
        "https://apps.game.qq.com/cmc/zmMcnTargetContentList?r0=json&page=1&num=30&target=24&source=web_pc"
    )
    entries = payload.get("data", {}).get("result", [])
    return build_route_result(
        [
            {
                "id": entry.get("iDocID"),
                "title": entry.get("sTitle"),
                "cover": "https:{0}".format(entry.get("sIMG")),
                "author": entry.get("sAuthor"),
                "timestamp": entry.get("sCreated"),
                "hot": entry.get("iTotalPlay"),
                "url": "https://lol.qq.com/news/detail.shtml?docid={0}".format(quote(str(entry.get("iDocID") or ""))),
                "mobileUrl": "https://lol.qq.com/news/detail.shtml?docid={0}".format(quote(str(entry.get("iDocID") or ""))),
            }
            for entry in entries
        ]
    )


async def fetch_miyoushe_news(
    adapter: "HotSourceAdapter",
    *,
    game_id: str,
    post_type: str,
    page_size: int,
    slug: str,
) -> RouteResult:
    payload = await adapter.request_json(
        "https://bbs-api-static.miyoushe.com/painter/wapi/getNewsList?client_type=4&gids={0}&last_id=&page_size={1}&type={2}".format(
            game_id,
            page_size,
            post_type,
        )
    )
    payload_data = expect_object(payload, field="response")
    data = expect_object(payload_data.get("data"), field="data")
    entries = expect_list(data.get("list"), field="data.list")
    items = []
    for entry in entries:
        entry_data = expect_object(entry, field="data.list[]")
        post = expect_object(entry_data.get("post"), field="data.list[].post")
        user = entry_data.get("user")
        user_data = user if isinstance(user, dict) else {}
        images = post.get("images")
        cover = post.get("cover")
        if not cover and isinstance(images, list) and images:
            cover = images[0]
        post_id = post.get("post_id")
        items.append(
            {
                "id": post_id,
                "title": post.get("subject"),
                "desc": post.get("content"),
                "cover": cover,
                "author": user_data.get("nickname"),
                "timestamp": post.get("created_at"),
                "hot": post.get("view_status"),
                "url": "https://www.miyoushe.com/{0}/article/{1}".format(slug, post_id),
                "mobileUrl": "https://m.miyoushe.com/{0}/#/article/{1}".format(slug, post_id),
            }
        )
    return build_route_result(items)


async def fetch_genshin(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    return await fetch_miyoushe_news(adapter, game_id="2", post_type=params.get("type", "1"), page_size=20, slug="ys")


async def fetch_honkai(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    return await fetch_miyoushe_news(adapter, game_id="1", post_type=params.get("type", "1"), page_size=20, slug="bh3")


async def fetch_hostloc(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "hot")
    html = await adapter.request_text(
        "https://hostloc.com/forum.php?mod=guide&view={0}".format(rank_type),
        headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    document = HTMLParser(html)
    items = []
    for row in document.css("table tr"):
        title_link = row.css_first('th a[href*="thread-"], td a[href*="thread-"]')
        if title_link is None:
            continue
        href = title_link.attributes.get("href", "")
        title = title_link.text(strip=True)
        if not href or not title:
            continue
        by_cells = row.css("td.by")
        num_cell = row.css_first("td.num")
        board_cell = by_cells[0] if by_cells else None
        lastpost_cell = by_cells[1] if len(by_cells) > 1 else None
        board_link = board_cell.css_first('a[href*="forum"]') if board_cell else None
        author_link = board_cell.css_first("cite a") if board_cell else None
        publish_node = board_cell.css_first("em") if board_cell else None
        replies_node = num_cell.css_first("a") if num_cell else None
        views_node = num_cell.css_first("em") if num_cell else None
        last_author_node = lastpost_cell.css_first("cite a") if lastpost_cell else None
        last_time_node = lastpost_cell.css_first("em") if lastpost_cell else None
        board_name = board_link.text(strip=True) if board_link else None
        author_name = author_link.text(strip=True) if author_link else None
        publish_time = publish_node.text(strip=True) if publish_node else None
        replies_text = replies_node.text(strip=True) if replies_node else None
        views_text = views_node.text(strip=True) if views_node else None
        last_author = last_author_node.text(strip=True) if last_author_node else None
        last_time = last_time_node.text(strip=True) if last_time_node else None
        summary_parts = []
        if board_name:
            summary_parts.append("版块：{0}".format(board_name))
        if author_name:
            summary_parts.append("作者：{0}".format(author_name))
        if replies_text or views_text:
            summary_parts.append(
                "回复/查看：{0}/{1}".format(replies_text or "0", views_text or "0")
            )
        if last_author or last_time:
            summary_parts.append(
                "最后回复：{0} {1}".format(last_author or "", last_time or "").strip()
            )
        matched = re.search(r"thread-(\d+)-", href)
        items.append(
            {
                "id": matched.group(1) if matched else href,
                "title": title,
                "desc": " · ".join(summary_parts),
                "author": author_name,
                "timestamp": publish_time,
                "hot": extract_first_number(replies_text, default=0) or None,
                "url": urljoin("https://hostloc.com/", href),
                "mobileUrl": urljoin("https://hostloc.com/", href),
            }
        )
    if not items:
        raise adapter.upstream_error()
    return build_route_result(items)


async def fetch_netease_news(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://m.163.com/fe/api/hot/news/flow")
    entries = payload.get("data", {}).get("list", [])
    return build_route_result(
        [
            {
                "id": entry.get("docid"),
                "title": entry.get("title"),
                "cover": entry.get("imgsrc"),
                "author": entry.get("source"),
                "timestamp": entry.get("ptime"),
                "url": "https://www.163.com/dy/article/{0}.html".format(entry.get("docid")),
                "mobileUrl": "https://m.163.com/dy/article/{0}.html".format(entry.get("docid")),
            }
            for entry in entries
        ]
    )


async def fetch_newsmth(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://wap.newsmth.net/wap/api/hot/global")
    entries = payload.get("data", {}).get("topics", [])
    return build_route_result(
        [
            {
                "id": entry.get("firstArticleId"),
                "title": entry.get("article", {}).get("subject"),
                "desc": entry.get("article", {}).get("body"),
                "author": entry.get("article", {}).get("account", {}).get("name"),
                "timestamp": entry.get("article", {}).get("postTime"),
                "url": "https://wap.newsmth.net/article/{0}?title={1}&from=home".format(
                    entry.get("article", {}).get("topicId"),
                    quote(str(entry.get("board", {}).get("title") or "")),
                ),
                "mobileUrl": "https://wap.newsmth.net/article/{0}?title={1}&from=home".format(
                    entry.get("article", {}).get("topicId"),
                    quote(str(entry.get("board", {}).get("title") or "")),
                ),
            }
            for entry in entries
        ]
    )


async def fetch_ngabbs(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json(
        "https://ngabbs.com/nuke.php?__lib=load_topic&__act=load_topic_reply_ladder2&opt=1&all=1",
        method="POST",
        headers={
            "Accept": "*/*",
            "Host": "ngabbs.com",
            "Referer": "https://ngabbs.com/",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-Hans-CN;q=1",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "X-User-Agent": "NGA_skull/7.3.1(iPhone13,2;iOS 17.2.1)",
        },
        data_body={"__output": "14"},
    )
    entries = (payload.get("result") or [[]])[0]
    return build_route_result(
        [
            {
                "id": entry.get("tid"),
                "title": entry.get("subject"),
                "author": entry.get("author"),
                "timestamp": entry.get("postdate"),
                "hot": entry.get("replies"),
                "url": "https://bbs.nga.cn{0}".format(entry.get("tpcurl")),
                "mobileUrl": "https://bbs.nga.cn{0}".format(entry.get("tpcurl")),
            }
            for entry in entries
        ]
    )


async def fetch_qq_news(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=50")
    entries = ((payload.get("idlist") or [{}])[0].get("newslist") or [])[1:]
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "desc": entry.get("abstract"),
                "cover": entry.get("miniProShareImage"),
                "author": entry.get("source"),
                "timestamp": entry.get("timestamp"),
                "hot": entry.get("hotEvent", {}).get("hotScore"),
                "url": "https://new.qq.com/rain/a/{0}".format(entry.get("id")),
                "mobileUrl": "https://view.inews.qq.com/k/{0}".format(entry.get("id")),
            }
            for entry in entries
        ]
    )


async def fetch_sina(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "all")
    payload = await adapter.request_json(
        "https://newsapp.sina.cn/api/hotlist?newsId=HB-1-snhs%2Ftop_news_list-{0}".format(rank_type)
    )
    entries = payload.get("data", {}).get("hotList", [])
    items = []
    for entry in entries:
        base = entry.get("base", {})
        info = entry.get("info", {})
        nested = base.get("base", {})
        items.append(
            {
                "id": nested.get("uniqueId"),
                "title": info.get("title"),
                "hot": parse_chinese_number(info.get("hotValue")),
                "url": nested.get("url"),
                "mobileUrl": nested.get("url"),
            }
        )
    return build_route_result(items)


async def fetch_sina_news(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "1")
    list_type = {
        "1": {"www": "news", "params": "www_www_all_suda_suda"},
        "2": {"www": "news", "params": "video_news_all_by_vv"},
        "3": {"www": "news", "params": "total_slide_suda"},
        "4": {"www": "news", "params": "news_china_suda"},
        "5": {"www": "news", "params": "news_world_suda"},
        "6": {"www": "news", "params": "news_society_suda"},
        "7": {"www": "sports", "params": "sports_suda"},
        "8": {"www": "finance", "params": "finance_0_suda"},
        "9": {"www": "ent", "params": "ent_suda"},
        "10": {"www": "tech", "params": "tech_news_suda"},
        "11": {"www": "news", "params": "news_mil_suda"},
    }
    config = list_type.get(rank_type, list_type["1"])
    today = datetime.now()
    day_key = today.strftime("%Y%m%d")
    raw = await adapter.request_text(
        "https://top.{0}.sina.com.cn/ws/GetTopDataList.php?top_type=day&top_cat={1}&top_time={2}&top_show_num=50".format(
            config["www"],
            config["params"],
            day_key,
        )
    )
    matched = SINA_NEWS_PATTERN.match(raw.strip())
    if not matched:
        raise ValueError("invalid sina news payload")
    entries = json.loads(matched.group("body")).get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "author": entry.get("media"),
                "hot": parse_chinese_number(entry.get("top_num")),
                "timestamp": "{0} {1}".format(entry.get("create_date"), entry.get("create_time")).strip(),
                "url": entry.get("url"),
                "mobileUrl": entry.get("url"),
            }
            for entry in entries
        ]
    )


async def fetch_smzdm(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "1")
    payload = await adapter.request_json("https://post.smzdm.com/rank/json_more/?unit={0}".format(rank_type))
    entries = payload.get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("article_id"),
                "title": entry.get("title"),
                "desc": entry.get("content"),
                "cover": entry.get("pic_url"),
                "author": entry.get("nickname"),
                "timestamp": entry.get("time_sort"),
                "hot": extract_first_number(str(entry.get("collection_count") or ""), default=0),
                "url": entry.get("jump_link"),
                "mobileUrl": entry.get("jump_link"),
            }
            for entry in entries
        ]
    )


async def fetch_sspai(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    tag = params.get("type", "热门文章")
    payload = await adapter.request_json(
        "https://sspai.com/api/v1/article/tag/page/get?limit=40&tag={0}".format(quote(tag))
    )
    entries = payload.get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "desc": entry.get("summary"),
                "cover": entry.get("banner"),
                "author": entry.get("author", {}).get("nickname"),
                "timestamp": entry.get("released_time"),
                "hot": entry.get("like_count"),
                "url": "https://sspai.com/post/{0}".format(entry.get("id")),
                "mobileUrl": "https://sspai.com/post/{0}".format(entry.get("id")),
            }
            for entry in entries
        ]
    )


async def fetch_starrail(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    return await fetch_miyoushe_news(adapter, game_id="6", post_type=params.get("type", "1"), page_size=20, slug="sr")


async def fetch_thepaper(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar")
    entries = payload.get("data", {}).get("hotNews", [])
    return build_route_result(
        [
            {
                "id": entry.get("contId"),
                "title": entry.get("name"),
                "cover": entry.get("pic"),
                "timestamp": entry.get("pubTimeLong"),
                "hot": entry.get("praiseTimes"),
                "url": "https://www.thepaper.cn/newsDetail_forward_{0}".format(entry.get("contId")),
                "mobileUrl": "https://m.thepaper.cn/newsDetail_forward_{0}".format(entry.get("contId")),
            }
            for entry in entries
        ]
    )


async def fetch_tieba(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://tieba.baidu.com/hottopic/browse/topicList")
    entries = payload.get("data", {}).get("bang_topic", {}).get("topic_list", [])
    return build_route_result(
        [
            {
                "id": entry.get("topic_id"),
                "title": entry.get("topic_name"),
                "desc": entry.get("topic_desc"),
                "cover": entry.get("topic_pic"),
                "timestamp": entry.get("create_time"),
                "hot": entry.get("discuss_num"),
                "url": entry.get("topic_url"),
                "mobileUrl": entry.get("topic_url"),
            }
            for entry in entries
        ]
    )


async def fetch_toutiao(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc")
    payload_data = expect_object(payload, field="response")
    entries = expect_list(payload_data.get("data"), field="data")
    items = []
    for entry in entries:
        entry_data = expect_object(entry, field="data[]")
        image = entry_data.get("Image")
        image_data = image if isinstance(image, dict) else {}
        cluster_id = entry_data.get("ClusterIdStr")
        items.append(
            {
                "id": cluster_id,
                "title": entry_data.get("Title"),
                "cover": image_data.get("url"),
                "timestamp": cluster_id,
                "hot": entry_data.get("HotValue"),
                "url": "https://www.toutiao.com/trending/{0}/".format(cluster_id),
                "mobileUrl": "https://api.toutiaoapi.com/feoffline/amos_land/new/html/main/index.html?topic_id={0}".format(cluster_id),
            }
        )
    return build_route_result(items)


async def fetch_weatheralarm(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    province = params.get("province", "")
    payload = await adapter.request_json(
        "http://www.nmc.cn/rest/findAlarm?pageNo=1&pageSize=20&signaltype=&signallevel=&province={0}".format(quote(province))
    )
    entries = payload.get("data", {}).get("page", {}).get("list", [])
    return build_route_result(
        [
            {
                "id": entry.get("alertid"),
                "title": entry.get("title"),
                "desc": "{0} {1}".format(entry.get("issuetime"), entry.get("title")).strip(),
                "cover": entry.get("pic"),
                "timestamp": entry.get("issuetime"),
                "url": "http://nmc.cn{0}".format(entry.get("url")),
                "mobileUrl": "http://nmc.cn{0}".format(entry.get("url")),
            }
            for entry in entries
        ]
    )


async def fetch_weibo(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json(
        "https://weibo.com/ajax/side/hotSearch",
        headers={"Referer": "https://weibo.com/", "User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    entries = payload.get("data", {}).get("realtime", [])
    return build_route_result(
        [
            {
                "id": entry.get("mid") or entry.get("word_scheme") or "weibo-{0}".format(index),
                "title": entry.get("word") or entry.get("word_scheme") or "热搜{0}".format(index + 1),
                "desc": entry.get("word_scheme") or "#{0}#".format(entry.get("word") or entry.get("word_scheme") or ""),
                "timestamp": entry.get("onboard_time"),
                "url": "https://s.weibo.com/weibo?q={0}".format(quote(str(entry.get("word") or entry.get("word_scheme") or ""))),
                "mobileUrl": "https://s.weibo.com/weibo?q={0}".format(quote(str(entry.get("word") or entry.get("word_scheme") or ""))),
            }
            for index, entry in enumerate(entries)
        ]
    )


async def fetch_yystv(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json("https://www.yystv.cn/home/get_home_docs_by_page")
    entries = payload.get("data", [])
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "cover": entry.get("cover"),
                "author": entry.get("author"),
                "timestamp": entry.get("createtime"),
                "url": "https://www.yystv.cn/p/{0}".format(entry.get("id")),
                "mobileUrl": "https://www.yystv.cn/p/{0}".format(entry.get("id")),
            }
            for entry in entries
        ]
    )


async def fetch_zhihu_daily(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    payload = await adapter.request_json(
        "https://daily.zhihu.com/api/4/news/latest",
        headers={"Referer": "https://daily.zhihu.com/api/4/news/latest", "Host": "daily.zhihu.com"},
    )
    entries = [entry for entry in payload.get("stories", []) if entry.get("type") == 0]
    return build_route_result(
        [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "cover": (entry.get("images") or [None])[0],
                "author": entry.get("hint"),
                "url": entry.get("url"),
                "mobileUrl": entry.get("url"),
            }
            for entry in entries
        ]
    )


async def fetch_github(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "daily")
    url = "https://github.com/trending?since={0}".format(rank_type)
    headers = {
        "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    last_error: Optional[Exception] = None
    for _ in range(3):
        try:
            html = await adapter.request_text(url, headers=headers)
            document = HTMLParser(html)
            items = []
            for index, node in enumerate(document.css("article.Box-row")):
                anchor = node.css_first("h2 a")
                if anchor is None:
                    continue
                parts = [part.strip() for part in re.sub(r"\s+", " ", anchor.text(strip=True)).split("/") if part.strip()]
                owner = parts[0] if parts else ""
                repo = parts[1] if len(parts) > 1 else ""
                href = anchor.attributes.get("href", "")
                items.append(
                    {
                        "id": index,
                        "title": repo,
                        "desc": (node.css_first("p.col-9.color-fg-muted") or node.css_first("p")).text(strip=True)
                        if (node.css_first("p.col-9.color-fg-muted") or node.css_first("p"))
                        else None,
                        "hot": (node.css_first('a[href$="/stargazers"]').text(strip=True) if node.css_first('a[href$="/stargazers"]') else None),
                        "url": "https://github.com{0}".format(href),
                        "mobileUrl": "https://github.com{0}".format(href),
                        "summary": None,
                        "author": owner,
                    }
                )
            return build_route_result(items)
        except Exception as exc:
            last_error = exc
    raise last_error or ValueError("github trending fetch failed")


async def fetch_history(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    month = str(params.get("month") or datetime.now().month).zfill(2)
    day = str(params.get("day") or datetime.now().day).zfill(2)
    payload = await adapter.request_json(
        "https://baike.baidu.com/cms/home/eventsOnHistory/{0}.json".format(month),
        params={"_": round(datetime.now().timestamp() * 1000)},
    )
    entries = payload.get(month, {}).get(month + day, [])
    return build_route_result(
        [
            {
                "id": index,
                "title": html_to_text(entry.get("title")),
                "cover": entry.get("pic_share") if entry.get("cover") else None,
                "desc": html_to_text(entry.get("desc")),
                "url": entry.get("link"),
                "mobileUrl": entry.get("link"),
            }
            for index, entry in enumerate(entries)
        ]
    )


async def fetch_ithome(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text("https://m.ithome.com/rankm/")
    document = HTMLParser(html)
    items = []
    for node in document.css(".rank-box .placeholder"):
        link_node = node.css_first("a")
        title_node = node.css_first(".plc-title")
        if link_node is None or title_node is None:
            continue
        href = link_node.attributes.get("href", "")
        image_node = node.css_first("img")
        items.append(
            {
                "id": extract_first_number(href, default=100000),
                "title": title_node.text(strip=True),
                "cover": (image_node.attributes.get("data-original") if image_node else None) or (image_node.attributes.get("src") if image_node else None),
                "timestamp": node.css_first("span.post-time").text(strip=True) if node.css_first("span.post-time") else None,
                "hot": extract_first_number(node.css_first(".review-num").text(strip=True) if node.css_first(".review-num") else None),
                "url": build_ithome_public_url(href),
                "mobileUrl": build_ithome_public_url(href),
            }
        )
    return build_route_result(items)


async def fetch_ithome_xijiayi(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text("https://www.ithome.com/zt/xijiayi")
    document = HTMLParser(html)
    items = []
    for node in document.css(".newslist li"):
        link_node = node.css_first("a")
        href = link_node.attributes.get("href", "") if link_node else ""
        time_text = node.css_first("span.time").text(strip=True) if node.css_first("span.time") else ""
        matched = re.search(r"'([^']+)'", time_text)
        image_node = node.css_first("img")
        items.append(
            {
                "id": extract_first_number(href, default=100000),
                "title": node.css_first(".newsbody h2").text(strip=True) if node.css_first(".newsbody h2") else None,
                "desc": node.css_first(".newsbody p").text(strip=True) if node.css_first(".newsbody p") else None,
                "cover": image_node.attributes.get("data-original") if image_node else None,
                "timestamp": matched.group(1) if matched else None,
                "hot": extract_first_number(node.css_first(".comment").text(strip=True) if node.css_first(".comment") else None),
                "url": href,
                "mobileUrl": build_ithome_xijiayi_mobile_url(href),
            }
        )
    return build_route_result(items)


async def fetch_jianshu(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text("https://www.jianshu.com/", headers={"Referer": "https://www.jianshu.com"})
    document = HTMLParser(html)
    items = []
    for node in document.css("ul.note-list li"):
        link_node = node.css_first("a")
        href = link_node.attributes.get("href", "") if link_node else ""
        image_node = node.css_first("img")
        items.append(
            {
                "id": href.rstrip("/").split("/")[-1] or "undefined",
                "title": node.css_first("a.title").text(strip=True) if node.css_first("a.title") else None,
                "cover": image_node.attributes.get("src") if image_node else None,
                "desc": node.css_first("p.abstract").text(strip=True) if node.css_first("p.abstract") else None,
                "author": node.css_first("a.nickname").text(strip=True) if node.css_first("a.nickname") else None,
                "url": "https://www.jianshu.com{0}".format(href),
                "mobileUrl": "https://www.jianshu.com{0}".format(href),
            }
        )
    return build_route_result(items)


async def fetch_douban_group(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text("https://www.douban.com/group/explore")
    document = HTMLParser(html)
    items = []
    for node in document.css(".article .channel-item"):
        link_node = node.css_first("h3 a")
        href = link_node.attributes.get("href", "") if link_node else ""
        topic_id = extract_first_number(href, default=100000000)
        image_node = node.css_first(".pic-wrap img")
        items.append(
            {
                "id": topic_id,
                "title": link_node.text(strip=True) if link_node else None,
                "cover": image_node.attributes.get("src") if image_node else None,
                "desc": node.css_first(".block p").text(strip=True) if node.css_first(".block p") else None,
                "timestamp": node.css_first("span.pubtime").text(strip=True) if node.css_first("span.pubtime") else None,
                "hot": 0,
                "url": href or "https://www.douban.com/group/topic/{0}".format(topic_id),
                "mobileUrl": "https://m.douban.com/group/topic/{0}/".format(topic_id),
            }
        )
    return build_route_result(items)


async def fetch_douban_movie(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text(
        "https://movie.douban.com/chart/",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
            )
        },
    )
    document = HTMLParser(html)
    items = []
    for node in document.css(".article tr.item"):
        anchor = node.css_first("a")
        href = anchor.attributes.get("href", "") if anchor else ""
        item_id = extract_first_number(href, default=0)
        score = node.css_first(".rating_nums").text(strip=True) if node.css_first(".rating_nums") else "0.0"
        image_node = node.css_first("img")
        items.append(
            {
                "id": item_id,
                "title": "【{0}】{1}".format(score, anchor.attributes.get("title", "") if anchor else ""),
                "cover": image_node.attributes.get("src") if image_node else None,
                "desc": node.css_first("p.pl").text(strip=True) if node.css_first("p.pl") else None,
                "hot": extract_first_number(node.css_first("span.pl").text(strip=True) if node.css_first("span.pl") else None),
                "url": href or "https://movie.douban.com/subject/{0}/".format(item_id),
                "mobileUrl": "https://m.douban.com/movie/subject/{0}/".format(item_id),
            }
        )
    return build_route_result(items)


async def fetch_hackernews(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    html = await adapter.request_text("https://news.ycombinator.com", headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT})
    document = HTMLParser(html)
    items = []
    for node in document.css(".athing"):
        story_id = node.attributes.get("id", "")
        title_node = node.css_first(".titleline a")
        href = title_node.attributes.get("href", "") if title_node else ""
        score_node = document.css_first("#{0}".format("score_" + story_id))
        items.append(
            {
                "id": story_id,
                "title": title_node.text(strip=True) if title_node else None,
                "hot": extract_first_number(score_node.text(strip=True) if score_node else None, default=0) or None,
                "url": href or "https://news.ycombinator.com/item?id={0}".format(story_id),
                "mobileUrl": href or "https://news.ycombinator.com/item?id={0}".format(story_id),
            }
        )
    return build_route_result(items)


async def fetch_producthunt(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    items = await fetch_rss_route(
        adapter,
        "https://www.producthunt.com/feed",
        headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    return build_route_result(
        [
            {
                "id": item.get("guid") or index,
                "title": item.get("title"),
                "desc": html_to_text(item.get("contentSnippet") or item.get("content")),
                "author": item.get("author"),
                "timestamp": item.get("pubDate"),
                "url": item.get("link"),
                "mobileUrl": item.get("link"),
            }
            for index, item in enumerate(items)
        ]
    )


async def fetch_bilibili(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "0")
    wbi_query = await fetch_bilibili_wbi_query(adapter)
    payload = await adapter.request_json(
        "https://api.bilibili.com/x/web-interface/ranking/v2?rid={0}&type=all&{1}".format(rank_type, wbi_query),
        headers={
            "Referer": "https://www.bilibili.com/ranking/all",
            "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
        },
    )
    entries = payload.get("data", {}).get("list", [])
    if entries:
        return build_route_result(
            [
                {
                    "id": entry.get("bvid"),
                    "title": entry.get("title"),
                    "desc": entry.get("desc") or "该视频暂无简介",
                    "cover": str(entry.get("pic") or "").replace("http:", "https:"),
                    "author": entry.get("owner", {}).get("name"),
                    "timestamp": entry.get("pubdate"),
                    "hot": entry.get("stat", {}).get("view"),
                    "url": entry.get("short_link_v2") or "https://www.bilibili.com/video/{0}".format(entry.get("bvid")),
                    "mobileUrl": "https://m.bilibili.com/video/{0}".format(entry.get("bvid")),
                }
                for entry in entries
            ]
        )
    fallback = await adapter.request_json(
        "https://api.bilibili.com/x/web-interface/ranking?jsonp=jsonp?rid={0}&type=all&callback=__jp0".format(rank_type),
        headers={"Referer": "https://www.bilibili.com/ranking/all", "User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    entries = fallback.get("data", {}).get("list", [])
    return build_route_result(
        [
            {
                "id": entry.get("bvid"),
                "title": entry.get("title"),
                "desc": entry.get("desc") or "该视频暂无简介",
                "cover": str(entry.get("pic") or "").replace("http:", "https:"),
                "author": entry.get("author"),
                "hot": entry.get("video_review"),
                "url": "https://www.bilibili.com/video/{0}".format(entry.get("bvid")),
                "mobileUrl": "https://m.bilibili.com/video/{0}".format(entry.get("bvid")),
            }
            for entry in entries
        ]
    )


async def fetch_douyin(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    cookie = await fetch_douyin_cookie(adapter)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.douyin.com/",
        "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
    }
    if cookie:
        headers["Cookie"] = "passport_csrf_token={0}".format(cookie)
    payload = await adapter.request_json(
        "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1",
        headers=headers,
    )
    payload_data = expect_object(payload, field="response")
    data = expect_object(payload_data.get("data"), field="data")
    entries = expect_list(data.get("word_list"), field="data.word_list")
    items = []
    for entry in entries:
        entry_data = expect_object(entry, field="data.word_list[]")
        sentence_id = entry_data.get("sentence_id")
        items.append(
            {
                "id": sentence_id,
                "title": entry_data.get("word"),
                "timestamp": entry_data.get("event_time"),
                "hot": entry_data.get("hot_value"),
                "url": "https://www.douyin.com/hot/{0}".format(sentence_id),
                "mobileUrl": "https://www.douyin.com/hot/{0}".format(sentence_id),
            }
        )
    return build_route_result(items)


async def fetch_weread(adapter: "HotSourceAdapter", params: Mapping[str, str]) -> RouteResult:
    rank_type = params.get("type", "rising")
    payload = await adapter.request_json(
        "https://weread.qq.com/web/bookListInCategory/{0}?rank=1".format(rank_type),
        headers={"User-Agent": DEFAULT_DESKTOP_USER_AGENT},
    )
    entries = payload.get("books", [])
    items = []
    for entry in entries:
        book = entry.get("bookInfo", {})
        detail_id = build_weread_detail_id(str(book.get("bookId") or "")) or ""
        items.append(
            {
                "id": book.get("bookId"),
                "title": book.get("title"),
                "author": book.get("author"),
                "desc": book.get("intro"),
                "cover": str(book.get("cover") or "").replace("s_", "t9_"),
                "timestamp": book.get("publishTime"),
                "hot": entry.get("readingCount"),
                "url": "https://weread.qq.com/web/bookDetail/{0}".format(detail_id),
                "mobileUrl": "https://weread.qq.com/web/bookDetail/{0}".format(detail_id),
            }
        )
    return build_route_result(items)


async def fetch_zhihu(adapter: "HotSourceAdapter", _: Mapping[str, str]) -> RouteResult:
    headers: Dict[str, str] = {}
    if adapter.settings.hot_zhihu_cookie:
        headers["Cookie"] = adapter.settings.hot_zhihu_cookie
    payload = await adapter.request_json(
        "https://api.zhihu.com/topstory/hot-lists/total?limit=50",
        headers=headers or None,
    )
    entries = payload.get("data", [])
    items = []
    for entry in entries:
        target = entry.get("target", {})
        question_id = str(target.get("url") or "").rstrip("/").split("/")[-1]
        detail_text = str(entry.get("detail_text") or "0")
        try:
            hot_value = int(float(detail_text.split(" ")[0]) * 10000)
        except (IndexError, ValueError):
            hot_value = None
        items.append(
            {
                "id": target.get("id"),
                "title": target.get("title"),
                "desc": target.get("excerpt"),
                "cover": ((entry.get("children") or [{}])[0]).get("thumbnail"),
                "timestamp": target.get("created"),
                "hot": hot_value,
                "url": "https://www.zhihu.com/question/{0}".format(question_id),
                "mobileUrl": "https://www.zhihu.com/question/{0}".format(question_id),
            }
        )
    return build_route_result(items)


def build_route_fetchers() -> Dict[str, RouteFetcher]:
    return {
        "36kr": fetch_36kr,
        "51cto": fetch_51cto,
        "52pojie": fetch_52pojie,
        "acfun": fetch_acfun,
        "baidu": fetch_baidu,
        "bilibili": fetch_bilibili,
        "csdn": fetch_csdn,
        "dgtle": fetch_dgtle,
        "douban-group": fetch_douban_group,
        "douban-movie": fetch_douban_movie,
        "douyin": fetch_douyin,
        "geekpark": fetch_geekpark,
        "genshin": fetch_genshin,
        "github": fetch_github,
        "guokr": fetch_guokr,
        "hackernews": fetch_hackernews,
        "hellogithub": fetch_hellogithub,
        "history": fetch_history,
        "honkai": fetch_honkai,
        "hostloc": fetch_hostloc,
        "hupu": fetch_hupu,
        "huxiu": fetch_huxiu,
        "ifanr": fetch_ifanr,
        "ithome": fetch_ithome,
        "ithome-xijiayi": fetch_ithome_xijiayi,
        "jianshu": fetch_jianshu,
        "juejin": fetch_juejin,
        "kuaishou": fetch_kuaishou,
        "lol": fetch_lol,
        "netease-news": fetch_netease_news,
        "newsmth": fetch_newsmth,
        "ngabbs": fetch_ngabbs,
        "producthunt": fetch_producthunt,
        "qq-news": fetch_qq_news,
        "sina": fetch_sina,
        "sina-news": fetch_sina_news,
        "smzdm": fetch_smzdm,
        "sspai": fetch_sspai,
        "starrail": fetch_starrail,
        "thepaper": fetch_thepaper,
        "tieba": fetch_tieba,
        "toutiao": fetch_toutiao,
        "weatheralarm": fetch_weatheralarm,
        "weibo": fetch_weibo,
        "weread": fetch_weread,
        "yystv": fetch_yystv,
        "zhihu": fetch_zhihu,
        "zhihu-daily": fetch_zhihu_daily,
    }
