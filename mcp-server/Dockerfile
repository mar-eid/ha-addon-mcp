
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# Pakker
RUN apk add --no-cache python3 py3-pip bash jq curl

# App
WORKDIR /opt/mcp
COPY server.py requirements.txt run.sh ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Helse
ENV MCP_PORT=8099
HEALTHCHECK CMD wget -qO- http://127.0.0.1:${MCP_PORT}/health || exit 1

RUN chmod +x /opt/mcp/run.sh
CMD [ "/opt/mcp/run.sh" ]
