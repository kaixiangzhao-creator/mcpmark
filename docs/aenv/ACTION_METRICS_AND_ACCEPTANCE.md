# WebArena 小型 AEnv 行动指标与验收标准

## 1. 范围和基线

目标环境：

| MCPMark category | 原始 Docker 镜像 | 默认端口 |
| --- | --- | ---: |
| `shopping` | `shopping_final_0712:latest` | 7770 |
| `shopping_admin` | `shopping_admin_final_0719:latest` | 7780 |
| `reddit` | `postmill-populated-exposed-withimg:latest` | 9999 |

本机首次盘点观察到的 Docker 展开大小约为 141GB、19.6GB、107GB。该值只是初始观察，
正式基线必须保存 `docker image inspect`、layer history、容器目录占用与数据清单证据。

## 2. 行动指标

### 2.1 可审计性

| 指标 | 要求 |
| --- | --- |
| 原始镜像标识 | 保存 image ID、RepoDigest（如有）、创建时间和架构 |
| 内容取证 | 保存主要目录体积、数据库目录、媒体目录、缓存和日志体积 |
| 数据完整性 | 为外置 baseline 保存文件数、字节数和校验 manifest |
| 版本追踪 | 每个关键版本有 Git commit、构建 tag 和 AEnv 标识 |
| 凭据安全 | Git 历史和文档扫描不得出现有效 token/secret |

### 2.2 体积和启动效率

所有数值以实际工具输出为证，不使用 tar 文件名或 UI 展示值替代。

| 指标 | 硬门禁 | 目标值 |
| --- | ---: | ---: |
| Shopping registry/inspect size | `< 10,000,000,000 bytes` | `<= 7GB` |
| Shopping 本地解包累计 layer size | `< 10GB` | `<= 9GB` |
| Shopping Admin registry/inspect size | `< 10,000,000,000 bytes` | `<= 2.5GB` |
| Shopping Admin 本地解包累计 layer size | `< 10GB` | `<= 8GB` |
| Postmill registry/inspect size | `< 10,000,000,000 bytes` | `<= 4GB` |
| Postmill 本地解包累计 layer size | `< 10GB` | `<= 8GB` |
| 单题重复执行时重新下载完整媒体 | `0` | `0` |
| 同一节点镜像重复 pull/load | 非版本变化时 `0` | `0` |
| 健康检查 | 在官方 AEnv 超时内成功 | 记录 P50/P95 |

### 2.3 状态隔离

| 状态 | 每道题要求 |
| --- | --- |
| MySQL/PostgreSQL | 从固定 baseline 创建新快照、clone 或等价恢复 |
| 登录 session/cookie | 清空并重新创建 Playwright Browser Context |
| 应用 cache | 清空或切换到任务独立目录 |
| 可写媒体 | 使用任务独立 COW/upper，结束后丢弃 |
| 只读图片 | 可以跨任务共享，但校验值和 URL 语义必须稳定 |
| 后台任务/进程 | 不得延续上一题产生的任务和状态 |

状态泄漏测试至少执行同一 category 的顺序测试：题 A 做可观测写入，结束后启动题 B，确认
数据库、页面、session、cache 和可写文件均不存在 A 的变化。

## 3. 官方 AEnv 合规门禁

每个环境必须满足：

1. 使用 Astrolabe AEnv 官方文档允许的 base、构建与上传流程；
2. 使用用户指定的 `shopee-aenvironment==0.1.96`，除非官方文档明确要求其他版本并记录原因；
3. 上传成功后，必须通过远程 API 创建真实实例，不能只依据 build/upload 状态；
4. 实例内入口进程保持运行，端口、健康检查和工作目录符合官方契约；
5. 保存 build、upload、instance-create、startup 和 application 日志的可定位方式；
6. 从无本机 Docker 缓存的执行上下文验证一次冷启动路径；
7. AEnv 标识、版本、digest 和验收时间写入本地验收报告，不保存凭据。

