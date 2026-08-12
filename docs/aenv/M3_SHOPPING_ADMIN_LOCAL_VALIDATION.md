# M3 Shopping Admin 本地验收

验收日期：2026-08-12

## 构建对象

```text
source image:
  shopping_admin_final_0719:latest
  sha256:993d1ee9c1355ad56b7e5282cb0308efbe09d74a517213d3f072f28b9409a591

runtime image:
  harbor.shopeemobile.com/ai-infra/shopping-admin-final-0719:2.0.0
  sha256:00a48cb834130630b34465794022b33919721742c450f63f0fb905dfb57d423b
```

runtime 使用 `shopee-aenvironment==0.1.96` 的官方 CLI 构建，最终 stage 为
`sts_ai_agent_sandbox/base:v0.1.2`。AEnv 0.1.96 local builder 固定 `pull=true`，所以将已加载的
source image 推入只监听 `127.0.0.1:5000` 的本机 registry，作为 donor stage 的兼容引用。
未修改官方 SDK。

## 外置状态

从原镜像导出的 pristine baseline 包含：

- `/var/lib/mysql`；
- `/var/www/magento2/pub/media`；
- `/usr/share/java/elasticsearch/data`。

本次实测 baseline 为 437MB、2088 个文件；manifest 文件的 SHA-256 为：

```text
6ccc2bcf3a555e7654aa1be92fd17a40e0b13f4d8c7c84a4c829b1db6a2da4dd
```

manifest 与数据保存在仓库外的 `mcpmark-data`，不进入 Git。首次 smoke 直接挂载 baseline 后，
MariaDB crash recovery 会修改它；该结果被废弃。正式 smoke 从重新导出的 pristine baseline
通过 reflink 创建独立 writable slot，证明“容器重启不等于状态重置”。

## 体积门禁

| 口径 | 实测 | 门禁 |
| --- | ---: | ---: |
| `docker image inspect .Size` | 1,654,501,329 bytes | < 10,000,000,000 bytes |
| `docker system df -v` cumulative size | 5.93GB | < 10GB |

两种口径均通过。相比已有 1.0.1 的约 13GB 本地累计 layer，新版本避免了递归 chown 复制层，
并把 baseline 与历史日志移出 runtime。

## 功能验收

挂载独立 writable slot 后：

| 检查 | 结果 |
| --- | --- |
| 官方 health `:49999/health` | HTTP 200 |
| AEnv health `:8081/health` | HTTP 200 |
| Magento 首页 | HTTP 302/200 启动流程正常 |
| Magento `/admin` | HTTP 302，与原始镜像对照一致 |
| 代表性媒体文件 | HTTP 200，1869 bytes |
| supervisor | MariaDB、Elasticsearch、Nginx、PHP-FPM、Redis、Mailcatcher、AEnv 均 RUNNING |
| MCP tools | `webarena_status`、`configure_public_url` 可发现 |
| `configure_public_url` | 真实 MCP 调用成功，两个 base URL 更新并 flush cache |

第一版只创建空日志目录前，Nginx 和 Elasticsearch 因原配置引用日志路径而退出；修正为保留空的
可写日志目录，不把历史日志放回镜像。第二版移除了整个 Magento `var`，导致 `/admin` 由原镜像
的 302 变为 404；最终版只清空 log/cache/session/page_cache，保留不足 100MB 的必要 runtime
元数据，恢复到与原镜像一致的 302。

## 尚未通过的门禁

- 本版本尚未推送 Harbor/AEnv Hub；
- 远程 PVC 尚未导入 baseline；
- 尚未创建并验证 2.0.0 的真实远程 service；
- Shopping 和 Postmill runtime 尚未完成；
- MCPMark provider 尚未接入。

因此本报告只证明 Shopping Admin 的本地小型 runtime 和外置数据组合通过，不代表整个任务完成。
