#!/bin/sh
set -eu

DATA_ROOT="${AENV_DATA_ROOT:-/aenv-data}"
for required in mysql media elasticsearch; do
  if [ ! -d "${DATA_ROOT}/${required}" ]; then
    echo "AEnv external baseline is missing ${DATA_ROOT}/${required}" >&2
    exit 1
  fi
done

BASE_URL="${WEBARENA_PUBLIC_BASE_URL:-http://127.0.0.1:8080/}"
case "${BASE_URL}" in
  http://*|https://*) ;;
  *) echo "WEBARENA_PUBLIC_BASE_URL must start with http:// or https://" >&2; exit 2 ;;
esac
case "${BASE_URL}" in */) ;; *) BASE_URL="${BASE_URL}/" ;; esac

cd /var/www/magento2
attempt=0
until php bin/magento config:show web/unsecure/base_url >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge 180 ]; then
    echo "Magento database did not become ready within 180 seconds" >&2
    exit 1
  fi
  sleep 1
done

php bin/magento config:set web/unsecure/base_url "${BASE_URL}"
php bin/magento config:set web/secure/base_url "${BASE_URL}"
php bin/magento cache:flush
