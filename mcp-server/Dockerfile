ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# Systempakker
RUN apk add --no-cache python3 py3-pip bash jq curl

# Opprett venv og bruk den videre
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# (Valgfritt) oppgrader pip i venv – dette ER lov
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# App
WORKDIR /opt/mcp
COPY server.py requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# s6 services
COPY rootfs/ /

# Healthcheck
ENV MCP_PORT=8099
HEALTHCHECK CMD wget -qO- http://127.0.0.1:${MCP_PORT}/health || exit 1