# MCPMark WebArena：从 Docker Save Tar 重构为本机进程环境的交接手册

## 1. 任务目标与输入

接手者只应假设拥有：

1. MCPMark 官方仓库 `https://github.com/eval-sys/mcpmark.git`；
2. 三个由 `docker save` 产生的原始归档：
   - `shopping_final_0712.tar`；
   - `shopping_admin_final_0719.tar`；
   - `postmill-populated-exposed-withimg.tar`。

最终运行路径不得依赖 Docker daemon、已 load 的镜像、AEnv、Harbor、Kubernetes 或
PVC。Tar 只在首次物化 runtime 和 pristine baseline 时使用；正式评测直接启动本机进程。

本手册是一份完整交接文件，不依赖本仓库 `aenv/`、`docs/aenv/` 或当前失败分支中的实现。

## 2. 唯一代码基线

不要从当前工作分支继续修改，也不要 cherry-pick 任何 AEnv/external-state 提交。以官方
默认分支为唯一基线：

```bash
git clone https://github.com/eval-sys/mcpmark.git
cd mcpmark
git fetch origin --prune
git switch --create feat/webarena-host-process origin/main
git rev-parse HEAD
```

本手册编写时官方 `main` 为：

```text
cd45b7f57923b9b3985467f5139927575f83141c
```

若官方 HEAD 已更新，应记录新 commit，并重新检查本手册列出的文件位置；不要机械套用旧
行号。开始编码前确认工作树中不存在以下失败路线的文件或配置：

- `aenv/`；
- `src/mcp_services/playwright_webarena/state/aenv_backend.py`；
- `external-state`、`aenv_pvc_name_template` 等非官方配置；
- 任何 `localhost:5000` donor registry 引用。

## 3. 不可改变的边界

只修改 `playwright_webarena` 的环境提供方式，不改变：

- task 数据、instruction、`meta.json` 和 verifier；
- 其他 MCP service 的 state/task/login manager；
- agent、模型调用、结果目录和聚合格式；
- `WEBARENA_BASE_URL` 的 verifier 契约；
- `BaseStateManager` 的公共生命周期，除非是所有 service 都需要的独立 bugfix。

官方代码中需要保留的关键接口是：

```text
PlaywrightStateManager.set_up(task)
  → task.base_url
  → agent 每题刷新 service config
  → verifier 读取 WEBARENA_BASE_URL
PlaywrightStateManager.clean_up(task)
```

不要把宿主机路径、固定端口或数据库凭据写入 task/verifier。

## 4. 为什么不能只创建 Python venv

venv 只能安装 Python 包。三个网站还依赖 PHP-FPM、PHP extensions、Nginx、MySQL 或
PostgreSQL、Redis、Elasticsearch/JDK、动态链接器及系统共享库。它们必须作为固定版本的
本机 runtime bundle 存在。

普通 `fork()` 也不能重置环境：fork 的 Copy-on-Write 只作用于进程内存，父子进程仍写同一
数据库、索引和媒体目录。子进程退出不会撤销 WAL、binlog、translog 或图片修改。因此：

```text
venv（控制层）
  + 固定本机 runtime（程序层）
  + 每题 reflink/COW 状态（数据层）
  + 每题进程组和端口（生命周期层）
  = 完整无容器环境
```

## 5. 无 Docker 解包 Tar

### 5.1 工具前提

目标 Linux 主机需要预装或由基础设施提供：

- `skopeo`：读取 `docker-archive` 并转换为 OCI layout；
- `umoci`：按 layer 顺序和 whiteout 规则生成合并 rootfs；
- `jq`、`sha256sum`、`readelf`、`file`、`tar`；
- 支持 `cp --reflink=always` 的 GNU coreutils 和文件系统；
- `flock`；
- cgroup v2/systemd user unit，或至少 POSIX process group；
- Python 项目要求的 venv/Playwright 依赖。

这些是宿主工具，不是容器运行时。不要通过 `tar -xf` 直接拼接 layer：Docker save tar 是
多层差异归档，直接解压会错误处理文件覆盖和 whiteout 删除标记。

### 5.2 输入目录约定

所有大文件必须放在 Git 仓库外：

