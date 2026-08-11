# sweb-sandbox template

This template wraps a SWE-bench `sweb.eval.x86_64.*` image inside the sandbox base image used by AEnv.

## What it does

- Uses the selected `SWEB_SOURCE_IMAGE` as a source stage
- Keeps `sts_ai_agent_sandbox/base` as the final runtime layer
- Copies `/testbed` and `/opt/miniconda3` from the source image
- Starts the standard AEnv sandbox entrypoint

## Before building

Update `SWEB_SOURCE_IMAGE` in `Dockerfile` to the specific SWE-bench image you want to wrap.

## Validation helpers

The generated environment includes:

- `image_info()`
- `repo_listing(path, limit=50)`
- `basic_health(task="sweb-sandbox")`

