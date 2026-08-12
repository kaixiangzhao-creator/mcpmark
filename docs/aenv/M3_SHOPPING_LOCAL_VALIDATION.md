# M3 Shopping 本地验收

验收日期：2026-08-12

## 构建对象

```text
source image:
  shopping_final_0712:latest
  sha256:ccff8c1772be884313edad94136d2a4048020300a0fc169781c50a02aa8bd206
  inspect size: 67,575,805,572 bytes

runtime image:
  harbor.shopeemobile.com/ai-infra/shopping-final-0712:2.0.0
  sha256:524669203eb69b6c95be3b0a8787cd6bdef536ce52a7a4b9f63528476dbc12d3
```

runtime 的最终 stage 为官方
`harbor.shopeemobile.com/sts_ai_agent_sandbox/base:v0.1.2`，固定安装
`shopee-aenvironment==0.1.96`，最终构建命令为官方
`aenv build --no-push`。最终修正版构建耗时 659.73 秒。

## donor 构建原因

AEnv 0.1.96 local builder 固定 `pull=true`，因此已加载的 source image 先通过
只监听 `127.0.0.1:5000` 的本机 registry 提供。Shopping 源镜像的 parent layer
为 67GB；legacy builder 在这个 parent 上执行排除数据的 RUN 并 commit 时长期无
进展。最终采用 BuildKit 在本机生成仅包含 `/aenv-copy` runtime 内容的 donor，
再由官方 AEnv builder 复制到官方 sandbox final stage。

BuildKit 只生成本地中间 donor，不是发布物；最终镜像仍由官方 CLI 构建。donor
registry manifest digest 为
`sha256:eba3f3e61125fc4b2c7eba72735dab18cf6670030a58eb426b0ad48f4aab0cc5`。

第一版 donor 意外保留了 `/usr/share/java/elasticsearch/data` 目录。Dockerfile 中的
`ln -s` 因目标目录已存在而在目录内部创建链接，Elasticsearch 实际仍使用镜像内 UID 102
的数据并因 `node.lock` 权限失败反复重启。修正版 donor 明确删除 data/logs，发布 Dockerfile
再用 `test ! -e /usr/share/java/elasticsearch/data` 作为构建期门禁，随后才创建指向
`/aenv-data/elasticsearch` 的链接。真实 smoke 中 PID 稳定，证明该问题已经修复。

首次向匿名 Docker registry volume 推送源镜像，在 50.37/57.18GB 时失败。registry
日志的真实根因是其所在 `/data` 分区 `no space left on device`，Docker 客户端表面
错误为 `blob upload invalid`。只删除了可恢复的 donor registry volume，并将 registry
改为仓库外 `/home/toc/SSE/mcpmark-registry` bind mount；没有删除用户镜像或 baseline。

## 体积门禁

| 口径 | 实测 | 门禁 |
| --- | ---: | ---: |
| `docker image inspect .Size` | 1,787,494,859 bytes | < 10,000,000,000 bytes |
| `docker image ls` cumulative layer size | 6.37GB | < 10GB |

两个硬门禁均通过。后续变更仍必须同时重测两个口径，不能只看 inspect size。

## 外置状态

从原镜像导出：

- `/var/lib/mysql` → `/aenv-data/mysql`；
- `/var/www/magento2/pub/media` → `/aenv-data/media`；
- `/usr/share/java/elasticsearch/data` → `/aenv-data/elasticsearch`。

导出包含约 448 万媒体文件，耗时主要来自数百万小文件的目录项、ownership 和 manifest
计算，而非单个大文件。baseline 位于仓库外，不进入 Git。每题仅克隆 MySQL 与
Elasticsearch；历史媒体可只读共享，要求上传/改图的任务使用 COW media。

本次 pristine baseline 实测为 55GB、4,481,037 个文件，其中媒体文件 4,479,817 个；
manifest SHA-256 为：

```text
82f8ffd08c4076859aa8d9679f5026b8fd4cbc0593f197305254f7766f30547d
```

## 功能验收

使用 MCPMark 正式 `external-state` manager 挂载 baseline 并启动发布镜像，结果如下：

| 检查 | 结果 |
| --- | --- |
| 官方 health `:49999/health` | HTTP 200 |
| AEnv health `:8081/health` | HTTP 200 |
| Magento 首页 | HTTP 200，164,866 bytes |
| 商品数据 | `catalog_product_entity` 为 104,368 条，与原镜像一致 |
| 代表性图片 | 19,134 bytes；SHA-256 `4deb39db6f545ef598db942a0bba4a90f08e83e3227e9453ce09373d8a87e14c`，与原镜像一致 |
| Elasticsearch | cluster yellow（单节点正常），PID 19 连续 20 秒不变，外置索引可读 |
| supervisor | MySQL、Elasticsearch、Nginx、PHP-FPM、Redis、Mailcatcher、AEnv 均 RUNNING |
| AEnv reward | `/task/reward` HTTP 200、score 1.0 |
| 外置路径 | MySQL、media、Elasticsearch 均为指向 `/aenv-data` 的软链接 |
| 媒体策略 | readonly mount；容器内写入返回 `Read-only file system` |
| manager cleanup | 容器和拥有 cleanup token 的 run state 均成功清理 |

重置验收连续创建两个独立状态槽。第一槽启动后新建
`magentodb.mcpmark_reset_marker` 并确认有一条数据，再清理该槽；第二槽从 pristine baseline
启动时该表不存在，商品数仍为 104,368，Web/AEnv health 均为 200，Elasticsearch PID
再次保持稳定。这直接证明逐题重置来自 baseline 新槽，而不是复用上一题已修改的容器。

## 远程状态

Shopping 本地 runtime 与外置 baseline 的组合已经通过。Harbor/AEnv Hub 上传状态在本次
上传完成后补记。Admin 与 Postmill 已证明 AEnv Hub 上传不等于远程运行：当前
`/env-service` 返回 HTTP 404/JSON `null`，instance create 也没有留下实例；此外尚缺官方
baseline→逐题 PVC snapshot/clone 机制。因此即使 Hub 上传成功，远程逐题实例仍只能标记为
受阻，直到两个平台前置条件解决。