```text
WEBARENA_HOST_ROOT/
  archives/             # 用户提供的三个 tar，只读
  oci/                  # 中间 OCI layout
  unpacked/             # umoci 合并 rootfs，仅用于取证/物化
  runtimes/             # 只读固定 runtime bundle
  baselines/            # 只读 pristine 数据
  runs/                 # 每题临时状态和配置
  manifests/            # 校验值、版本和取证报告
  locks/                 # 端口、物化和清理锁
```

不要默认 `/home/...`；通过 `WEBARENA_HOST_ROOT` 显式传入绝对路径。

### 5.3 转换与合并

为每个 tar 执行等价流程：

```bash
skopeo inspect docker-archive:/absolute/path/image.tar
skopeo copy \
  docker-archive:/absolute/path/image.tar \
  oci:/absolute/path/WEBARENA_HOST_ROOT/oci/shopping:source
umoci unpack --rootless \
  --image /absolute/path/WEBARENA_HOST_ROOT/oci/shopping:source \
  /absolute/path/WEBARENA_HOST_ROOT/unpacked/shopping
```

实际脚本不得覆盖已存在目录。先写入同一文件系统下的临时目录，完成校验后原子 rename。
保存：tar SHA-256、OCI digest、architecture、image config、rootfs 文件数和字节数。

### 5.4 必须新增的物化命令

新增独立 CLI，建议：

```text
python -m src.mcp_services.playwright_webarena.host_runtime.materialize \
  --category shopping \
  --archive /data/archives/shopping_final_0712.tar \
  --root /data/webarena-host
```

它必须：

1. 验证 tar、架构和工具版本；
2. 调用 skopeo/umoci，不调用 `docker`；
3. 生成 runtime 与 baseline；
4. 清空历史 log、cache、session 和 PID 文件；
5. 生成 JSON manifest；
6. 将 runtime/baseline 设为当前评测用户不可写；
7. 重复执行相同输入时幂等；输入 digest 不同则拒绝覆盖已有版本。

## 6. 从 rootfs 划分 runtime 与 baseline

下列路径是最低已知边界，必须由脚本在实际 tar 中验证，缺失时 fail closed。

### Shopping 与 Shopping Admin

有状态 baseline：

```text
/var/lib/mysql                         → baselines/<category>/mysql
/usr/share/java/elasticsearch/data    → baselines/<category>/elasticsearch
/var/www/magento2/pub/media           → baselines/<category>/media
```

runtime 至少包括 Magento 程序、PHP/扩展、Nginx、MySQL server、Redis、Elasticsearch/JDK
以及所需库和配置。不要把上述三个 baseline 目录、历史 log/cache/session 复制进 runtime。

### Postmill/Reddit

有状态 baseline：

```text
/usr/local/pgsql/data                         → baselines/reddit/postgres
/var/www/html/public/submission_images        → baselines/reddit/submission_images
```

runtime 至少包括 Postmill 程序、PHP/扩展、Nginx、PostgreSQL server 及所需库和配置。

### Runtime 物化原则

不要把整个 rootfs 永久复制为 runtime。先用 `file`、`readelf -l/-d` 和递归依赖扫描生成
程序依赖清单，再复制明确的应用/二进制/库目录。manifest 必须列出：

- 源 tar SHA-256 和 OCI digest；
- OS、architecture、ELF interpreter；
- PHP、Nginx、数据库、Redis、Elasticsearch/JDK 版本；
- 应用代码和 runtime 文件的校验摘要；
- baseline 文件数、字节数及 manifest SHA-256；
- 明确排除的数据、日志、缓存和 session 路径。

不得把几十 GB 图片藏入 venv、wheel、Git LFS 或新的 runtime bundle。

## 7. Alpine/musl 与宿主兼容

原归档可能包含 Alpine/musl 二进制，而宿主可能是 Debian/glibc。不要直接调用并假设可用。
物化时对每个入口程序记录：

```bash
file PROGRAM
readelf -l PROGRAM
readelf -d PROGRAM
```

运行策略按优先级选择，并写入 manifest：

