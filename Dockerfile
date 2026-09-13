FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    OM_DATA_DIR=/data \
    OM_LOG_DIR=/data/logs \
    ORACLE_CLIENT_LIB_DIR=/opt/oracle/instantclient \
    LD_LIBRARY_PATH=/opt/oracle/instantclient

# Oracle Instant Client：用于 Thick 模式连接旧版本 Oracle（Thin 模式仅支持 12.1+）
ARG INSTANTCLIENT_URL=https://download.oracle.com/otn_software/linux/instantclient/2113000/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip

RUN set -eux; \
    apt-get update; \
    (apt-get install -y --no-install-recommends curl unzip ca-certificates libaio1t64 \
        || apt-get install -y --no-install-recommends curl unzip ca-certificates libaio1); \
    if [ -e /usr/lib/x86_64-linux-gnu/libaio.so.1t64 ] && [ ! -e /usr/lib/x86_64-linux-gnu/libaio.so.1 ]; then \
        ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1; \
    fi; \
    ldconfig; \
    mkdir -p /opt/oracle; \
    curl -fSL -o /tmp/instantclient.zip "$INSTANTCLIENT_URL"; \
    unzip -q /tmp/instantclient.zip -d /opt/oracle; \
    rm -f /tmp/instantclient.zip; \
    mv /opt/oracle/instantclient_* /opt/oracle/instantclient; \
    apt-get purge -y curl unzip; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data

EXPOSE 8080
VOLUME ["/data"]

CMD ["python", "run_web.py"]
