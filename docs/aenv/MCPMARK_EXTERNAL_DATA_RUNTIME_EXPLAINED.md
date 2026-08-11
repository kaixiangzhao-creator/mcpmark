# MCPMark 镜像缩小后业务数据的存储与运行原理

## 1. 核心结论

镜像缩小不是把业务数据删除，也不是让 Python venv 重新生成几十 GB 数据，而是把数据从 Docker image layer 搬到独立存储，只保留一份。

```text
原方案
Docker image
├── 应用程序
├── PHP/Nginx/数据库程序
├── 数据库文件
├── 商品或帖子图片
├── 搜索索引
└── cache/log/session

外置方案
venv 控制程序
├── 选择 baseline
├── 创建数据库 COW clone
├── 生成 mount 参数
├── 启动或重置 Docker runtime
└── 任务结束后清理差异状态

精简 Docker runtime image
├── 官方 sandbox base
├── 应用程序
├── PHP/Nginx
├── 数据库/搜索服务程序
└── AEnv/健康入口

外部数据存储
├── 只读业务 baseline
├── 每任务数据库 clone
├── 每任务 cache/session/log
└── 每任务媒体 writable upper
```

Docker 镜像目标保持在 10 GB 以下；完整业务数据仍然真实存在，但不属于 Docker 镜像，不随每次容器启动重复下载和解压。

## 2. 四个容易混淆的对象

### 2.1 MCPMark venv

venv 是 Python 控制面，保存：

- MCPMark runner；
- Playwright 控制代码；
- verifier；
- 状态管理程序；
- snapshot driver；
- Docker/platform API 客户端。

venv 不保存：

- 40–52 GB 图片；
- MySQL/PostgreSQL data directory；
- Elasticsearch 索引；
- PHP/Nginx/MySQL/PostgreSQL 服务本身。

### 2.2 Runtime image

Runtime image 是小型 Docker 镜像，保存应用程序和固定运行依赖。

建议目标：

| 环境 | 当前 AEnv 镜像 | 精简目标 |
|---|---:|---:|
| Shopping Admin | 2.74 GB | ≤2.5 GB |
| Shopping | 44.63 GB | ≤7 GB |
| Postmill | 45.66 GB | ≤4 GB |

### 2.3 Runtime container

Runtime container 由 Docker 创建。venv 中的程序可以调用 Docker CLI/API 发起创建，但真正提供进程、文件系统和网络隔离的是 Docker。

容器启动时将外部状态挂载到应用原路径，因此应用不需要知道数据已经外置。

### 2.4 External baseline

Baseline 是不可变的初始业务数据：

- Shopping 商品、评论、价格、媒体、初始数据库；
- Shopping Admin 商品、订单、客户、规则、报表初始数据；
- Postmill 历史用户、论坛、帖子、评论、投票和帖子图片。

Baseline 存储一次，多个任务共享其只读部分；可变数据库通过写时复制创建任务分支。

## 3. 数据实际存在哪里

### 3.1 单机 Docker

推荐放在 Docker root 之外的独立数据盘：

```text
/srv/mcpmark-state/
├── baselines/
│   ├── shopping/0712/
│   │   ├── manifest.json
│   │   ├── mysql/
│   │   ├── media/
│   │   └── elasticsearch/
│   ├── shopping_admin/0719/
│   │   ├── manifest.json
│   │   ├── mysql/
│   │   ├── media/
│   │   └── elasticsearch/
│   └── reddit/postmill-withimg/
│       ├── manifest.json
│       ├── postgres/
│       └── submission_images/
├── slots/
│   ├── shopping-1/
│   ├── shopping-admin-1/
│   └── postmill-1/
└── runs/
    └── <run-id>/
```

该目录可以位于：

- 本机大容量 SSD；
- XFS/Btrfs/ZFS 数据盘；
- NFS/CephFS 等共享文件系统；
- 支持快照的块存储。

它不位于 runtime image，也不应位于容器匿名 writable layer。

### 3.2 Kubernetes/AEnv

对应形式：

| 数据 | 推荐存储 |
|---|---|
| 大量只读图片 | ReadOnlyMany PVC、CephFS、对象存储/CDN |
| MySQL/PostgreSQL baseline | CSI VolumeSnapshot、数据库快照服务 |
| 每任务 DB | 从 baseline 创建 PVC clone |
| Session/cache/log | EmptyDir、临时 PVC |
| ES baseline | Elasticsearch snapshot repository |

