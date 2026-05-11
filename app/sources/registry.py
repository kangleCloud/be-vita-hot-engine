"""Source adapter registry."""

from __future__ import annotations

from typing import Dict

from app.core.config import Settings
from app.sources.baidu import BaiduHotSource
from app.sources.base import HotSourceAdapter
from app.sources.bilibili import BilibiliHotSource
from app.sources.hot36kr import Kr36HotSource
from app.sources.ithome import ITHomeHotSource
from app.sources.juejin import JuejinHotSource
from app.sources.sspai import SSPaiHotSource
from app.sources.weibo import WeiboHotSource
from app.sources.zhihu import ZhihuHotSource

SOURCE_ADAPTERS = (
    WeiboHotSource,
    ZhihuHotSource,
    BaiduHotSource,
    BilibiliHotSource,
    JuejinHotSource,
    ITHomeHotSource,
    Kr36HotSource,
    SSPaiHotSource,
)


def build_source_registry(settings: Settings) -> Dict[str, HotSourceAdapter]:
    """Instantiate the fixed v1 source adapters."""

    registry: Dict[str, HotSourceAdapter] = {}
    for adapter_class in SOURCE_ADAPTERS:
        adapter = adapter_class(settings)
        registry[adapter.source_code] = adapter
    return registry
