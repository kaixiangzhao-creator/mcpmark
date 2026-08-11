# MCPMark WebArena 业务数据外置与 venv 状态管理方案

## 1. 目标与边界

本文针对 MCPMark `playwright_webarena` 的三个环境：

- `shopping_final_0712`
- `shopping_admin_final_0719`
- `postmill-populated-exposed-withimg`

目标是把数据库、媒体、索引、Session、缓存和日志从 Docker 镜像拆出，由 Python venv 中的状态管理程序负责基准校验、每任务快照克隆、运行时挂载和清理。Docker 镜像只保留官方 sandbox base、Magento/Postmill 应用及固定版本运行依赖。

“venv 实现”只指控制面。PHP、Nginx、MySQL、PostgreSQL、Redis、Elasticsearch 不能由 venv 替代，仍在容器或独立服务中运行。

必须满足：任务/verifier 语义不变；每次看到相同基准；任务间无状态污染；支持并行；保留 legacy 回退；凭据不进入镜像或 baseline。

## 2. 当前实现和实测

当前 [`playwright_state_manager.py`](https://github.com/eval-sys/mcpmark/blob/main/src/mcp_services/playwright_webarena/playwright_state_manager.py) 使用固定映射：

| Category | Image | 容器 | 端口 |
|---|---|---|---:|
| `shopping` | `shopping_final_0712` | `shopping` | 7770 |
| `shopping_admin` | `shopping_admin_final_0719` | `shopping_admin` | 7780 |
| `reddit` | `postmill-populated-exposed-withimg` | `forum` | 9999 |

每任务删除旧容器并从完整镜像新建，以容器可写层实现全量回滚。

### 2.1 镜像大小

本机 `docker image inspect .Size` 的十进制结果：

| Image | 大小 |
|---|---:|
| `shopping_admin_final_0719:latest` | 9.64 GB |
| `shopping_final_0712:latest` | 67.58 GB |
| `postmill-populated-exposed-withimg:latest` | 53.44 GB |
| 当前 Shopping Admin AEnv | 2.74 GB |
| 当前 Shopping AEnv | 44.63 GB |
| 当前 Postmill AEnv | 45.66 GB |
| 官方 `sts_ai_agent_sandbox/base:v0.1.2` | 0.52 GB |

`docker image inspect`、Harbor 传输和容器内 `du` 口径不同，不能直接相减承诺 registry 大小。

### 2.2 业务数据

| 环境 | 路径 | 逻辑大小 | 处理 |
|---|---|---:|---|
| Shopping | `/var/www/magento2/pub/media` | 52.11 GB | 外置，只读/COW |
| Shopping | `/var/lib/mysql` | 3.79 GB | 每任务快照 |
| Shopping | Magento log | 3.19 GB | 删除 |
| Shopping | ES data | 约 2.67 GB | snapshot/重建 |
| Shopping Admin | `/var/lib/mysql` | 0.36 GB | 每任务快照 |
| Shopping Admin | `pub` | 0.09 GB | 外置/保留 |
| Shopping Admin | `var` | 0.55 GB | cache/log/session 清理 |
| Postmill | `public/submission_images` | 40.36 GB，31,467 文件 | 外置，只读/COW |
| Postmill | `/usr/local/pgsql/data` | 4.99 GB | 每任务快照 |
| Postmill | 排除图片的应用目录 | 0.42 GB | runtime image |

[`customer_segmentation_setup`](https://github.com/eval-sys/mcpmark/blob/main/tasks/playwright_webarena/standard/shopping_admin/customer_segmentation_setup/description.md) 会新增客户组和客户；[`movie_reviewer_analysis`](https://github.com/eval-sys/mcpmark/blob/main/tasks/playwright_webarena/standard/reddit/movie_reviewer_analysis/description.md) 明确统计图片/海报帖子。因此数据库必须重置，图片能移出镜像但不能从评测语义中消失。

### 2.3 Docker layer 放大

当前转换镜像在 COPY 大目录后递归 `chown`，OverlayFS 可能把文件复制到新层：

- Shopping：`/var/www` 层 57.4 GB、MySQL 3.89 GB，后续 RUN 又 2.91 GB。
- Postmill：`/var/www` 41.8 GB、含 PG data 的 `/usr` 6.51 GB，后续 RUN 又 5.28 GB。

重构后小代码使用 `COPY --chown`；baseline 制作时一次性设置 UID/GID。禁止对 40 GB 目录做构建期/启动期 `chown -R`。

## 3. 目标架构

```text
MCPMark venv
├── evaluator / Playwright / verifier
├── ExternalStateBackend
├── SnapshotDriver
└── state CLI
        │ prepare / inspect / cleanup
        ▼
精简 runtime image
├── 官方 sandbox base
├── Magento/Postmill + PHP/Nginx
├── 必要服务程序
└── AEnv gateway（AEnv 模式）
        ├── 每任务 DB clone（可写）
        ├── 共享媒体 baseline（只读/COW）
        ├── cache/session/log（可写）
        └── ES snapshot/clone
```

venv 通过 Docker/platform API、mount spec、环境变量、HTTP 和 cleanup token 组装环境。StateManager 继续设置 `task.base_url`；TaskManager 继续用 `WEBARENA_BASE_URL` 给 verifier 注入动态地址。

## 4. 数据布局和 Manifest

```text
/srv/mcpmark-state/
├── baselines/
│   ├── shopping/0712/{manifest.json,mysql,media,elasticsearch}
│   ├── shopping_admin/0719/{manifest.json,mysql,media,elasticsearch}
│   └── reddit/postmill-withimg/{manifest.json,postgres,submission_images}
└── runs/<run-id>/
    ├── state.json
    ├── database/
    ├── media-upper/
    ├── cache/
    ├── session/
    └── logs/
```

baseline 固定源镜像 digest、数据库版本、snapshot 格式、文件数量和 tree digest，禁止 `latest`。

```json
{
  "schema_version": 1,
  "profile": "reddit/postmill-withimg",
  "source_image": "postmill-populated-exposed-withimg@sha256:<digest>",
  "database": {
    "engine": "postgresql",
    "version": "<exact-version>",
    "snapshot_format": "cold-directory",
    "path": "postgres"
  },
  "media": {
    "mode": "readonly",
    "path": "submission_images",
    "file_count": 31467,
    "tree_digest": "sha256:<digest>"
  }
}
```

## 5. Baseline 制作

不能在数据库持续写入时直接复制 data directory：

- MySQL/MariaDB：停库冷复制，或匹配版本的 `mariabackup`。
- PostgreSQL：停库冷复制，或 `pg_basebackup`。
- Elasticsearch：snapshot API，或停进程后复制。

逻辑 dump 仅作可移植回退；严格还原优先物理快照，避免序列、统计信息和索引状态变化。

Shopping 导出 MySQL、媒体原图、ES snapshot；排除 log/page cache/session/tmp/Redis/生成缩略图缓存。Shopping Admin 使用独立 baseline。Postmill 导出 PG 和完整 submission_images；当前无图片上传任务时可只读挂载，未来有上传任务改 COW。

## 6. venv 控制层

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e .
```

建议 `pyproject.toml` 增加：

```toml
[project.optional-dependencies]
webarena-state = ["filelock>=3.16,<4"]
test = ["pytest>=8,<9"]
```

`mariabackup`、`pg_basebackup`、`btrfs`、`zfs`、`xfs_io`、CSI 工具是系统依赖，不由 venv 提供。

```python
@dataclass
class PreparedState:
    run_id: str
    profile: str
    mounts: list[MountSpec]
    environment: dict[str, str]
    cleanup_token: str

class StateBackend(Protocol):
    def prepare(self, profile: str, run_id: str) -> PreparedState: ...
    def cleanup(self, cleanup_token: str) -> None: ...
    def inspect(self, cleanup_token: str) -> dict: ...
```

SnapshotDriver：

- `reflink`：本地 XFS/Btrfs 推荐。
- `btrfs`/`zfs`：子卷快照。
- `copy`：兼容但慢、真实复制。
- `csi`：Kubernetes/AEnv VolumeSnapshot。

prepare 必须事务化：加锁、校验 manifest、建唯一 run、克隆 DB、准备媒体/cache/session/log、原子写 state.json；失败全回滚。cleanup 幂等且只能删除 token 对应 run。

## 7. 每任务生命周期

Shopping：克隆 MySQL；创建空 Redis/Session/cache/log；媒体只读/COW，缩略图写 run；恢复 ES 或重建；启动动态容器；等待 MySQL/Magento/HTTP；设置动态 base URL；结束删除容器、DB clone、所有 writable state。

Shopping Admin 同理，并验证新增客户/客户组在下一次 prepare 后消失。

Postmill：克隆 PG；挂载共享图片或 COW media；创建空 Symfony cache/log/session；启动并等待 PG/HTTP；结束删除 DB clone、新上传和 cache，保留历史图片。

## 8. 精简 runtime image

保留：官方 sandbox base、固定 PHP/Nginx、应用代码/vendor、必要服务程序、AEnv venv/健康入口、空挂载点。

排除：DB data、Magento 大媒体、Postmill submission_images、ES/Redis data、cache/session/log/tmp、tar 和中间文件。

长期在官方 Debian base 原生安装兼容依赖，避免搬整个 Alpine `/usr`、`/lib`、`/etc`。短期可用 `source-pruned` 多阶段，但最终只能复制排除业务 data 后的运行时。

统一挂载点：

```text
/state/database
/state/media
/state/cache
/state/session
/state/log
```

再映射到应用原路径。Magento media 含生成 cache，优先 COW；Postmill 当前可直接只读挂载 submission_images。禁止只读父挂载遮蔽需写子目录。

## 9. 缩容后大小和重启成本

以下是基于官方 base 0.52 GB、layer history 和目录实测的保守验收目标，不是重构完成后的实测：

| 环境 | 当前 AEnv | 第一阶段 runtime 目标 | 原生重建/服务外置 |
|---|---:|---:|---:|
| Shopping Admin | 2.74 GB | ≤2.5 GB | 1.5–2.2 GB |
| Shopping | 44.63 GB | ≤7 GB（含 ES runtime） | 2–4 GB（ES 外置） |
| Postmill | 45.66 GB | ≤4 GB | 1.5–3 GB |

每次评测：

| 环境 | 冷拉取 | warm restart | DB 逻辑 clone | COW 物理增量目标 | 临时预算 |
|---|---:|---:|---:|---:|---:|
| Shopping Admin | ≤2.5 GB | 近 0 | 0.36 GB | 10–200 MB | 0.1–0.5 GB |
| Shopping | ≤7 GB | 近 0 | 3.79 GB | 50–500 MB | 0.5–2 GB |
| Postmill | ≤4 GB | 近 0 | 4.99 GB | 20–500 MB | 0.1–1 GB |

共享 baseline 一次存储：Shopping 媒体 52.11 GB + DB 3.79 GB + ES；Admin DB 0.36 GB；Postmill 图片 40.36 GB + DB 4.99 GB。

`copy` driver 会真实复制完整 DB，不能使用 COW 增量表。目标：reflink prepare <10 秒；Shopping ready <180 秒；Postmill ready <120 秒；cleanup <10 秒。

## 10. MCPMark 修改点

仓库：[`eval-sys/mcpmark`](https://github.com/eval-sys/mcpmark/tree/main)。

### 10.1 `playwright_state_manager.py`

修改 [状态管理器](https://github.com/eval-sys/mcpmark/blob/main/src/mcp_services/playwright_webarena/playwright_state_manager.py)：

1. 保留 `legacy-docker`，新增 `external-state`。
2. Category 改为 runtime image + baseline profile。
3. prepare 后生成 `--mount`/`--env` 再 docker run。
4. 容器名 `mcpmark-<category>-<run-id>`，动态 host port。
5. readiness 失败同时清容器和 state。
6. cleanup 先停容器，再 backend.cleanup。
7. `skip_cleanup` 输出 state/显式清理命令。
8. 不再删除用户固定名容器。

```python
CATEGORY_CONFIGS = {
    "shopping": {
        "runtime_image": "mcpmark/shopping-runtime:0712-v1",
        "state_profile": "shopping/0712",
        "container_port": 8080, "readiness_path": "/",
    },
    "shopping_admin": {
        "runtime_image": "mcpmark/shopping-admin-runtime:0719-v1",
        "state_profile": "shopping_admin/0719",
        "container_port": 8080, "readiness_path": "/admin",
    },
    "reddit": {
        "runtime_image": "mcpmark/postmill-runtime:withimg-v1",
        "state_profile": "reddit/postmill-withimg",
        "container_port": 8080, "readiness_path": "/",
    },
}
```

### 10.2 新增模块

```text
src/mcp_services/playwright_webarena/state/
├── backend.py
├── external_backend.py
├── legacy_backend.py
├── models.py
├── profiles.py
├── state_cli.py
└── snapshot/{base.py,reflink.py,copy.py,csi.py}
```

```bash
.venv/bin/python -m src.mcp_services.playwright_webarena.state.state_cli \
  bootstrap --profile shopping/0712 --source-image shopping_final_0712:latest
.venv/bin/python -m src.mcp_services.playwright_webarena.state.state_cli \
  prepare --profile shopping/0712 --run-id smoke-001 --output json
.venv/bin/python -m src.mcp_services.playwright_webarena.state.state_cli \
  cleanup --run-id smoke-001
```

bootstrap 是一次性管理操作，不在每次评测从大 tar 导入。

### 10.3 `src/services.py`

在 config schema 和 state_manager mapping 增加：

| 环境变量 | 默认 |
|---|---|
| `WEBARENA_STATE_BACKEND` | `legacy-docker` |
| `WEBARENA_STATE_ROOT` | `/srv/mcpmark-state` |
| `WEBARENA_SNAPSHOT_DRIVER` | `reflink` |
| `WEBARENA_RUNTIME_REGISTRY` | 空 |
| `WEBARENA_MEDIA_MODE` | `readonly` |
| `WEBARENA_RESET_TIMEOUT` | `300` |
| `WEBARENA_KEEP_FAILED_STATE` | `false` |

先保持 legacy 默认，回归后切 external-state。

### 10.4 `src/evaluator.py`

把 cleanup 放入覆盖 setup→execute→verify 的 `try/finally`。setup 部分成功即登记 cleanup token；agent/verifier 异常也释放。仅 KEEP_FAILED_STATE 时保留失败 run。GC 只能删有 MCPMark manifest 且超 TTL 的 run。

### 10.5 `src/factory.py`

现有 mapping 可传新增参数，无需结构重写；增加 schema→ExternalStateBackend 构造测试。

### 10.6 TaskManager/verifier

[`playwright_task_manager.py`](https://github.com/eval-sys/mcpmark/blob/main/src/mcp_services/playwright_webarena/playwright_task_manager.py) 已使用 `task.base_url` 和 `WEBARENA_BASE_URL`。审计所有 verifier：优先动态 URL；7770/7780/9999 仅调试 fallback；不修改任务与标准答案。

### 10.7 文档

修改 [`docs/mcp/playwright.md`](https://github.com/eval-sys/mcpmark/blob/main/docs/mcp/playwright.md)：大 tar 标 legacy；新增 runtime image、baseline bootstrap、状态变量、snapshot、inspect/cleanup/gc、容量检查和图片约束。同步 `docs/installation_and_docker_usage.md` 与 env 示例。

## 11. 测试

新增：

```text
tests/playwright_webarena/
├── test_external_state_backend.py
├── test_snapshot_driver.py
├── test_state_manager_external.py
├── test_cleanup_on_failure.py
└── test_parallel_isolation.py
```

单元测试：prepare 唯一、baseline 只读、cleanup 幂等、失败回滚、token 隔离、legacy 不变。

集成测试：

- Shopping：搜索/SKU/价格/评论一致；修改购物车/比较；重置后为空。
- Admin：创建 Premium Europe/客户；重置后新增消失、计数恢复。
- Postmill：图片帖子数一致；新增账号/帖子/投票；重置后消失。

原大镜像与 external-state 完整比较 verifier、答案字段、搜索数量/排序/分页、DOM selector、图片 HTTP/MIME/宽高、连续运行初态和并行隔离。占位图还需视觉模型回归。

## 12. 上线顺序

1. 固定源 digest，记录 golden。
2. 先移出 cache/log，消除递归 chown。
3. 外置数据库，实现 snapshot/并行隔离。
4. 外置原图，先只读/COW，不用占位图。
5. 构建精简 runtime，达到体积目标。
6. CI/小流量 external-state，保留 legacy。
7. 全回归后切默认。

## 13. AEnv

AEnv artifact 引用精简 runtime 的不可变 Harbor digest。数据通过 CSI snapshot、共享只读 PVC、节点 baseline cache、独立 snapshot 服务或对象存储挂载。

`deployConfig.service.enableStorage=true` 只代表持久存储，不等于自动从 baseline 克隆。未确认 AEnv snapshot/clone 前不能假设开启 storage 即完成方案。

如果平台只能启动单镜像且不能挂载 baseline，venv 无法单独补齐 40–52 GB 数据；需平台增加快照、使用外部状态服务，或采用占位图并接受视觉保真下降。

## 14. 完成标准

- runtime 达到目标并固定 digest；
- baseline 有 manifest/版本/校验；
- prepare/cleanup 幂等、并行隔离；
- 所有 easy/standard 回归；
- 连续运行初态一致；
- Postmill 图片计数不变；
- Magento 搜索数量/排序/分页不变；
- 异常不泄漏 clone；
- AEnv 真实远程实例通过。

## 15. 结论

- venv：控制、快照、验证、清理。
- runtime image：官方 base、应用、固定依赖。
- baseline：版本化业务初始数据。
- per-run：DB COW、Session、cache、log、新上传。

图片无需留在 Docker layer，但仍属于评测基准，应外置只读/COW，而不是删除。预计冷启动分别只拉取不超过约 2.5 GB、7 GB、4 GB；warm restart 不再重复传输 40–52 GB 媒体。