如果 AEnv 不支持 mount、PVC clone 或 snapshot，venv 无法凭空提供这些数据；需要平台增加存储能力，或者连接外部数据服务。

## 4. 三个环境的具体数据

### 4.1 Shopping

| 数据 | 当前逻辑大小 | 外置形式 |
|---|---:|---|
| `pub/media` | 约 52.11 GB | 共享只读/COW 文件树 |
| MySQL | 约 3.79 GB | 物理 baseline + 每任务 clone |
| Elasticsearch | 约 2.67 GB | snapshot + 每任务恢复 |
| Magento log | 约 3.19 GB | 不进 baseline，每任务空目录 |
| Redis/Session/cache | 可变 | 每任务空状态 |

商品媒体不能简单删除，因为图片 404 和布局变化可能影响 Playwright/视觉模型。第一阶段应保留原始图片，只改变存储位置。

### 4.2 Shopping Admin

| 数据 | 当前逻辑大小 | 外置形式 |
|---|---:|---|
| MySQL | 约 0.36 GB | baseline + clone |
| pub/media | 约 0.09 GB | 只读/COW |
| var/cache/log/session | 约 0.55 GB | 每任务清空 |

后台任务会新增客户、客户组等数据，因此不能只清浏览器 Cookie，必须回滚 MySQL。

### 4.3 Postmill

| 数据 | 当前逻辑大小 | 外置形式 |
|---|---:|---|
| submission_images | 约 40.36 GB，31,467 文件 | 共享只读/COW |
| PostgreSQL | 约 4.99 GB | baseline + clone |
| Symfony cache/log/session | 约 0.11 GB | 每任务空目录 |

电影论坛任务会统计图片/海报帖子，因此图片路径、HTTP 200、MIME 和 DOM 中的图片元素必须保留。

## 5. 图片如何继续支撑 Web

### 5.1 Shopping 页面请求

```text
Playwright GET /product.html
        │
        ▼
Nginx → PHP-FPM → Magento
        │
        ├── 从挂载的 MySQL clone 查询商品、价格、评论
        └── 生成含 /media/catalog/product/x.jpg 的 HTML
                               │
                               ▼
Playwright GET /media/catalog/product/x.jpg
                               │
                               ▼
Nginx 从外部挂载的 media 文件树读取图片
```

对 Magento/Nginx 而言，文件仍位于原路径；它不关心该路径来自 image layer 还是 bind mount。

### 5.2 Postmill 页面请求

```text
Playwright GET /f/movies
        │
        ▼
Postmill 从 PostgreSQL clone 查询帖子、票数、图片路径
        │
        ▼
生成帖子 HTML 和 <img src="/submission_images/...">
        │
        ▼
Nginx 从外部 submission_images 挂载目录读取原图
```

只要数据库引用、文件路径、权限、MIME 和 HTTP 行为相同，页面生成方式不变。

## 6. Docker 挂载示例

### 6.1 Postmill 示例

以下示例用于说明 mount 关系，具体 UID、端口和启动参数以最终 runtime image 为准：

```bash
docker run -d \
  --name mcpmark-postmill-slot-1 \
  -p 127.0.0.1:19999:8080 \
  --mount type=bind,src=/srv/mcpmark-state/slots/postmill-1/postgres,dst=/usr/local/pgsql/data \
  --mount type=bind,readonly,src=/srv/mcpmark-state/baselines/reddit/postmill-withimg/submission_images,dst=/var/www/html/public/submission_images \
  --mount type=bind,src=/srv/mcpmark-state/slots/postmill-1/cache,dst=/var/www/html/var/cache \
  --mount type=bind,src=/srv/mcpmark-state/slots/postmill-1/logs,dst=/var/www/html/var/log \
  mcpmark/postmill-runtime:withimg-v1
```

这条命令拉取/启动的是目标 ≤4 GB 的 runtime image。40.36 GB 图片由宿主机直接挂载，不进入 Docker pull。

### 6.2 Shopping 示例

Magento media 内部可能同时包含原图和生成 cache。最稳妥的是给每个 slot 创建文件系统级 COW media clone，再挂载整个 media：

```bash
docker run -d \
  --name mcpmark-shopping-slot-1 \
  -p 127.0.0.1:17770:8080 \
  --mount type=bind,src=/srv/mcpmark-state/slots/shopping-1/mysql,dst=/var/lib/mysql \
  --mount type=bind,src=/srv/mcpmark-state/slots/shopping-1/media,dst=/var/www/magento2/pub/media \
  --mount type=bind,src=/srv/mcpmark-state/slots/shopping-1/session,dst=/var/www/magento2/var/session \
  --mount type=bind,src=/srv/mcpmark-state/slots/shopping-1/cache,dst=/var/www/magento2/var/cache \
  --mount type=bind,src=/srv/mcpmark-state/slots/shopping-1/logs,dst=/var/www/magento2/var/log \
  mcpmark/shopping-runtime:0712-v1
```

