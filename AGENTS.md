# be-vita-hot-engine 协作说明

## 项目定位
- `be-vita-hot-engine` 是面向 `be-vita` 内部调用的 Python 热榜聚合服务。
- 服务对外暴露统一的 HTTP 只读接口，底层通过 `DailyHotApi` 兼容上游拉取热榜数据。
- 当前主实现以 `catalog + mirror` 为核心，不再维护零散单源直连适配器。

## 目录结构
- `app/api/`：HTTP 路由层。
- `app/services/`：业务编排层，负责源列表查询和单源快照分发。
- `app/sources/catalog.py`：物化全部固定 `sourceCode` 定义。
- `app/sources/mirror.py`：统一的上游镜像适配器。
- `app/sources/registry.py`：根据 catalog 注册全部适配器。
- `app/core/`：配置、鉴权、错误定义。
- `tests/`：接口、目录、适配器测试。

## 启动与测试
- 初始化环境：
  - `cd /Users/zhuningkang/Documents/git/github/vita/be-vita-hot-engine`
  - `/opt/homebrew/opt/python@3.10/bin/python3.10 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r requirements.txt`
- 开发启动：
  - `source .venv/bin/activate`
  - `set -a && source .env.develop && set +a`
  - `uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" --reload`
- 运行测试：
  - `./.venv/bin/pytest -q`

## 关键配置
- `HOT_API_TOKEN`：内部 Bearer Token。
- `HOT_HTTP_TIMEOUT`：上游 HTTP 超时秒数。
- `HOT_DAILYHOT_BASE_URL`：DailyHot 兼容上游地址。
- `HOT_ZHIHU_COOKIE`：预留的知乎直连配置，目前镜像模式不消费。
- `HOT_FILTER_WEIBO_ADVERTISEMENT`：微博广告过滤开关。

## 核心设计
- `build_source_catalog()` 负责把 route、变体参数、默认别名物化成固定 `sourceCode`。
- `build_source_registry()` 负责为每个 `SourcePreset` 注册一个 `DailyHotMirrorSource`。
- `HotService.list_sources()` 只返回目录元数据，不触发上游抓取。
- `HotService.get_source_snapshot()` 按 `sourceCode` 定位适配器并返回归一化快照。

## 代码约束
- 新增榜单时，优先在 `app/sources/catalog.py` 中扩展，不要恢复零散单源适配器。
- 需要兼容新上游字段时，优先修改 `DailyHotMirrorSource.normalize_items()` 的统一映射逻辑。
- 保持对外接口契约稳定，不随内部重构改变 `/api/v1/hot/*` 返回字段。
- 中文注释只写在复杂业务流程、兼容逻辑和边界处理处，不写逐行解释型注释。
