ARG BUILD_FROM
FROM $BUILD_FROM

# Install minimal system dependencies
RUN apk add --no-cache python3 py3-pip

# Create app directory
WORKDIR /app

# Copy and install Python packages with debugging
COPY requirements.txt ./
RUN echo "=== Installing Python packages ===" && \
    cat requirements.txt && \
    echo "=== Using pip3 with break-system-packages ===" && \
    pip3 install --break-system-packages --no-cache-dir -r requirements.txt && \
    echo "=== Installation successful ==="

# Copy application
COPY server.py ./

# Copy services
COPY rootfs /

# Simple healthcheck
HEALTHCHECK CMD python3 -c "import requests; requests.get('http://localhost:8099/health')" || exit 1