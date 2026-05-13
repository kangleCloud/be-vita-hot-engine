"""Source catalog for DailyHot-compatible presets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


DEFAULT_VISIBLE_SOURCE_CODES = {
    # 默认展示的是对前端更通用的榜单别名，避免把所有参数变体都直接暴露为默认入口。
    "bilibili",
    "weibo",
    "douyin",
    "zhihu",
    "36kr",
    "baidu",
    "sspai",
    "ithome",
    "thepaper",
    "toutiao",
    "tieba",
    "juejin",
    "qq-news",
    "douban-movie",
    "genshin",
    "starrail",
    "lol",
    "netease-news",
    "weread",
    "douban-group",
    "ngabbs",
    "hellogithub",
    "jianshu",
    "zhihu-daily",
}


@dataclass(frozen=True)
class SourcePreset:
    """Materialized source definition exposed by the service."""

    source_code: str
    route_code: str
    icon_key: str
    source_name: str
    source_type: str
    description: str = ""
    enabled: bool = True
    default_visible: bool = False
    params: Dict[str, str] = field(default_factory=dict)


def build_source_catalog() -> List[SourcePreset]:
    """Return the full fixed source catalog."""

    # catalog 是对外 sourceCode 的唯一来源，所有 route 变体都需要在这里物化成稳定编码。
    catalog: List[SourcePreset] = []

    add_param_variants(
        catalog,
        route_code="36kr",
        source_name="36氪",
        default_key="hot",
        param_name="type",
        choices={
            "hot": "人气榜",
            "video": "视频榜",
            "comment": "热议榜",
            "collect": "收藏榜",
        },
    )
    add_static_source(catalog, "51cto", "51CTO", "推荐榜")
    add_param_variants(
        catalog,
        route_code="52pojie",
        source_name="吾爱破解",
        default_key="digest",
        param_name="type",
        choices={
            "digest": "最新精华",
            "hot": "最新热门",
            "new": "最新回复",
            "newthread": "最新发表",
        },
    )
    add_combo_variants(
        catalog,
        route_code="acfun",
        source_name="AcFun",
        defaults={"type": "-1", "range": "DAY"},
        params_map={
            "type": {
                "-1": "综合",
                "155": "番剧",
                "1": "动画",
                "60": "娱乐",
                "201": "生活",
                "58": "音乐",
                "123": "舞蹈·偶像",
                "59": "游戏",
                "70": "科技",
                "68": "影视",
                "69": "体育",
                "125": "鱼塘",
            },
            "range": {
                "DAY": "今日",
                "THREE_DAYS": "三日",
                "WEEK": "本周",
            },
        },
        source_type_builder=lambda labels: "排行榜 · {0} · {1}".format(labels["type"], labels["range"]),
        description="AcFun是一家弹幕视频网站，致力于为每一个人带来欢乐。",
    )
    add_param_variants(
        catalog,
        route_code="baidu",
        source_name="百度",
        default_key="realtime",
        param_name="type",
        choices={
            "realtime": "热搜",
            "novel": "小说",
            "movie": "电影",
            "teleplay": "电视剧",
            "car": "汽车",
            "game": "游戏",
        },
    )
    add_param_variants(
        catalog,
        route_code="bilibili",
        source_name="哔哩哔哩",
        default_key="0",
        param_name="type",
        choices={
            "0": "全站",
            "1": "动画",
            "3": "音乐",
            "4": "游戏",
            "5": "娱乐",
            "188": "科技",
            "119": "鬼畜",
            "129": "舞蹈",
            "155": "时尚",
            "160": "生活",
            "168": "国创相关",
            "181": "影视",
        },
        source_type_builder=lambda label: "热榜 · {0}".format(label),
        description="你所热爱的，就是你的生活",
    )
    add_static_source(catalog, "csdn", "CSDN", "排行榜", description="专业开发者社区")
    add_static_source(
        catalog,
        "dgtle",
        "数字尾巴",
        "热门文章",
        description="致力于分享美好数字生活体验，囊括你闻所未闻的最丰富数码资讯。",
    )
    add_static_source(catalog, "douban-group", "豆瓣讨论", "讨论精选")
    add_static_source(catalog, "douban-movie", "豆瓣电影", "新片榜")
    add_static_source(catalog, "douyin", "抖音", "热榜", description="实时上升热点")
    add_static_source(catalog, "geekpark", "极客公园", "热门文章", description="极客公园聚焦互联网领域。")
    add_param_variants(
        catalog,
        route_code="genshin",
        source_name="原神",
        default_key="1",
        param_name="type",
        choices={"1": "公告", "2": "活动", "3": "资讯"},
        source_type_builder=lambda label: "最新动态 · {0}".format(label),
    )
    add_param_variants(
        catalog,
        route_code="github",
        source_name="GitHub 趋势",
        default_key="daily",
        param_name="type",
        choices={"daily": "日榜", "weekly": "周榜", "monthly": "月榜"},
    )
    add_static_source(catalog, "guokr", "果壳", "热门文章", description="科技有意思")
    add_static_source(
        catalog,
        "hackernews",
        "Hacker News",
        "Popular",
        description="News about hacking and startups",
    )
    add_param_variants(
        catalog,
        route_code="hellogithub",
        source_name="HelloGitHub",
        default_key="featured",
        param_name="sort",
        choices={"featured": "精选", "all": "全部"},
        source_type_builder=lambda label: "热门仓库 · {0}".format(label),
        description="分享 GitHub 上有趣、入门级的开源项目",
    )
    add_static_source(catalog, "history", "历史上的今天", "今日", params={"month": "__today__", "day": "__today__"})
    add_param_variants(
        catalog,
        route_code="honkai",
        source_name="崩坏3",
        default_key="1",
        param_name="type",
        choices={"1": "公告", "2": "活动", "3": "资讯"},
        source_type_builder=lambda label: "最新动态 · {0}".format(label),
    )
    add_param_variants(
        catalog,
        route_code="hostloc",
        source_name="全球主机交流",
        default_key="hot",
        param_name="type",
        choices={
            "hot": "最新热门",
            "digest": "最新精华",
            "new": "最新回复",
            "newthread": "最新发表",
        },
    )
    add_param_variants(
        catalog,
        route_code="hupu",
        source_name="虎扑",
        default_key="1",
        param_name="type",
        choices={
            "1": "主干道",
            "6": "恋爱区",
            "11": "校园区",
            "12": "历史区",
            "612": "摄影区",
        },
        source_type_builder=lambda label: "步行街热帖 · {0}".format(label),
    )
    add_static_source(catalog, "huxiu", "虎嗅", "24小时")
    add_static_source(catalog, "ifanr", "爱范儿", "快讯", description="15秒了解全球新鲜事")
    add_static_source(catalog, "ithome", "IT之家", "热榜", description="爱科技，爱这里 - 前沿科技新闻网站")
    add_static_source(catalog, "ithome-xijiayi", "IT之家「喜加一」", "最新动态", description="最新最全的「喜加一」游戏动态尽在这里！")
    add_static_source(catalog, "jianshu", "简书", "热门推荐", description="一个优质的创作社区")
    add_static_source(catalog, "juejin", "稀土掘金", "文章榜")
    add_static_source(catalog, "kuaishou", "快手", "热榜", description="快手，拥抱每一种生活")
    add_static_source(catalog, "lol", "英雄联盟", "更新公告")
    add_static_source(catalog, "netease-news", "网易新闻", "热点榜")
    add_static_source(catalog, "newsmth", "水木社区", "热门话题", description="水木社区是一个源于清华的高知社群。")
    add_static_source(catalog, "ngabbs", "NGA", "论坛热帖", description="精英玩家俱乐部")
    add_static_source(
        catalog,
        "producthunt",
        "Product Hunt",
        "Today",
        description="The best new products, every day",
    )
    add_static_source(catalog, "qq-news", "腾讯新闻", "热点榜")
    add_param_variants(
        catalog,
        route_code="sina",
        source_name="新浪网",
        default_key="all",
        param_name="type",
        choices={
            "all": "新浪热榜",
            "hotcmnt": "热议榜",
            "minivideo": "视频热榜",
            "ent": "娱乐热榜",
            "ai": "AI热榜",
            "auto": "汽车热榜",
            "mother": "育儿热榜",
            "fashion": "时尚热榜",
            "travel": "旅游热榜",
            "esg": "ESG热榜",
        },
        description="热榜太多，一个就够",
    )
    add_param_variants(
        catalog,
        route_code="sina-news",
        source_name="新浪新闻",
        default_key="1",
        param_name="type",
        choices={
            "1": "总排行",
            "2": "视频排行",
            "3": "图片排行",
            "4": "国内新闻",
            "5": "国际新闻",
            "6": "社会新闻",
            "7": "体育新闻",
            "8": "财经新闻",
            "9": "娱乐新闻",
            "10": "科技新闻",
            "11": "军事新闻",
        },
    )
    add_param_variants(
        catalog,
        route_code="smzdm",
        source_name="什么值得买",
        default_key="1",
        param_name="type",
        choices={"1": "今日热门", "7": "周热门", "30": "月热门"},
        description="中立的、致力于帮助网友买到更有性价比网购产品的推荐网站。",
    )
    add_param_variants(
        catalog,
        route_code="sspai",
        source_name="少数派",
        default_key="hot_articles",
        param_name="type",
        choices={
            "hot_articles": "热门文章",
            "app_recommend": "应用推荐",
            "lifestyle": "生活方式",
            "productivity": "效率技巧",
            "podcast": "少数派播客",
        },
        param_values={
            "hot_articles": "热门文章",
            "app_recommend": "应用推荐",
            "lifestyle": "生活方式",
            "productivity": "效率技巧",
            "podcast": "少数派播客",
        },
    )
    add_param_variants(
        catalog,
        route_code="starrail",
        source_name="崩坏：星穹铁道",
        default_key="1",
        param_name="type",
        choices={"1": "公告", "2": "活动", "3": "资讯"},
        source_type_builder=lambda label: "最新动态 · {0}".format(label),
    )
    add_static_source(catalog, "thepaper", "澎湃新闻", "热榜")
    add_static_source(catalog, "tieba", "百度贴吧", "热议榜", description="全球领先的中文社区")
    add_static_source(catalog, "toutiao", "今日头条", "热榜")
    add_static_source(catalog, "weatheralarm", "中央气象台", "全国气象预警", params={"province": ""})
    add_static_source(catalog, "weibo", "微博", "热搜榜", description="实时热点，每分钟更新一次")
    add_param_variants(
        catalog,
        route_code="weread",
        source_name="微信读书",
        default_key="rising",
        param_name="type",
        choices={
            "rising": "飙升榜",
            "hot_search": "热搜榜",
            "newbook": "新书榜",
            "general_novel_rising": "小说榜",
            "all": "总榜",
        },
    )
    add_static_source(
        catalog,
        "yystv",
        "游研社",
        "全部文章",
        description="游研社是以游戏内容为主的新媒体。",
    )
    add_static_source(catalog, "zhihu", "知乎", "热榜")
    add_static_source(catalog, "zhihu-daily", "知乎日报", "推荐榜", description="每天三次，每次七分钟")

    return catalog


def add_static_source(
    catalog: List[SourcePreset],
    route_code: str,
    source_name: str,
    source_type: str,
    *,
    description: str = "",
    icon_key: Optional[str] = None,
    params: Optional[Dict[str, str]] = None,
) -> None:
    catalog.append(
        SourcePreset(
            source_code=route_code,
            route_code=route_code,
            icon_key=icon_key or route_code,
            source_name=source_name,
            source_type=source_type,
            description=description,
            default_visible=route_code in DEFAULT_VISIBLE_SOURCE_CODES,
            params=params or {},
        )
    )


def add_param_variants(
    catalog: List[SourcePreset],
    *,
    route_code: str,
    source_name: str,
    default_key: str,
    param_name: str,
    choices: Dict[str, str],
    description: str = "",
    icon_key: Optional[str] = None,
    source_type_builder=None,
    param_values: Optional[Dict[str, str]] = None,
) -> None:
    for raw_key, label in choices.items():
        # 默认参数直接复用 route_code 作为兼容别名，其余变体统一拼成 route__variant。
        source_code = route_code if raw_key == default_key else "{0}__{1}".format(route_code, sanitize_code(raw_key))
        source_type = source_type_builder(label) if source_type_builder else label
        catalog.append(
            SourcePreset(
                source_code=source_code,
                route_code=route_code,
                icon_key=icon_key or route_code,
                source_name=source_name,
                source_type=source_type,
                description=description,
                default_visible=(raw_key == default_key and route_code in DEFAULT_VISIBLE_SOURCE_CODES),
                params={param_name: (param_values or {}).get(raw_key, raw_key)},
            )
        )


def add_combo_variants(
    catalog: List[SourcePreset],
    *,
    route_code: str,
    source_name: str,
    defaults: Dict[str, str],
    params_map: Dict[str, Dict[str, str]],
    source_type_builder,
    description: str = "",
    icon_key: Optional[str] = None,
    source_name_builder=None,
) -> None:
    ordered_keys: Sequence[str] = tuple(params_map.keys())
    # 组合参数会展开为笛卡尔积，这样每个可访问榜单都有固定 sourceCode。
    combinations: List[Dict[str, str]] = [{}]
    for key in ordered_keys:
        next_combinations: List[Dict[str, str]] = []
        for combo in combinations:
            for option_key in params_map[key]:
                new_combo = dict(combo)
                new_combo[key] = option_key
                next_combinations.append(new_combo)
        combinations = next_combinations

    for combo in combinations:
        suffix_parts = [sanitize_code(combo[key]) for key in ordered_keys]
        is_default = all(combo[key] == defaults[key] for key in ordered_keys)
        source_code = route_code if is_default else "{0}__{1}".format(route_code, "__".join(suffix_parts))
        labels = {key: params_map[key][combo[key]] for key in ordered_keys}
        catalog.append(
            SourcePreset(
                source_code=source_code,
                route_code=route_code,
                icon_key=icon_key or route_code,
                source_name=source_name_builder(labels) if source_name_builder else source_name,
                source_type=source_type_builder(labels),
                description=description,
                default_visible=(is_default and route_code in DEFAULT_VISIBLE_SOURCE_CODES),
                params={key: combo[key] for key in ordered_keys},
            )
        )


def sanitize_code(value: str) -> str:
    """Convert variant values to stable ASCII-ish suffixes."""

    # sourceCode 后缀需要稳定、可预测，避免空格、符号或大小写差异影响接口契约。
    stripped = value.strip()
    negative = stripped.startswith("-")
    normalized = stripped.lower()
    result_chars: List[str] = []
    for char in normalized:
        if char.isalnum():
            result_chars.append(char)
        else:
            if not result_chars or result_chars[-1] == "_":
                continue
            result_chars.append("_")
    result = "".join(result_chars).strip("_")
    if negative:
        result = "neg_{0}".format(result)
    return result or "variant"