不要把只读 `pub/media` 父目录直接盖住一个需要写入的 cache 子目录，除非使用嵌套 mount 或应用已把写路径拆开。

## 7. Baseline Manifest 示例

```json
{
  "schema_version": 1,
  "profile": "shopping/0712",
  "source_image": "shopping_final_0712@sha256:<source-digest>",
  "database": {
    "engine": "mariadb",
    "version": "<exact-version>",
    "snapshot_format": "cold-directory",
    "logical_size_bytes": 3794212000,
    "path": "mysql"
  },
  "media": {
    "path": "media",
    "mode": "cow",
    "logical_size_bytes": 52106760000,
    "tree_digest": "sha256:<tree-manifest-digest>"
  },
  "search": {
    "engine": "elasticsearch",
    "version": "<exact-version>",
    "snapshot": "elasticsearch"
  }
}
```

Manifest 用于防止：

- baseline 与 runtime 版本不匹配；
- 错误使用同名 tag；
- 图片目录缺失；
- 数据库快照损坏；
- 不同任务误用不同初始状态。

## 8. venv 控制代码示例

下面是结构示例，不是可以直接用于生产的完整实现：

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess
import uuid


@dataclass
class PreparedState:
    run_id: str
    database: Path
    media: Path
    cache: Path
    session: Path
    logs: Path


class WebArenaStateController:
    def __init__(self, state_root: Path, snapshot_driver):
        self.state_root = state_root.resolve()
        self.snapshot_driver = snapshot_driver

    def prepare_shopping(self) -> PreparedState:
        run_id = uuid.uuid4().hex
        run_root = self.state_root / "runs" / run_id
        run_root.mkdir(parents=True, exist_ok=False)

        database = self.snapshot_driver.clone(
            self.state_root / "baselines/shopping/0712/mysql",
            run_root / "mysql",
        )
        media = self.snapshot_driver.clone(
            self.state_root / "baselines/shopping/0712/media",
            run_root / "media",
        )

        cache = run_root / "cache"
        session = run_root / "session"
        logs = run_root / "logs"
        for path in (cache, session, logs):
            path.mkdir()

        return PreparedState(
            run_id=run_id,
            database=database,
            media=media,
            cache=cache,
            session=session,
            logs=logs,
        )

    def start_runtime(self, state: PreparedState) -> str:
        name = f"mcpmark-shopping-{state.run_id[:12]}"
        command = [
            "docker", "run", "-d",
            "--name", name,
            "--mount", f"type=bind,src={state.database},dst=/var/lib/mysql",
            "--mount", f"type=bind,src={state.media},dst=/var/www/magento2/pub/media",
            "--mount", f"type=bind,src={state.cache},dst=/var/www/magento2/var/cache",
            "--mount", f"type=bind,src={state.session},dst=/var/www/magento2/var/session",
            "mcpmark/shopping-runtime:0712-v1",
        ]
        subprocess.run(command, check=True)
        return name
```

生产实现还必须增加：

- baseline manifest 校验；
- 文件锁；
- 镜像大小硬门禁；
- mount 路径白名单；
- 失败回滚；
- cleanup token；
- 超时和日志；
- orphan GC；
- 并行隔离测试。

## 9. 镜像大小硬门禁示例

如果不能容忍 Docker 拉取 10 GB 以上镜像，应在 venv 控制层启动前检查：

```python
import json
import subprocess

MAX_IMAGE_BYTES = 10_000_000_000


def assert_image_size(image: str) -> None:
    result = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .Size}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    size = json.loads(result.stdout)
    if size > MAX_IMAGE_BYTES:
        raise RuntimeError(
            f"Refusing to start {image}: {size} bytes exceeds 10 GB"
        )
```

远端 Harbor 还应在部署前检查 manifest/config size。镜像门禁不统计外部 PVC、共享图片或数据库服务，因为它们不属于 Docker image pull。

## 10. 不删除常驻容器时如何重置

常驻容器应属于一个 slot：

```text
mcpmark-shopping-slot-1
└── /state（容器创建时固定挂载）
    ├── database
    ├── media
    ├── cache
    ├── session
    └── logs