1. 直接使用 tar 内自带的绝对 ELF loader 和对应 library path 的 wrapper；
2. 对 runtime 副本使用可审计的 `patchelf` 修正 interpreter/RPATH；
3. 构建与宿主兼容、版本一致的原生 runtime bundle。

禁止修改 pristine unpacked rootfs。每个 wrapper 必须使用绝对路径，清理
`LD_PRELOAD/PYTHONPATH/PYTHONHOME` 等外部污染变量。若 PHP extension、数据库 data format
或 Elasticsearch/JDK 不兼容，物化必须失败，不能自动升级到“差不多”的版本。

## 8. 每题目录与状态隔离

每题生成不可预测且唯一的 `run_id`：

```text
runs/<category>/<run_id>/
  state/        # DB/index/media COW
  app/          # 可写 cache/session/generated/pub static
  config/       # 本题服务配置
  logs/         # 所有 stdout/stderr 和服务日志
  pids/
  sockets/
  tmp/
  browser/
  run.json      # ownership token、端口、状态与版本
```

创建过程必须为：临时目录 → 完整准备 → 写 manifest → 原子 rename。`run.json` 至少保存
category、run ID、随机 cleanup token、baseline/runtime digest、创建时间、进程组/cgroup、
端口和状态机阶段。

### 状态复制

- MySQL/PostgreSQL/Elasticsearch：`cp -a --reflink=always` 到本题 `state/`；
- 默认历史媒体：由另一个只读 OS 账号拥有，任务账号只能读；
- 涉及上传/改图：把媒体 reflink 到本题 `state/`；
- Magento/Postmill 的 cache、session、generated、临时上传目录始终每题独立；
- Playwright browser profile 每题独立，结束后删除。

必须先做真实 reflink 探针。任何 `--reflink=always` 失败都终止 setup；禁止静默退化为
44～55GB 普通复制。

## 9. 每题进程编排

所有服务必须前台运行，禁止自行 daemonize。建议命令形态：

```text
mysqld/mariadbd       --datadir RUN/state/mysql --socket RUN/sockets/mysql.sock ...
postgres              -D RUN/state/postgres -k RUN/sockets ...
elasticsearch         使用 RUN/state/elasticsearch、独立 HTTP/transport 端口
redis-server          --daemonize no、独立端口和目录
php-fpm               -F，使用本题 prefix/socket/config
nginx                 daemon off，使用本题 config/pid/log/port
MCP/Playwright        使用项目 venv、当前 base URL 和本题 browser profile
```

Magento/Postmill 应用树也要为每题提供可写 runtime view，使 cache/session/generated 不写入
共享 runtime。不要创建全局 `/var/www`、`/var/lib/mysql` 或固定 `/run/*.pid` 依赖。

每题使用一个 systemd transient unit/cgroup；无法使用时，由一个 `start_new_session=True` 的
supervisor 进程创建 POSIX session，其他服务由它派生并继承同一生命周期。只记录单个 PID
不够，因为 Nginx、PHP-FPM 和数据库会产生子进程。

退出顺序：停止接收 Web 请求 → 正常关闭 PHP/Nginx → 正常关闭 DB/ES/Redis → 等待 → TERM
整个 cgroup/process group → 超时后 KILL → 确认无进程和端口 → 保存日志摘要 → 删除状态。

## 10. 端口与配置

不要复用官方固定的 7770/7780/9999 作为内部唯一值。每题至少动态分配：

- Web；
- MySQL 或 PostgreSQL；
- Redis；
- Elasticsearch HTTP 与 transport；
- 必要的 MCP/health 端口。

端口分配需要跨进程 file lock，并把端口写入 `run.json`。仅执行一次 `bind(0)` 后关闭 socket
存在竞争；应在锁内预留端口并尽可能到服务启动前保持 reservation。

所有配置从模板渲染到本题 `config/`。不得用字符串替换修改共享配置。Magento setup 后使用
tar 中已有应用配置读取数据库连接，并把 secure/unsecure base URL 更新为本题 Web URL，
随后 flush cache。凭据从物化后的受限配置读取，不写入 Git、日志或文档。

## 11. MCPMark 官方代码改动清单

### 11.1 新增文件

建议只在以下新目录实现：

