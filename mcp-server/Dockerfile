ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# System packages
RUN apk add --no-cache \
    postgresql-dev \
    gcc \
    musl-dev \
    python3-dev \
    bash \
    jq \
    curl

# Fix PEP 668 issue by using --break-system-packages (safe in containers)
WORKDIR /opt/mcp
COPY server.py requirements.txt ./

# Install Python packages (bypass PEP 668 in container)
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Copy s6 services (use your existing structure)
COPY rootfs/ /

# Healthcheck
ENV MCP_PORT=8099
HEALTHCHECK CMD curl -f http://127.0.0.1:${MCP_PORT}/health || exit 1