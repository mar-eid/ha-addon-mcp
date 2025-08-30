ARG BUILD_FROM
FROM $BUILD_FROM

# Install minimal system dependencies  
RUN apk add --no-cache \
    python3 \
    py3-pip \
    postgresql-client \
    curl

# Create app directory
WORKDIR /app

# Copy and install Python packages
COPY requirements.txt ./
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Copy application and run script
COPY server.py ./
COPY run.sh ./

# Make run script executable
RUN chmod +x run.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1

# Direct execution (no s6-overlay)
CMD ["./run.sh"]
