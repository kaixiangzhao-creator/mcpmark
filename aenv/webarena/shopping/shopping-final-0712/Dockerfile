ARG WEBARENA_SOURCE_IMAGE=localhost:5000/mcpmark/webarena-shopping-runtime-source:0712
FROM ${WEBARENA_SOURCE_IMAGE} AS source

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
COPY --chown=1001:1001 --from=source /aenv-copy/elasticsearch/ /usr/share/java/elasticsearch/
COPY --chown=1001:1001 --from=source /var/lib/redis/ /var/lib/redis/
COPY --chown=1001:1001 --from=source /var/lib/nginx/ /var/lib/nginx/
COPY --chown=1001:1001 --from=source /var/spool/ /var/spool/
COPY --chown=1001:1001 --from=source /var/mail/ /var/mail/

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
    ES_JAVA_HOME=/usr/share/java/elasticsearch/jdk \
    ES_JAVA_OPTS="-Xms512m -Xmx512m" \
    HOME=/home/user

WORKDIR /home/user
COPY requirements.txt /home/user/requirements.txt

RUN sed -i '/^[[:space:]]*user[[:space:]]\+nginx;/d; s#pid[[:space:]]\+/var/run/nginx.pid;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf && \
    sed -i 's/listen 80;/listen 8080;/; s/listen \[::\]:80/listen [::]:8080/' /etc/nginx/conf.d/default.conf && \
    sed -i '/^[[:space:]]*user[[:space:]]*=/d; /^[[:space:]]*group[[:space:]]*=/d' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's#command=mysqld --user=mysql#command=mysqld#' /etc/supervisor.d/mysql.ini && \
    sed -i 's#command=su elastico -c "ES_JAVA_HOME=/usr elasticsearch"#command=/usr/share/java/elasticsearch/bin/elasticsearch#' /etc/supervisor.d/elasticsearch.ini && \
    sed -i 's#--smtp-port=25#--smtp-port=1025#' /etc/supervisor.d/mailcatcher.ini && \
    mv /etc/supervisor.d/cron.ini /etc/supervisor.d/cron.disabled && \
    test ! -e /usr/share/java/elasticsearch/data && \
    mkdir -p /opt/aenv /aenv-data /run/mysqld /run/nginx /run/redis \
      /var/log/nginx /var/tmp/nginx/client_body /usr/local/var/run \
      /usr/share/java/elasticsearch/logs \
      /home/user/.mcp-gateway /tmp/aenv-logs \
      /var/www/magento2/var/cache /var/www/magento2/var/log \
      /var/www/magento2/var/page_cache /var/www/magento2/var/session \
      /var/www/magento2/var/view_preprocessed && \
    ln -s /aenv-data/mysql /var/lib/mysql && \
    ln -s /aenv-data/media /var/www/magento2/pub/media && \
    ln -s /aenv-data/elasticsearch /usr/share/java/elasticsearch/data && \
    python3 -m venv ${AENV_RUNTIME} && \
    ${AENV_RUNTIME}/bin/python -m pip install --upgrade pip && \
    ${AENV_RUNTIME}/bin/python -m pip install --no-cache-dir -r /home/user/requirements.txt && \
    chown -R root:root /opt/aenv && \
    chmod -R go-w /opt/aenv && \
    chown user:user /aenv-data /run /run/mysqld /run/nginx /run/redis \
      /var/log /var/log/nginx /var/tmp/nginx /usr/local/var/run \
      /usr/share/java/elasticsearch/logs /tmp/aenv-logs \
      /var/www/magento2/var /var/www/magento2/var/cache \
      /var/www/magento2/var/log /var/www/magento2/var/page_cache \
      /var/www/magento2/var/session /var/www/magento2/var/view_preprocessed

COPY --chown=1001:1001 servers.yaml /home/user/.mcp-gateway/servers.yaml
COPY --chown=1001:1001 mcp_config.json /home/user/mcp_config.json
COPY --chown=1001:1001 src /home/user/src
COPY --chown=1001:1001 health_server.py /home/user/health_server.py
COPY --chown=1001:1001 configure-shopping.sh /home/user/configure-shopping.sh
COPY supervisor-aenv.ini /etc/supervisor.d/aenv.ini
COPY supervisor-shopping-config.ini /etc/supervisor.d/shopping-config.ini

RUN chmod 0755 /home/user/configure-shopping.sh && \
    chmod 0644 /etc/supervisord.conf /etc/supervisor.d/*.ini

EXPOSE 8080 8081 49999
USER user
