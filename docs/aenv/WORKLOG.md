# MCPMark WebArena AEnv 改造工作日志

Notion 同步页面：<https://app.notion.com/p/3b9af8dad1e481a7a609d710894eb967>

本日志只记录脱敏后的关键动作、困难、版本和证据位置。任何凭据不得写入本文件。

## 2026-08-11

### M0：执行与验收基线

- 克隆上游：`https://github.com/eval-sys/mcpmark.git`。
- 创建个人 fork：`https://github.com/kaixiangzhao-creator/mcpmark.git`。
- 工作分支：`aenv/webarena-external-state`。
- 新增 `AGENT.md` 和 `docs/aenv/ACTION_METRICS_AND_ACCEPTANCE.md`。
- Git commit：`7117062 docs(aenv): define execution and acceptance gates`。
- 分支已推送到个人 fork。

### M1：设计基线

- 将 `MCPMARK_EXTERNAL_DATA_RUNTIME_EXPLAINED.md` 原样加入 `docs/aenv/`。
- 将 `MCPMARK_EXTERNAL_STATE_VENV_DESIGN.md` 原样加入 `docs/aenv/`。
- 两份仓库副本均已通过 `cmp` 与原始文件进行字节级一致性检查。
- 创建并验证用户指定父页面下的 Notion 工作日志。

### 初始镜像观察

本机已经存在目标原始镜像：

| 环境 | 本地 tag | Docker 展开大小观察值 |
| --- | --- | ---: |
| Shopping | `shopping_final_0712:latest` | 约 141GB |
| Shopping Admin | `shopping_admin_final_0719:latest` | 约 19.6GB |
| Postmill | `postmill-populated-exposed-withimg:latest` | 约 107GB |

这些值不是最终基线。M2 将分别记录 image inspect size、history/layer、容器目录占用、
媒体与数据库内容大小，区分压缩归档大小、镜像虚拟大小和实际业务数据大小。

### 当前困难和风险

- 本机未安装 GitHub CLI；已使用 GitHub API 创建 fork，并使用 Git 直接推送，不影响版本迭代。
- 原始 Docker 展开大小高于此前“接近 50GB”的归档口径，必须防止用不同大小口径作错误比较。
- AEnv 外置数据、持久化挂载、实例日志和远程访问契约尚需从官方页面与 SDK 0.1.96 实际确认。
- 图片不能先删后测；第一阶段必须保留原始 baseline，并验证外置后的 URL、DOM 和 verifier 等价。

### 下一步

1. 获取并保存 AEnv 官方约束摘要，不复制任何凭据。
2. 安装/核对 `shopee-aenvironment==0.1.96`。
3. 对三镜像进行只读取证并形成 M2 报告。
4. 根据 AEnv 官方存储能力确定 baseline 的最终承载位置。

### M1 完成

- Git commit：`8af11d7 docs(aenv): add external-state and official AEnv baseline`。
- 已推送到个人 fork 工作分支。
- 已安装并核对 `shopee-aenvironment==0.1.96`，Build Commit 为 `f417ac9`。
- 官方 SDK 确认支持 Environment service、`service_url` 和可选 PVC；baseline 导入和快照仍待实测。

### M2 初步结论

- `docker image inspect .Size` 与 `docker system df -v` 的本地解包累计 layer 大小口径不同。
- 已有 Shopping Admin AEnv 1.0.1 的 inspect size 约 2.74GB，但本地 layer size 约 13GB。
- 约 3.89GB layer 来自构建中的递归 `chown`，需要以 `COPY --chown` 和预先裁剪替代。
- 为满足“不拉起 10GB 以上 Docker”，验收标准升级为 registry/inspect 和本地解包 layer 双门禁。

## 2026-08-12

### M3 Shopping Admin 本地 runtime

- `apply_patch` 权限故障已由用户调整执行配置后解除；临时文件创建、读取、删除均通过。
- 官方 AEnv 0.1.96 local builder 固定使用 `pull=true`，不会直接采用仅本机加载的 donor 镜像。
- 启动只监听 `127.0.0.1:5000` 的本机 registry，作为 donor 引用适配层；未修改官方 SDK。
- 导出 Shopping Admin pristine baseline：437MB、2088 文件，数据和 manifest 均位于 Git 仓库外。
- 使用 `aenv build --no-push` 构建 runtime 成功。
- 最终镜像 inspect size 为 1,654,501,329 bytes，本地累计 layer size 为 5.93GB。
- MariaDB、Elasticsearch、Nginx、PHP-FPM、Redis、Mailcatcher、AEnv 全部 RUNNING。
- 官方 health 与 AEnv health 均为 HTTP 200；`/admin` 与原镜像对照均为 302；样例媒体为 200。
- 真实 MCP 调用 `configure_public_url` 成功。
- 详细证据：`docs/aenv/M3_SHOPPING_ADMIN_LOCAL_VALIDATION.md`。
- 当前只完成本地验收，尚未上传 2.0.0，也未解决远程 PVC baseline 导入。
