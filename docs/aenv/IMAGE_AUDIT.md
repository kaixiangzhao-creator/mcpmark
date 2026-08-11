# WebArena 三镜像 M2 取证报告

取证日期：2026-08-11

所有命令均针对本机已经加载的原始镜像。目录大小来自覆盖入口、只执行 `du/find` 的一次性
容器；没有启动 Web、数据库或后台服务。

## 1. 镜像标识与大小口径

| 环境 | Image ID | `docker inspect .Size` | `docker system df` size | 合并 rootfs `du` |
| --- | --- | ---: | ---: | ---: |
| Shopping | `ccff8c1772be` | 67,575,805,572 B | 约 141GB | 64,175,340 KiB |
| Shopping Admin | `993d1ee9c135` | 9,639,932,023 B | 约 19.6GB | 5,096,492 KiB |
| Postmill | `0a0c002b4dd0` | 53,435,001,827 B | 约 107GB | 47,305,152 KiB |

三个镜像均为 `linux/amd64`，入口为 `/docker-entrypoint.sh`，默认命令为：

```text
supervisord -n -j /supervisord.pid
```

`inspect .Size`、registry 压缩传输大小、本地累计 layer 和合并 rootfs 是不同口径。最终验收
必须同时报告，且 registry/inspect 与本地解包累计 layer 都必须小于 10GB。

## 2. Shopping

### 2.1 主要目录

| 路径 | 大小 |
| --- | ---: |
| `/var/www/magento2/pub/media` | 52,106,760 KiB |
| `/var/www/magento2/pub/media/catalog` | 52,106,344 KiB |
| `/var/lib/mysql` | 3,794,212 KiB |
| `/var/lib/mysql/magentodb` | 3,590,400 KiB |
| `/var/www/magento2/var` | 3,195,264 KiB |
| `/var/www/magento2/var/log` | 3,188,484 KiB |
| `/usr/share/java/elasticsearch/data` | 865,212 KiB |
| `/usr/share/java/elasticsearch/logs` | 1,334,732 KiB |
| `/var/www/magento2/vendor` | 592,812 KiB |

- `pub/media` 文件数：4,479,817。
- MySQL 文件数：1,068。
- 大部分镜像空间由商品媒体、数据库以及历史应用/Elasticsearch 日志构成。
- 448 万小文件意味着外置存储的 inode、首次导入和挂载性能必须单独验收，不能只看 GB。

### 2.2 原始服务

原始 supervisor 启动：cron、Elasticsearch、Mailcatcher、MariaDB、Nginx、PHP-FPM 和 Redis。

### 2.3 候选拆分

```text
PVC/baseline:
  /var/www/magento2/pub/media
  /var/lib/mysql
  /usr/share/java/elasticsearch/data

每题可写/重置:
  /var/www/magento2/var/session
  /var/www/magento2/var/cache
  media 可写 upper（如任务允许写媒体）

不迁移:
  /var/www/magento2/var/log/*
  /usr/share/java/elasticsearch/logs/*
```

## 3. Shopping Admin

### 3.1 主要目录

| 路径 | 大小 |
| --- | ---: |
| `/var/www/magento2/pub/media` | 86,420 KiB |
| `/var/lib/mysql` | 359,272 KiB |
| `/var/www/magento2/var` | 548,516 KiB |
| `/var/www/magento2/var/log` | 453,220 KiB |
| `/usr/share/java/elasticsearch/logs` | 1,333,472 KiB |
| `/usr/share/java/elasticsearch/data` | 988 KiB |
| `/var/www/magento2/vendor` | 679,760 KiB |

- `pub/media` 文件数：927。
- MySQL 文件数：1,071。
- 合并 rootfs 只有约 5.1GB，但原镜像 layer 累积较大，说明有重复写入/删除层。

### 3.2 已有 AEnv 1.0.1 的复核

已有官方 sandbox base 镜像：

```text
ai-01.my.harbor.shopeemobile.com/ai-infra/
shopping-admin-final-0719@sha256:344f1d805364e7ad8ea594084b5533bce87a90f068ed11cf2e73940460d9de71
```

该版本已留下真实远程实例成功记录，`docker inspect .Size` 约 2.74GB。但本机
`docker system df -v` 显示约 13GB，本次 history 发现：

- 一次递归权限/venv 构建 `RUN` layer 约 3.89GB；
- 完整复制 `/usr` 约 3.08GB；
- 完整复制 `/var/www` 约 1.48GB；
- 复制 MySQL 约 368MB；
- 官方 base 本身约 1.97GB 本地解包大小。

因此 1.0.1 是“官方入口和远程实例契约已验证”的参考实现，但不满足新的本地 `<10GB`
双门禁。新版本必须在 source stage 先删除日志/外置数据，使用 `COPY --chown`，并禁止后续
递归 `chown` 复制整个文件树。

## 4. Postmill

### 4.1 主要目录

| 路径 | 大小 |
| --- | ---: |
| `/var/www/html/public/submission_images` | 40,360,920 KiB |
| `/usr/local/pgsql/data` | 4,987,268 KiB |
| `/usr/local/pgsql/data/base` | 4,263,184 KiB |
| `/usr/local/pgsql/data/pg_wal` | 720,900 KiB |
| `/var/www/html/var` | 105,040 KiB |
| `/var/www/html/node_modules` | 170,636 KiB |
| `/var/www/html/vendor` | 122,476 KiB |

- `public` 文件数：32,519。
- `submission_images` 文件数：31,467。
- PostgreSQL 文件数：1,844。
- 原始 supervisor 只启动 Nginx、PostgreSQL 和 PHP-FPM。

### 4.2 候选拆分

```text
PVC/baseline:
  /var/www/html/public/submission_images
  /usr/local/pgsql/data

每题可写/重置:
  /var/www/html/var/cache
  /var/www/html/var/sessions
  数据库任务快照

runtime:
  Postmill 代码、vendor、node_modules、Nginx、PHP-FPM、PostgreSQL 二进制
```

## 5. 不能采用的瘦身方式

```dockerfile
FROM original-large-image
RUN rm -rf /large/data
```

该方式只生成 whiteout，新镜像仍保留原始大 layer。必须在多阶段 source 中裁剪后只复制需要
的文件到官方 sandbox base，或使用等价的全新 rootfs 构建。最终 runtime 不得继承原始大镜像
作为最终父层。

## 6. 下一步构建门禁

1. 三个 Dockerfile 的最终层必须为官方 `sts_ai_agent_sandbox/base:v0.1.2`。
2. source stage 先移除外置数据、历史日志、cache 和临时文件。
3. 所有大目录第一次复制时即设置最终 owner，禁止递归 chown 产生复制层。
4. 本地构建后同时检查 `docker image inspect`、`docker system df -v` 和运行时 `du`。
5. 本地挂载真实 baseline 后验证 Web/数据库，再上传 AEnv。
6. AEnv 必须真实创建远程实例；已有 Admin 1.0.1 只能作为入口契约参考，不能替代新版本验收。
