#!/bin/sh
set -eu

registry_container=mcpmark-aenv-source-registry
repository_root=$(git rev-parse --show-toplevel)
registry_data=${MCPMARK_SOURCE_REGISTRY_DATA:-"${repository_root}/../mcpmark-registry"}

if docker container inspect "$registry_container" >/dev/null 2>&1; then
  mount_type=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/registry"}}{{.Type}}{{end}}{{end}}' "$registry_container")
  if [ "$mount_type" != bind ]; then
    echo "registry must bind-mount /var/lib/registry outside Docker's data disk" >&2
    echo "remove the recoverable donor registry and run this command again" >&2
    exit 1
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$registry_container")" != true ]; then
    docker start "$registry_container" >/dev/null
  fi
else
  mkdir -p "$registry_data"
  docker run -d --restart unless-stopped --name "$registry_container" \
    -p 127.0.0.1:5000:5000 \
    -v "$registry_data:/var/lib/registry" registry:2 >/dev/null
fi

printf 'registry=%s\ndata=%s\n' "$registry_container" "$registry_data"