```text
src/mcp_services/playwright_webarena/host_runtime/
  __init__.py
  models.py
  profiles.py
  archive.py
  materialize.py
  snapshot.py
  ports.py
  process_group.py
  config_renderer.py
  supervisor.py
  backend.py
  templates/
    shopping/
    shopping_admin/
    reddit/
```

职责必须分开：archive/materialize 只负责一次性 tar 物化；backend/supervisor 只负责逐题
运行；snapshot 只管理有 ownership token 的状态目录；ports 只分配/释放端口。

### 11.2 重写 `playwright_state_manager.py`

基于官方文件重写 Docker 部分，保留 `BaseStateManager` 接口：

```text
_create_initial_state(task)
  → HostProcessBackend.prepare_and_start(category)
  → readiness
  → InitialStateInfo(run_id, entry_url, metadata)
_store_initial_state_info(...)
  → task.base_url
  → task.host_runtime_metadata
_cleanup_task_initial_state(task)
  → 按 token 停进程并删除本题状态
get_service_config_for_agent()
  → environment=webarena-host-process
  → 当前动态 base_url
```

不要继续设置 `task.docker_container_name` 或返回 `docker` metadata。官方 tree 中这些字段只由
旧 state manager 自己设置，没有 task/verifier 依赖；真正公共契约是 `task.base_url`。

### 11.3 修改 `src/services.py`

只修改 `SERVICES["playwright_webarena"]`，增加并映射：

```text
WEBARENA_HOST_ROOT
WEBARENA_RUNTIME_MANIFEST_ROOT
WEBARENA_MEDIA_MODE=readonly|cow
WEBARENA_RESET_TIMEOUT
WEBARENA_KEEP_FAILED_STATE
WEBARENA_PROCESS_ISOLATION=systemd|cgroup|process-group
```

删除该 service 的 Docker image/container/tar 配置概念。不要改变其他 service schema。

### 11.4 修改 login helper

只更新 Docker 描述，并保证每题使用独立 browser state/profile。不要改变认证语义或其他
Playwright service。

### 11.5 修复 evaluator cleanup

官方 `MCPEvaluator._run_single_task` 只在正常完成 verification 后清理；agent 或 verifier 抛
异常时会遗留宿主进程。必须把 setup 后的 Execute、Verify 和结果构造放入 `try/finally`，
在 finally 中调用 `state_manager.clean_up(task)`。setup 内部部分启动失败也必须由 backend 自己
回滚。此改动应保持其他 service 的既有行为，并新增全局回归测试。

### 11.6 不应修改

- `tasks/playwright_webarena/**`；
- verifier 的默认 URL/业务规则；
- `PlaywrightTaskManager` 对 `task.base_url` 和 `WEBARENA_BASE_URL` 的现有注入；
- results reporter、aggregator 和其他 MCP service。

## 12. 运行前检查和 CLI

新增两个明确命令，不在评测时隐式做重型物化：

```bash
# 一次性物化
python -m src.mcp_services.playwright_webarena.host_runtime.materialize \
  --all \
  --shopping-tar /data/shopping_final_0712.tar \
  --shopping-admin-tar /data/shopping_admin_final_0719.tar \
  --reddit-tar /data/postmill-populated-exposed-withimg.tar \
  --root /data/webarena-host

# 无写入预检
python -m src.mcp_services.playwright_webarena.host_runtime.materialize \
  doctor --root /data/webarena-host
```

`doctor` 必须检查 manifest/digest、runtime 可执行性、reflink、目录权限、进程隔离能力、可用
内存、端口锁和 baseline 必需路径，且不得启动评测或修改 baseline。

## 13. 测试计划

### 单元测试

新增 `tests/playwright_webarena/host_runtime/`，覆盖：

- tar 类型、architecture、digest 和缺失路径拒绝；
- whiteout 后 rootfs 取值（使用极小 fixture，不提交真实 tar）；
- category/profile 映射；
- reflink 不支持时 fail closed；
- run ID、原子创建和重复 ID 拒绝；
- cleanup token 不匹配时拒绝删除；
- 端口并发分配；
- 配置模板无固定全局路径/端口；
- process group 的正常、TERM、KILL 和 orphan cleanup；
- setup 任一步失败时回滚；
- agent/verifier 抛异常时 evaluator 仍清理；
- `task.base_url` 和 agent service config 使用当前任务 URL。

