#!/bin/sh
set -eu

repository_root=$(git rev-parse --show-toplevel)
project_dir="${repository_root}/aenv/webarena/shopping/shopping-final-0712"
donor_ref=localhost:5000/mcpmark/webarena-shopping-runtime-source:0712

"${repository_root}/scripts/aenv/ensure_source_registry.sh" >/dev/null
DOCKER_BUILDKIT=1 docker build --pull=false \
  --file "${project_dir}/Dockerfile.donor" \
  --tag "$donor_ref" \
  "$project_dir"
docker push "$donor_ref"
