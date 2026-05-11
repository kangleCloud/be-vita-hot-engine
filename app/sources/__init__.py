"""Hot source adapters."""

from app.sources.baidu import BaiduHotSource
from app.sources.bilibili import BilibiliHotSource
from app.sources.hot36kr import Kr36HotSource
from app.sources.ithome import ITHomeHotSource
from app.sources.juejin import JuejinHotSource
from app.sources.sspai import SSPaiHotSource
from app.sources.weibo import WeiboHotSource
from app.sources.zhihu import ZhihuHotSource

__all__ = [
    "BaiduHotSource",
    "BilibiliHotSource",
    "Kr36HotSource",
    "ITHomeHotSource",
    "JuejinHotSource",
    "SSPaiHotSource",
    "WeiboHotSource",
    "ZhihuHotSource",
]
