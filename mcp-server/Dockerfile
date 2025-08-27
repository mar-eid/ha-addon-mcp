ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# Systempakker (bashio følger med i HA-base)
RUN apk add --no-cache python3 py3-pip curl jq

# App
WORKDIR /opt/mcp
COPY server.py requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# s6 services (rootfs legges på /)
COPY rootfs/ /

# Healthcheck (valgfritt)
ENV MCP_PORT=8099
HEALTHCHECK CMD wget -qO- http://127.0.0.1:${MCP_PORT}/health || exit 1

# Ikke sett CMD/ENTRYPOINT – HA-base har ENTRYPOINT ["/init"] (s6 pid 1)