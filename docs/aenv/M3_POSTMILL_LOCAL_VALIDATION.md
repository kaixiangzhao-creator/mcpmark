# M3 Postmill 本地验收

验收日期：2026-08-12

## 构建对象

```text
source image:
  postmill-populated-exposed-withimg:latest
  sha256:0a0c002b4dd089db8a22064886cb31f89d5ac493d90f6c41074639d56c6f4fbe

runtime image:
  harbor.shopeemobile.com/ai-infra/postmill-populated-exposed-withimg:2.0.0
  sha256:1bcb4ccda34e490df5a8ca7eeafde6ea9bd700dddfc3d18b8add8c71ca7eca26
```

runtime 使用 `shopee-aenvironment==0.1.96` 官方 CLI 的
`aenv build --no-push` 构建，最终 stage 为
`sts_ai_agent_sandbox/base:v0.1.2`。构建耗时 566.36 秒。AEnv 0.1.96 local builder
固定 `pull=true`，所以先将已加载的 source image 推入只监听 `127.0.0.1:5000`
的本机 registry，作为 donor stage；没有修改官方 SDK，也没有把 donor 推送到 Harbor。

## 外置状态

从原镜像导出的 pristine baseline 包含：

- `/usr/local/pgsql/data`，在 runtime 内映射为 `/aenv-data/postgres`；
- `/var/www/html/public/submission_images`，在 runtime 内映射为
  `/aenv-data/submission_images`。

实测 baseline 为 44GB、33311 个文件，其中图片 31467 个，PostgreSQL 约 4.8GB，
图片约 38.5GB。manifest 文件的 SHA-256 为：

```text
56ad00ecbb7504ac3c0b7161bef1aa798e91e449e9771689f4981a9cd154202b
```

manifest 与数据位于仓库外的 `mcpmark-data`，不进入 Git。每个任务通过 reflink（文件系统
不支持时退化为普通复制）从 pristine baseline 创建新的 writable slot。实测依次创建并启动
`postmill-smoke-1`、`postmill-smoke-2`；第二个 slot 的 Web 和 health 均成功，证明不需要重新拉取
runtime 镜像即可重置有状态数据。

## 体积门禁

| 口径 | 实测 | 门禁 |
| --- | ---: | ---: |
| `docker image inspect .Size` | 1,085,580,495 bytes | < 10,000,000,000 bytes |
| `docker system df -v` cumulative size | 4.39GB | < 10GB |

两种口径均通过。原镜像在本机 `docker system df -v` 的 cumulative size 为 107GB；
40GB 级图片层和 PostgreSQL baseline 均不再进入每次拉起的 runtime。

## 功能验收

挂载独立 writable slot 后：

| 检查 | 结果 |
| --- | --- |
| 官方 health `:49999/health` | HTTP 200 |
| AEnv health `:8081/health` | HTTP 200 |
| Postmill 首页 | HTTP 200，title 为 `Postmill` |
| 原镜像对照 | HTML 长度相同，仅 canonical/OG URL 的宿主端口不同 |
| 代表性图片 | HTTP 200，1,358,180 bytes，与原镜像及 baseline 逐字节一致 |
| PostgreSQL | 正常完成 crash recovery；`submissions` 为 2,551,513 条 |
| supervisor | PostgreSQL、Nginx、PHP-FPM、AEnv 均 RUNNING |
| runtime 用户 | 官方 sandbox 的 `user`（UID/GID 1001） |
| AEnv reward | `/task/reward` 真实调用 HTTP 200、score 1.0 |
| 状态重置 | 从 pristine 创建第二个 slot 后 health/Web 再次通过 |

## 尚未通过的门禁

- 本版本尚未推送 Harbor/AEnv Hub；
- 远程 PVC 尚未导入 baseline；
- 尚未创建并验证 2.0.0 的真实远程 service；
- Shopping runtime 尚未完成；
- MCPMark provider 尚未接入。

因此本报告只证明 Postmill 的本地小型 runtime 与外置 baseline 组合通过，不代表整个任务完成。
