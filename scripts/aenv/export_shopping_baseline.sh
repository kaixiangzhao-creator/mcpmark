#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 NEW_BASELINE_DIRECTORY" >&2
  exit 2
fi

destination=$1
source_image=shopping_final_0712:latest

if [ -e "$destination" ]; then
  echo "refusing to overwrite existing baseline: $destination" >&2
  exit 1
fi

mkdir -p "$destination"
docker run --rm --entrypoint /bin/sh -v "$destination:/out" "$source_image" -c '
  set -eu
  cp -a /var/lib/mysql /out/mysql
  cp -a /var/www/magento2/pub/media /out/media
  cp -a /usr/share/java/elasticsearch/data /out/elasticsearch
  chown -R 1001:1001 /out
'

manifest="${destination}.sha256"
(
  cd "$destination"
  find . -type f -print0 | sort -z | xargs -0 sha256sum
) >"$manifest"

printf 'source_image=%s\n' "$(docker image inspect "$source_image" -f '{{.Id}}')"
printf 'baseline=%s\nmanifest=%s\n' "$destination" "$manifest"
du -sh "$destination"
wc -l "$manifest"
