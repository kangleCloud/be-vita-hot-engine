# be-vita-hot-engine

`be-vita-hot-engine` 是独立的 Python 热榜聚合服务，面向 `be-vita` 内部调用，负责以 Python 原生抓取方式将 `DailyHotApi` 的热榜能力同步为统一的内部 HTTP 契约。

## 当前能力

- 服务框架：FastAPI
- Python 基线：`3.10`
- 认证方式：`Authorization: Bearer <HOT_API_TOKEN>`
- 上游能力：内建实现 `DailyHotApi` 当前 `56` 个 route，并物化为 `180` 个固定 `sourceCode`
- 兼容性：保留默认榜单别名，例如 `bilibili`、`36kr`、`weibo` 继续可用；非默认预设使用 `route__variant` 形式，例如 `github__weekly`
- 当前实现不包含 Redis、定时任务、管理后台和数据库

## 项目结构

```text
be-vita-hot-engine/
├── app/
│   ├── api/v1/hot.py
│   ├── core/
│   ├── schemas/
│   ├── services/
│   └── sources/
├── deploy/
│   ├── Dockerfile
│   └── docker-compose.yaml
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## 本地环境

按你指定的解释器与虚拟环境使用方式：

```bash
cd /Users/zhuningkang/Documents/git/github/vita/be-vita-hot-engine
/opt/homebrew/opt/python@3.10/bin/python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

准备配置：

```bash
cp .env.example .env.develop
```

关键配置项：

| 变量名 | 说明 |
| --- | --- |
| `APP_NAME` | 服务名称 |
| `APP_ENV` | 运行环境，默认 `develop` |
| `APP_HOST` | 服务监听地址；容器部署建议使用 `0.0.0.0` |
| `APP_PUBLIC_HOST` | 对外访问主机名或 IP，仅用于拼接访问地址和部署说明 |
| `APP_PORT` | 服务监听端口；Docker 部署时也作为宿主机映射端口 |
| `APP_LOG_DIR` | Docker 部署日志目录；容器会将 `be-vita-hot-engine.log` 写入该目录 |
| `HOT_API_TOKEN` | 内部 Bearer Token |
| `HOT_HTTP_TIMEOUT` | 上游请求超时时间，单位秒 |
| `HOT_DAILYHOT_BASE_URL` | 已废弃，仅保留兼容读取；当前 Python 原生取数主流程不会再依赖它 |
| `HOT_ZHIHU_COOKIE` | 预留给后续直连抓取模式的知乎 Cookie |
| `HOT_FILTER_WEIBO_ADVERTISEMENT` | 是否启用微博广告项过滤，默认 `false` |

说明：`APP_PUBLIC_HOST` 只用于拼接访问地址，不参与 FastAPI 监听地址和路由注册。
说明：`APP_LOG_DIR` 只用于 Docker 容器日志落盘；当前日志文件固定为 `${APP_LOG_DIR}/be-vita-hot-engine.log`。

## 启动方式

开发启动：

```bash
source .venv/bin/activate
set -a
source .env.develop
set +a
uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" --reload
```

访问示例：

- 健康检查：`GET /api/v1/health`
- 源列表：`GET /api/v1/hot/sources`
- 单源快照：`GET /api/v1/hot/{source_code}`
- 对外访问地址：`http://{APP_PUBLIC_HOST}:{APP_PORT}/api/v1/...`

源目录说明：

- `/api/v1/hot/sources` 返回全部物化后的榜单定义，而不是仅返回少量固定源
- 带参数的榜单已展开为固定编码
- 默认榜单保留兼容别名

示例：

- `github`：默认日榜
- `github__weekly`：周榜
- `smzdm`：今日热门
- `smzdm__30`：月热门
- `genshin`：原神公告
- `starrail__3`：崩坏：星穹铁道资讯

## 接口示例

健康检查：

```bash
set -a
source .env.develop
set +a
BASE_URL="http://${APP_PUBLIC_HOST}:${APP_PORT}"

curl "${BASE_URL}/api/v1/health"
```

查询源列表：

```bash
curl "${BASE_URL}/api/v1/hot/sources" \
  -H 'Authorization: Bearer replace-with-a-secure-token'
```

查询微博热搜：

```bash
curl "${BASE_URL}/api/v1/hot/weibo" \
  -H 'Authorization: Bearer replace-with-a-secure-token'
```

查询 GitHub 周榜：

```bash
curl "${BASE_URL}/api/v1/hot/github__weekly" \
  -H 'Authorization: Bearer replace-with-a-secure-token'
```

源列表响应项示例：

```json
{
  "sourceCode": "github__weekly",
  "routeCode": "github",
  "iconKey": "github",
  "sourceName": "GitHub 趋势",
  "sourceType": "周榜",
  "description": "",
  "enabled": true,
  "defaultVisible": false
}
```

单源响应结构：

```json
{
  "sourceCode": "weibo",
  "routeCode": "weibo",
  "sourceName": "微博热搜",
  "sourceType": "热搜榜",
  "fetchedAt": "2026-05-11T12:00:00Z",
  "items": [
    {
      "rank": 1,
      "title": "示例标题",
      "url": "https://example.com",
      "hotValue": "123456",
      "cover": null,
      "summary": null,
      "publishedAt": null
    }
  ]
}
```

错误结构：

```json
{
  "code": "upstream_fetch_failed",
  "detail": "failed to fetch source weibo",
  "sourceCode": "weibo"
}
```

## 运行测试

```bash
source .venv/bin/activate
pytest
```

## Docker

构建镜像：

```bash
docker build -f deploy/Dockerfile -t be-vita-hot-engine .
```

使用 `docker run`：

```bash
set -a
source .env.production
set +a

mkdir -p "${APP_LOG_DIR}"

docker run --rm \
  --env-file .env.production \
  -v "${APP_LOG_DIR}:${APP_LOG_DIR}" \
  -p "${APP_PORT}:${APP_PORT}" \
  be-vita-hot-engine
```

使用 compose：

```bash
docker compose --env-file .env.production -f deploy/docker-compose.yaml up --build
```

如果你要自定义 `APP_LOG_DIR`，需要在执行 `docker compose` 时通过 `--env-file` 或当前 shell 环境提供该变量，不能只依赖 `env_file: ../.env.production` 给容器注入。

容器启动后可通过 `http://${APP_PUBLIC_HOST}:${APP_PORT}/api/v1/health` 访问健康检查。
容器日志会落盘到 `${APP_LOG_DIR}/be-vita-hot-engine.log`，同时继续可通过 `docker logs be-vita-hot-engine` 查看实时输出。

直接启动项目：
```bash
# 激活虚拟环境
source .venv/bin/activate

# 加载环境变量到当前 Shell
set -a
source .env.develop
set +a

# 启动服务
uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT"
```