## 4. Web 与评测一致性

每个环境至少通过以下检查：

- 原始镜像和小型 AEnv 的关键首页、登录页及任务页面均返回预期状态码；
- 静态资源和代表性图片 URL 不出现新增 404；
- Shopping/Shopping Admin 的 Magento base URL、数据库连接和 cache flush 正常；
- Postmill 的 PostgreSQL、图片路径、登录和帖子页面正常；
- 使用相同任务在原始环境与新环境各执行至少一组 smoke verifier；
- 对涉及图片、上传、删除、数据库修改和登录状态的代表任务进行回归；
- Playwright 获得的 URL、DOM/可访问性语义和 verifier 所需状态等价；允许无关的时间戳、实例地址差异。

## 5. MCPMark 适配验收

代码必须：

1. 保留现有 local Docker provider，新增或明确支持 AEnv provider，不把内网地址硬编码到 task/verifier；
2. 通过 category 映射 Shopping、Shopping Admin、Reddit 的 AEnv 环境标识；
3. 在每道题 `set_up` 时创建或分配干净实例/slot，并注入实际 base URL；
4. 在 `clean_up` 时释放实例或可靠恢复任务状态；
5. setup 失败时返回真实错误和日志定位信息，不把失败吞成笼统的 `State Duplication Error`；
6. 支持超时、重试、幂等清理和中断后的资源回收；
7. verifier 继续通过 `WEBARENA_BASE_URL` 或等价显式参数访问当前实例；
8. 单元测试覆盖 provider 选择、category 映射、状态转换、失败清理和 URL 注入；
9. 至少完成三个 category 各一道真实端到端任务或经批准的等价 smoke task。

## 6. GitHub 里程碑

| 里程碑 | 必需产物 | 推送要求 |
| --- | --- | --- |
| M0 执行基线 | `AGENT.md`、本文件 | 独立 commit |
| M1 设计基线 | 两份外置状态设计文档、官方约束记录 | 独立 commit |
| M2 镜像取证 | 三镜像报告、baseline manifest、瘦身预算 | 独立 commit |
| M3 Runtime | 三个可复现构建定义与本地验证 | 可按环境拆分 commit |
| M4 AEnv | 上传记录、环境版本、实例日志与 smoke 结果 | 独立 commit，不含 secret |
| M5 MCPMark | AEnv provider、配置、测试和迁移文档 | 独立 commit |
| M6 E2E | 最终验收报告、已知限制与回滚说明 | 独立 commit/tag |

## 7. Notion 过程记录

用户指定父页面：`MCPmark Toolathlon`。应新建子页面记录关键动作和困难。同步内容必须脱敏，
并至少包括 M0-M6 状态、Git commit、AEnv 版本、验收结果、失败日志位置和下一步。

如果当前执行环境没有 Notion MCP、浏览器登录态或写权限：

1. 在 `docs/aenv/WORKLOG.md` 先完整记录；
2. 明确记录无法同步的具体原因；
3. 获得访问能力后补写 Notion，并在本地记录页面链接和同步时间。

## 8. 最终通过条件

以下条件必须同时满足：

- 三个最终 runtime 镜像的 registry/inspect 大小和本地解包累计 layer 大小均通过 `<10GB` 硬门禁；
- 三个环境均按官方流程上传为 AEnv；
- 三个 AEnv 均通过远程实例创建、启动、健康检查和代表性页面检查；
- 外置图片和数据库继续完整支撑评测，逐题状态隔离测试通过；
- MCPMark 可针对三个 category 自动创建/分配 AEnv、执行、验证和清理；
- GitHub 工作分支包含 M0-M6 可审计历史；
- 本地与 Notion 关键记录均完成，且无凭据泄漏。

任何一个条件缺少证据时，状态只能标为“进行中”或“受阻”，不得标为“成功”。
