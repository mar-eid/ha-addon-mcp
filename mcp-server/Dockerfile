ARG BUILD_FROM
FROM $BUILD_FROM

# Install only essential runtime dependencies first
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    ca-certificates

# Create app directory
WORKDIR /app

# Copy application files first
COPY server.py ./
COPY run.sh ./
RUN chmod +x run.sh

# Install Python packages with progressive fallback strategy
RUN set -e && \
    echo "=== Attempting lightweight package installation ===" && \
    \
    echo "Step 1: Core packages only" && \
    pip3 install --break-system-packages --no-cache-dir \
        --prefer-binary --only-binary=:all: \
        mcp==1.1.2 || { \
        echo "Binary mcp failed, installing from source"; \
        pip3 install --break-system-packages --no-cache-dir mcp==1.1.2; \
    } && \
    \
    echo "Step 2: Database packages" && \
    pip3 install --break-system-packages --no-cache-dir \
        --prefer-binary --only-binary=:all: \
        asyncpg==0.29.0 \
        psycopg2-binary==2.9.9 \
        python-dateutil==2.8.2 && \
    \
    echo "Step 3: Web framework (minimal)" && \
    pip3 install --break-system-packages --no-cache-dir \
        --prefer-binary --only-binary=:all: \
        fastapi==0.104.1 \
        uvicorn==0.24.0 && \
    \
    echo "=== All packages installed successfully ===" && \
    pip3 list

# Simple health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8099/health', timeout=5)" || exit 1

# Run the application
CMD ["./run.sh"]