#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 SOURCE_IMAGE localhost:5000/REPOSITORY:TAG" >&2
  exit 2
fi

source_image=$1
target_ref=$2
registry_container=mcpmark-aenv-source-registry

case "$target_ref" in
  localhost:5000/*) ;;
  *) echo "target must use the loopback-only localhost:5000 registry" >&2; exit 2 ;;
esac

docker image inspect "$source_image" >/dev/null
if docker container inspect "$registry_container" >/dev/null 2>&1; then
  if [ "$(docker inspect -f '{{.State.Running}}' "$registry_container")" != true ]; then
    docker start "$registry_container" >/dev/null
  fi
else
  docker run -d --restart unless-stopped --name "$registry_container" \
    -p 127.0.0.1:5000:5000 registry:2 >/dev/null
fi

docker tag "$source_image" "$target_ref"
docker push "$target_ref"