```

新任务开始：

1. 锁定 slot，停止接收请求。
2. 停止 Nginx/PHP。
3. 停止 MySQL/PG、Redis、Elasticsearch。
4. 回滚或替换 slot 的数据库 snapshot。
5. 恢复 media COW clone，或清空 media upper。
6. 清空 cache/session/log。
7. 恢复搜索索引。
8. 启动数据库、Redis、Elasticsearch、PHP、Nginx。
9. 等待业务 readiness。
10. 创建全新 Playwright Browser Context。
11. 释放 slot 给任务。

正常任务之间不删除 slot 容器。若 reset 失败、进程泄漏或健康检查失败，才销毁并从小型 runtime image 重建 slot。

Docker bind mount 不能在容器创建后随意更换，因此常驻 slot 应固定挂载一个父目录；状态管理器在该父目录内执行 snapshot rollback/原子目录切换。

## 11. Playwright 为什么仍能正常评测

Playwright 只看到 URL、HTML、CSS、JavaScript、图片和 API 响应，不知道文件来自：

- Docker image layer；
- bind mount；
- PVC；
- 对象存储；
- 独立数据库服务。

只要以下契约不变，外置本身不应改变结果：

- 数据库初始值；
- 搜索索引、数量、排序和分页；
- URL/Cookie domain；
- 图片 URL、状态、MIME 和尺寸；
- DOM 和关键 selector；
- 服务版本、时区和 locale；
- 每任务全新 Browser Context；
- readiness 等待真实业务就绪。

风险来自不完整重置或存储行为变化，而不是“不重新拉取”：

- 旧 Cookie/LocalStorage；
- Redis 购物车；
- DB 中残留客户/帖子；
- ES 仍是旧索引；
- PHP OPcache/连接未重启；
- 图片从远端加载过慢；
- 占位图改变视觉和布局。

第一阶段应使用原始图片的本机/同节点只读挂载，不应直接改占位图。

## 12. 空间节省到底在哪里

原方案：

```text
Shopping AEnv image  44.63 GB
Postmill AEnv image  45.66 GB
每个冷节点重新拉取和解压
大目录 chown 还可能制造重复 layer
```

外置方案：

```text
Shopping runtime image   ≤7 GB
Postmill runtime image   ≤4 GB
Admin runtime image      ≤2.5 GB

共享 Shopping baseline  约 59 GB，只存一次
共享 Postmill baseline  约 45 GB，只存一次
每任务物理新增          通常几十到几百 MB
```

因此节省的是：

- Docker registry 存储；
- Docker pull 流量；
- 镜像解压时间；
- 每任务完整数据复制；
- OverlayFS 重复层；
- 并行任务的增量空间。

业务数据总量没有消失。如果要求整台机器包含业务数据也小于 10 GB，则必须把 baseline 放到远程共享存储或服务；完整 WebArena 数据仍需在某处保存。

## 13. 推荐实施顺序

1. 固定三个源镜像 digest。
2. 导出并校验 baseline。
3. 先外置 log/cache/session。
4. 实现 DB snapshot clone。
5. 外置原始图片，不使用占位图。
6. 构建小于 10 GB 的 runtime image。
7. 加入镜像大小硬门禁。
8. 修改 MCPMark StateManager。
9. 对原镜像和外置方案做完整等价回归。
10. 启用常驻 slot 容器池。
11. 最后评估占位图或远程对象存储优化。

## 14. 验收检查

Shopping：

- 商品搜索数量、排序、分页一致；
- SKU、价格、评论一致；
- 图片全部 HTTP 200；
- 修改购物车后 reset 能恢复为空。

Shopping Admin：

- 初始客户/客户组/订单计数一致；
- 新建客户/客户组成功；
- reset 后新增数据消失。

Postmill：

- 历史帖子、票数、评论一致；
- 电影论坛图片帖子数量一致；
- 新建账号/论坛/帖子/投票成功；
- reset 后新增数据消失。

通用：

- 同一任务连续运行两次初始结果一致；
- 并行 slot 互不影响；
- runtime image 均小于 10 GB；
- warm restart 不重新复制 40–52 GB 图片；
- reset 失败会隔离 slot，不继续参与评测。

## 15. 一句话总结

大数据以“外部只读 baseline + 每任务 COW 状态”的形式存放在宿主机数据盘、共享 PVC、快照存储或对象存储；venv 负责选择、克隆、挂载和清理；Docker 只运行小于 10 GB 的应用 runtime；Playwright 仍通过相同 Web 路径访问相同数据库和图片。
