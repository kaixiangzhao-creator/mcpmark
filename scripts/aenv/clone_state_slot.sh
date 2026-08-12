#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 PRISTINE_BASELINE NEW_WRITABLE_SLOT" >&2
  exit 2
fi

baseline=$1
slot=$2

if [ ! -d "$baseline" ]; then
  echo "baseline directory does not exist: $baseline" >&2
  exit 1
fi
if [ -e "$slot" ]; then
  echo "refusing to overwrite existing slot: $slot" >&2
  exit 1
fi

mkdir -p "$(dirname "$slot")"
cp -a --reflink=auto "$baseline" "$slot"
printf 'slot=%s\n' "$slot"
