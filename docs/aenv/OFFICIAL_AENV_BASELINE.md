# Astrolabe AEnv 官方能力基线

本文只记录从 Compass AEnv 官方文档和 `shopee-aenvironment==0.1.96` 实际安装包确认的
能力。记录日期为 2026-08-11。后端行为仍须以真实远程实例验证为准。

官方文档：<https://compass.llm.shopee.io/astrolabe/documentation/aenv>

## 1. 固定工具版本

本项目固定使用：

```text
shopee-aenvironment==0.1.96
```

安装：

```bash
python3 -m venv .venv-aenv
.venv-aenv/bin/pip install \
  shopee-aenvironment==0.1.96 \
  --index-url https://pypi.shopee.io
```

本次实测版本信息：

```text
AEnv SDK Version: 0.1.96
Build Commit: f417ac9
```

`COMPASS_ADMIN_API_KEY` 只能由进程环境、CI secret 或运行时 secret 注入，不能写入仓库。

## 2. 官方构建与发布路径

官方文档规定的项目结构包含：

```text
environment/
├── config.json
├── mcp_config.json
├── Dockerfile
├── requirements.txt
└── src/
    ├── mcp_gateway.py
    └── custom_env.py
```

官方基本流程是：

```bash
aenv init <environment-name>
aenv build --push
aenv push
```

0.1.96 的 `aenv build` 实测支持：

- `--work-dir`、`--dockerfile`；
- `--image-name`、多个 `--image-tag`；
- `--registry`、`--namespace`；
- `--type local|remote`；
- `--push`；
- `--platform`。

因此三个环境必须各自维护可复现的 AEnv project，而不是仅给现有大镜像追加 tag。

## 3. Sandbox instance

官方 Python SDK 用法：

```python
from aenv import Environment

async with Environment("name@version", ttl="5m") as env:
    tools = await env.list_tools()
```

0.1.96 `Environment` 构造参数已确认包含：

- `env_name`、`ttl`、`instance_id`；
- `datasource`；
- `cpu`、`memory`、`warm_pool_size`；
- `environment_variables`、`arguments`；
- `startup_timeout`、`api_key`、`owner`；
- `aenv_url`、`aenv_data_url`。

Sandbox-backed 环境还支持 `create_shell_session()`。但是现有官方入门页面没有承诺普通 sandbox
instance 会把任意业务容器端口直接暴露为 Playwright 可访问 URL。因此不得在没有实测的情况下
把 Shopping 的 80 端口等同于 SDK 的 MCP/functions endpoint。

## 4. Environment service 与 PVC

官方 `config.json` 示例的 `deployConfig.service` 包含：

```json
{
  "replicas": 1,
  "port": 8081,
  "enableStorage": false,
  "storageName": "aenv",
  "storageSize": "10Gi",
  "mountPath": "/home/admin/data"
}
```

0.1.96 的 `AEnvSchedulerClient.create_env_service()` 和请求模型进一步确认支持：

- `service_name`、`replicas`、`environment_variables`、`owner`；
- `pvc_name`、`mount_path`、`storage_size`；
- `port`；
- CPU、memory 和 ephemeral storage 的 request/limit；
- 返回 `service_url` 和 `pvc_name`。

SDK 注释明确说明：指定 `storage_size` 时会创建 PVC，并且 `replicas` 必须为 1；StorageClass
由后端部署配置，不能通过该 API 指定。

这使“Web runtime 小镜像 + AEnv 官方 PVC”成为当前最符合官方能力的候选架构：

```text
AEnv service runtime (<10GB)
  + PVC mount
      ├── immutable media baseline
      ├── database baseline
      └── task writable/reset state
```

但 SDK 提供“创建空 PVC”不等于已经解决 40–52GB baseline 的上传、预置、快照和跨服务复用。
这些能力必须通过后端 API、CLI 配置和最小实验继续确认。

## 5. 当前决策

在最小远程实验完成前：

1. 不把普通 sandbox 假定为可直接访问的 Web 服务；
2. 不把 PVC 假定为支持任意宿主机 bind mount；
3. 不把 `datasource` 假定为可替代业务图片和数据库目录；
4. 不上传新的大镜像作为“外置数据”替代方案；
5. 先创建一个小型 HTTP AEnv service，验证 `service_url`、端口、PVC 持久性和日志；
6. 实验通过后再确定三个环境是使用逐题 service、固定 service slot，还是 sandbox + 官方代理。

## 6. 必须补齐的官方实测证据

- `aenv build --push` 与 `aenv push` 的真实成功记录；
- 从 Hub 通过 SDK 创建实例/服务，而不是仅看 UI 状态；
- `service_url` 可被 Playwright 所在执行环境访问；
- PVC 在 Pod/实例重建后的持久性；
- baseline 向 PVC 导入的官方支持路径和吞吐；
- 多任务是否能复用同一只读 baseline，或是否需要三个独立 PVC；
- reset 操作的原子性、耗时和失败恢复；
- build、scheduler、startup 和 application 日志的真实定位方式。

缺少上述证据时，架构结论标记为“候选”，不得标记为“已完成”。
