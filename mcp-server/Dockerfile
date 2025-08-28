ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# Install system dependencies
RUN apk add --no-cache \
    postgresql-dev \
    gcc \
    musl-dev \
    python3-dev \
    py3-pip

# Copy requirements first for better caching
COPY requirements.txt /tmp/requirements.txt

# Create virtual environment and install packages
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Working directory (matches what your s6 script expects)
WORKDIR /app
COPY server.py ./

# Copy s6 services
COPY rootfs/ /

# Set environment for the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Healthcheck
ENV MCP_PORT=8099
HEALTHCHECK CMD wget -qO- http://127.0.0.1:${MCP_PORT}/health || exit 1