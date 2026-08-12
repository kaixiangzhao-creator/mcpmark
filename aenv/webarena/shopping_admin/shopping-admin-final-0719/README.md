# Shopping Admin AEnv runtime

This project was created with the official `shopee-aenvironment==0.1.96`
`sweb-sandbox` scaffold and then adapted to WebArena.

The image contains the application and service binaries. It does not contain
the mutable MySQL, media, or Elasticsearch baseline. At runtime `/aenv-data`
must contain:

```text
/aenv-data/mysql
/aenv-data/media
/aenv-data/elasticsearch
```

The Dockerfile's final stage is the official
`harbor.shopeemobile.com/sts_ai_agent_sandbox/base:v0.1.2` image. It preserves
the official base entrypoint and runs as the official `user` account.

## Local donor registry

AEnv 0.1.96's local Docker builder always uses `pull=true`. Seed the already
loaded source image into a loopback-only registry before building:

```bash
scripts/aenv/seed_source_registry.sh \
  shopping_admin_final_0719:latest \
  localhost:5000/mcpmark/webarena-shopping-admin-source:0719
```

This registry is only a local compatibility bridge for the donor stage. The
large source image is never an ancestor or artifact of the final AEnv image.

## Build

From this directory, with the repository AEnv venv active:

```bash
../../../../.venv-aenv/bin/aenv build --no-push
```

## Local state and smoke run

Export a pristine baseline once and clone a writable slot for each run:

```bash
scripts/aenv/export_shopping_admin_baseline.sh \
  /data/mcpmark/baselines/shopping-admin-v1
scripts/aenv/clone_state_slot.sh \
  /data/mcpmark/baselines/shopping-admin-v1 \
  /data/mcpmark/slots/shopping-admin-smoke
```

Mount the slot, never the pristine baseline, at `/aenv-data`. Set
`WEBARENA_PUBLIC_BASE_URL` when the public URL is already known. If AEnv assigns
the URL after service creation, call the registered `configure_public_url` MCP
tool before starting evaluation.

## Required checks

- official health port `49999` returns 200;
- AEnv port `8081` returns 200 and exposes `webarena_status` and
  `configure_public_url`;
- Web port `8080` serves `/`, `/admin`, and representative `/media/...` paths;
- MariaDB, Elasticsearch, Nginx, PHP-FPM, Redis and AEnv are running;
- both inspect size and local cumulative layer size are below 10GB.
