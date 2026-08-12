#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 SOURCE_IMAGE localhost:5000/REPOSITORY:TAG" >&2
  exit 2
fi

source_image=$1
target_ref=$2
repository_root=$(git rev-parse --show-toplevel)

case "$target_ref" in
  localhost:5000/*) ;;
  *) echo "target must use the loopback-only localhost:5000 registry" >&2; exit 2 ;;
esac

docker image inspect "$source_image" >/dev/null
"${repository_root}/scripts/aenv/ensure_source_registry.sh" >/dev/null

docker tag "$source_image" "$target_ref"
docker push "$target_ref"
