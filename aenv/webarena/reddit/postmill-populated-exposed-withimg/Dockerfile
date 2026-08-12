ARG WEBARENA_SOURCE_IMAGE=localhost:5000/mcpmark/webarena-postmill-source:withimg
FROM ${WEBARENA_SOURCE_IMAGE} AS source

USER root
# Build a donor view that excludes the 40GB image tree, PostgreSQL baseline,
# caches and logs. GNU tar excludes these directories without descending into
# their contents.
RUN mkdir -p /aenv-copy/www /aenv-copy /external-state && \
    tar -C /var/www \
      --exclude='./html/public/submission_images' \
      --exclude='./html/var/cache' \
      --exclude='./html/var/log' \
      --exclude='./html/var/sessions' \
      -cf - . | tar -C /aenv-copy/www -xf - && \
    mv /usr/local/pgsql /aenv-copy/pgsql && \
    rm -rf /aenv-copy/pgsql/data && \
    mv /usr/share/java/elasticsearch /external-state/elasticsearch-unused

FROM harbor.shopeemobile.com/sts_ai_agent_sandbox/base:v0.1.2 AS sandbox-base
FROM sandbox-base AS runtime

USER root

COPY --from=source /bin/ /usr/bin/
COPY --from=source /sbin/ /usr/sbin/
COPY --from=source /usr/ /usr/
COPY --from=source /lib/ /usr/lib/
COPY --from=source /etc/ /etc/
COPY --from=source /opt/ /opt/

COPY --chown=1001:1001 --from=source /aenv-copy/www/ /var/www/
COPY --chown=1001:1001 --from=source /aenv-copy/pgsql/ /usr/local/pgsql/
COPY --chown=1001:1001 --from=source /var/lib/nginx/ /var/lib/nginx/
COPY --chown=1001:1001 --from=source /var/spool/ /var/spool/

COPY --from=sandbox-base /etc/passwd /etc/passwd
COPY --from=sandbox-base /etc/group /etc/group
COPY --from=sandbox-base /etc/shadow /etc/shadow
COPY --from=sandbox-base /etc/gshadow /etc/gshadow
COPY --from=sandbox-base /etc/ld.so.cache /etc/ld.so.cache
COPY --from=sandbox-base /etc/ld.so.conf /etc/ld.so.conf
COPY --from=sandbox-base /etc/ld.so.conf.d/ /etc/ld.so.conf.d/

ENV AENV_RUNTIME=/opt/aenv/runtime \
    AENV_DATA_ROOT=/aenv-data \
    AENV_TOOLS_PATH=/home/user/src \
    HOME=/home/user

WORKDIR /home/user
COPY requirements.txt /home/user/requirements.txt

RUN sed -i '/^[[:space:]]*user[[:space:]]\+nginx;/d; s#pid[[:space:]]\+/var/run/nginx.pid;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf && \
    sed -i 's/listen 80;/listen 8080;/; s/listen \[::\]:80/listen [::]:8080/' /etc/nginx/conf.d/default.conf && \
    sed -i '/^[[:space:]]*user[[:space:]]*=/d; /^[[:space:]]*group[[:space:]]*=/d' /usr/local/etc/php-fpm.d/www.conf && \
    mkdir -p /opt/aenv /aenv-data /run/postgresql /run/nginx \
      /var/log/nginx /var/tmp/nginx/client_body /usr/local/var/run \
      /home/user/.mcp-gateway /tmp/aenv-logs \
      /var/www/html/var/cache /var/www/html/var/log /var/www/html/var/sessions && \
    ln -s /aenv-data/postgres /usr/local/pgsql/data && \
    ln -s /aenv-data/submission_images /var/www/html/public/submission_images && \
    python3 -m venv ${AENV_RUNTIME} && \
    ${AENV_RUNTIME}/bin/python -m pip install --upgrade pip && \
    ${AENV_RUNTIME}/bin/python -m pip install --no-cache-dir -r /home/user/requirements.txt && \
    chown -R root:root /opt/aenv && \
    chmod -R go-w /opt/aenv && \
    chown user:user /aenv-data /run /run/postgresql /run/nginx \
      /var/log /var/log/nginx /var/tmp/nginx /usr/local/var/run \
      /tmp/aenv-logs /var/www/html/var /var/www/html/var/cache \
      /var/www/html/var/log /var/www/html/var/sessions

COPY --chown=1001:1001 servers.yaml /home/user/.mcp-gateway/servers.yaml
COPY --chown=1001:1001 mcp_config.json /home/user/mcp_config.json
COPY --chown=1001:1001 src /home/user/src
COPY --chown=1001:1001 health_server.py /home/user/health_server.py
COPY supervisor-aenv.ini /etc/supervisor.d/aenv.ini
COPY supervisor-postgres.ini /etc/supervisor.d/pgsql.ini

RUN chmod 0644 /etc/supervisord.conf /etc/supervisor.d/*.ini

EXPOSE 8080 8081 49999
USER user
