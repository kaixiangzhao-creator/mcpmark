# Postmill AEnv runtime

Official AEnv 0.1.96 sandbox runtime for MCPMark's Reddit/Postmill category.
The image excludes PostgreSQL data and `public/submission_images`. A mounted
`/aenv-data` must provide writable `postgres` and `submission_images`
directories cloned from the versioned pristine baseline.

Seed the loopback donor registry from the repository root, then build here:

```bash
scripts/aenv/seed_source_registry.sh \
  postmill-populated-exposed-withimg:latest \
  localhost:5000/mcpmark/webarena-postmill-source:withimg

../../../../.venv-aenv/bin/aenv build --no-push
```

The final stage remains `sts_ai_agent_sandbox/base:v0.1.2`, the runtime user is
the official `user`, and ports 8080, 8081 and 49999 serve Web, AEnv MCP and the
official sandbox health endpoint respectively.
