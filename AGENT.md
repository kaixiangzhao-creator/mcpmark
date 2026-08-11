# MCPMark WebArena AEnv 改造执行约束

## 目标

将 MCPMark Playwright WebArena 使用的 Shopping、Shopping Admin 和 Reddit/Postmill
三个大体积 Docker 环境改造成符合 Astrolabe AEnv 官方规范的小型运行环境，同时保持
逐题初始状态隔离、页面内容、图片资源、自动验证与评测结果的一致性。

本文件约束参与本改造的人工和自动化 agent。若实现与本文件或官方文档冲突，优先级为：

1. Astrolabe AEnv 官方文档与官方 SDK 行为；
2. MCPMark 官方任务与 verifier 的可复现语义；
3. `docs/aenv/ACTION_METRICS_AND_ACCEPTANCE.md` 的硬性验收门槛；
4. 本仓库内的设计文档和实现便利性。

## 强制原则

1. 先取证，后修改。所有镜像体积、层内容、运行进程、端口、数据库和媒体目录必须来自实际检查。
2. 三个最终 Docker/AEnv runtime 的 Docker image size 均不得超过十进制 10 GB；超限不得上传或标记完成。
3. 业务图片、数据库 baseline 和其他大状态不得伪装成 Python wheel、venv 内容或新的超大启动镜像。
4. venv 只承载 MCPMark、AEnv 客户端和编排逻辑；外置数据由宿主机数据盘、AEnv 官方持久化能力或经批准的对象存储承载。
5. 每道题必须获得与原始镜像等价的干净初始状态。不得因复用容器泄漏上一题的数据库、会话、缓存或可写媒体。
6. 图片不得在没有评测证据的情况下删除、降质或替换占位图。第一阶段保持原始文件及 URL 语义。
7. AEnv 构建、上传、实例创建、日志定位和远程调用必须采用官方文档和固定版本 SDK 支持的方式。
8. 不在仓库、Git 历史、日志、Markdown、命令示例或 Notion 页面记录 token、密码、cookie 或私有 registry secret。
9. 用户已有改动不可覆盖；破坏性清理前必须精确确认对象和可恢复性。
10. 所有“成功”必须有可重复的命令、输出摘要和验收证据，不以控制台状态图标代替实例运行验证。

## 实施边界

### Runtime 镜像应包含

- Web 应用代码与固定版本运行时；
- Nginx/Apache、PHP/Node 等必要服务；
- 官方 AEnv 要求的入口、健康检查及最小系统依赖；
- 恢复、挂载和健康检查所需的小型脚本。

### Runtime 镜像不应包含

- Shopping 的完整 `pub/media` baseline；
- Postmill 的完整 `submission_images` baseline；
- 完整 MySQL/PostgreSQL 数据目录 baseline；
- 历史日志、缓存、session、临时文件、包管理缓存；
- 与运行无关的 tar、构建缓存和重复镜像层。

### 每题状态模型

每道题使用以下逻辑状态：

```text
small immutable runtime
  + immutable external baseline
  + per-task database snapshot/clone
  + per-task writable files/session/cache
  = complete isolated WebArena environment
```

可以逐题创建容器，也可以在有充分证据时复用运行 slot；无论采用哪种方式，逐题状态隔离
必须通过验收，不得仅依赖容器名称或进程重启。

## GitHub 迭代规则

1. 保留 `origin` 指向可写 fork，保留 `upstream` 指向 `eval-sys/mcpmark`；若尚无 fork，则在取得可写权限后建立。
2. 使用独立工作分支，建议名称：`aenv/webarena-external-state`。
3. 关键版本必须独立提交并推送：
   - 执行约束与验收基线；
   - 设计文档基线；
   - 镜像取证和 baseline manifest；
   - 每个 runtime 的构建定义；
   - AEnv provider 与 MCPMark 适配；
   - 端到端验收和运维文档。
4. 提交消息应说明对象和结果，不提交生成的大数据、Docker tar、数据库文件或图片集合。
5. 每次推送前检查 `git diff --check`、敏感信息和相关测试；失败的中间版本允许提交到工作分支，但必须明确标记失败原因。

## 记录要求

本地以 `docs/aenv/` 为权威记录，并在用户指定的 Notion 页面下同步关键动作与困难。
每项记录至少包含：时间、Git commit、镜像/AEnv 版本、执行命令的脱敏形式、结果、证据位置、
困难、当前判断和下一步。Notion 不可用时先写本地日志，并记录阻塞原因，不得丢失过程信息。

## 完成定义

只有 `docs/aenv/ACTION_METRICS_AND_ACCEPTANCE.md` 中所有硬门禁均有证据且通过，三个 AEnv
均可远程创建实例，MCPMark 能逐题调用、验证和清理，才可以声明本任务完成。
