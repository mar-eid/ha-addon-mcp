ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# Systempakker
RUN apk add --no-cache python3 py3-pip bash jq curl

# Oppgrader pip/setuptools/wheel (viktig for å hente riktige wheels)
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# App
WORKDIR /opt/mcp
COPY server.py requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# s6-tjenester (du har allerede rootfs/ lagt opp i forrige steg)
COPY rootfs/ /

ENV MCP_PORT=8099
HEALTHCHECK CMD wget -qO- http://127.0.0.1:${MCP_PORT}/health || exit 1