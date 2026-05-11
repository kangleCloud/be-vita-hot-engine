# be-vita-hot-engine

`be-vita-hot-engine` 是独立的 Python 热榜抓取服务，面向 `be-vita` 内部调用，负责抓取并归一化核心热榜数据，对外仅暴露只读 HTTP 接口。

## 当前能力

- 服务框架：FastAPI
- Python 基线：`3.10`
- 认证方式：`Authorization: Bearer <HOT_API_TOKEN>`
- 已支持源：`weibo`、`zhihu`、`baidu`、`bilibili`、`juejin`、`ithome`、`36kr`、`sspai`
- v1 不包含 Redis、定时任务、管理后台和数据库

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
| `APP_HOST` | 监听地址 |
| `APP_PORT` | 监听端口 |
| `HOT_API_TOKEN` | 内部 Bearer Token |
| `HOT_HTTP_TIMEOUT` | 上游请求超时时间，单位秒 |

## 启动方式

开发启动：

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问示例：

- 健康检查：`GET /api/v1/health`
- 源列表：`GET /api/v1/hot/sources`
- 单源快照：`GET /api/v1/hot/{source_code}`

## 接口示例

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

查询源列表：

```bash
curl http://127.0.0.1:8000/api/v1/hot/sources \
  -H 'Authorization: Bearer replace-with-a-secure-token'
```

查询微博热搜：

```bash
curl http://127.0.0.1:8000/api/v1/hot/weibo \
  -H 'Authorization: Bearer replace-with-a-secure-token'
```

单源响应结构：

```json
{
  "sourceCode": "weibo",
  "sourceName": "微博热搜",
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

使用 compose：

```bash
docker compose -f deploy/docker-compose.yaml up --build
```
