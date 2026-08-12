# Shopping AEnv runtime

Official AEnv 0.1.96 sandbox runtime for MCPMark's Shopping category. The
image contains Magento and its service binaries, but excludes MySQL, media and
Elasticsearch baseline data. A mounted `/aenv-data` must provide writable
`mysql`, `media` and `elasticsearch` directories cloned from a versioned
pristine baseline.

Create the sanitized donor with BuildKit, push that donor to the loopback-only
registry, then run the official AEnv build:

```bash
scripts/aenv/build_shopping_runtime_donor.sh

../../../../.venv-aenv/bin/aenv build --no-push
```

BuildKit is used only to materialize `/aenv-copy` without making the legacy
AEnv local builder commit a 67GB parent layer. The donor remains local and is
not the published artifact. The final image is still built by the official
AEnv CLI from the official sandbox base.

Unlike Admin/Postmill, do not seed the full 67GB Shopping source into the local
registry. BuildKit reads the already loaded source image locally; only the
sanitized donor is pushed for the official builder to pull.

The final stage remains `sts_ai_agent_sandbox/base:v0.1.2`, the runtime user is
the official `user`, and ports 8080, 8081 and 49999 serve Web, AEnv MCP and the
official sandbox health endpoint respectively.

Export the pristine baseline once with
`scripts/aenv/export_shopping_baseline.sh`. Clone a new writable slot from it
for each task, and mount only that slot at `/aenv-data`. Use
`WEBARENA_PUBLIC_BASE_URL` or the `configure_public_url` tool to update Magento
after the service URL is assigned.