### 真实验收顺序

1. Postmill 单题串行；
2. Postmill 第一槽写 marker，第二槽确认消失；
3. Shopping Admin 单题和双槽；
4. Shopping 单题和双槽；
5. 每 category 运行至少一道官方标准任务；
6. 同 category 两题并行；
7. 跨 category 并行；
8. SIGINT、agent exception、verifier timeout、数据库启动失败等故障注入。

业务等价检查至少包括：

- Web 状态码、关键 DOM/可访问性语义；
- 数据库 schema 和代表性记录数；
- Elasticsearch/PostgreSQL 查询；
- 登录、cookie/session 和上传/修改；
- 代表图片 URL、字节数和 SHA-256；
- 官方 verifier 输出；
- 第二题没有第一题的数据库、索引、session、cache 和媒体修改。

## 14. 硬性验收标准

只有以下条件全部通过才能宣布完成：

1. 物化和评测命令中没有 `docker`、AEnv、Harbor、Kubernetes/PVC 调用；
2. 新机器仅凭官方 MCPMark、三个 tar 和列明的宿主工具可重建；
3. runtime/baseline manifest 能从 tar digest 重复生成；
4. 三个环境都能完成官方任务、Playwright MCP 和 verifier；
5. 双槽 marker 测试证明逐题 pristine；
6. 两题并行时进程、端口、DB、index、media、cache、session 和 browser profile 隔离；
7. cleanup 后无子进程、监听端口和可写 run 目录；
8. baseline/runtime 对评测账号只读，所有服务使用低权限账号；
9. 评测账号不能读取 SSH、GitHub、Compass、云凭据和其他用户目录；
10. 相关单元/集成测试通过，其他 MCP service 回归测试无变化；
11. Git 中不包含 tar、rootfs、runtime、baseline、数据库、图片或有效凭据。

## 15. 安全与失败策略

完全移除容器意味着失去 mount/PID/network namespace。必须使用专用低权限 OS 用户、受限
目录权限、cgroup CPU/内存/PID 限额、ulimit 和网络出口策略。模型可操作的浏览器/MCP 进程
不得继承开发者 HOME、SSH agent、Git credential 或云凭据。

以下情况必须 fail closed，不允许“先运行再说”：

- tar digest/architecture 不匹配；
- runtime ABI 或数据库 data format 不兼容；
- baseline 可被任务账号修改；
- reflink 不可用；
- 无法建立进程组/cgroup；
- 固定端口或全局 PID/socket 冲突；
- cleanup token/受管路径校验失败；
- doctor 未通过。

## 16. Git 交付要求

建议分为独立提交：

1. `docs: add tar-to-host-process design and acceptance`；
2. `feat: add rootless WebArena archive materializer`；
3. `feat: add host-process runtime backend`；
4. `fix: guarantee evaluator cleanup on exceptions`；
5. `test: validate host runtime isolation and reset`；
6. `docs: record three-environment acceptance evidence`。

每次提交前执行相关测试、`git diff --check` 和 secret scan。不要改写官方基线历史，也不要
把失败的 AEnv 分支合并到新分支。

## 17. 接手者第一批动作

接手后按顺序执行：

1. 从官方 `origin/main` 新建干净分支并记录 commit；
2. 检查三个 tar 的 SHA-256、架构、tag 和 Docker archive 格式；
3. 实现无 Docker 的 archive→OCI→rootfs 最小 materializer；
4. 只读盘点三个 rootfs 的入口程序、ABI、服务版本和必需路径；
5. 验证目标数据盘 reflink 与权限模型；
6. 先实现 Postmill 串行 PoC；
7. 完成双槽 marker、真实 verifier 和异常清理后再进入 Shopping Admin；
8. 最后处理 55GB、约 448 万媒体文件的 Shopping，并进行并行测试。

不要一开始重写全部 state manager，也不要先复制数十 GB 数据。每个阶段先留下可重复证据，
未通过硬门禁时不得进入下一环境。
