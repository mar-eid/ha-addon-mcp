ARG BUILD_FROM
FROM $BUILD_FROM

# Set build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Add labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="mar-eid <your-email@domain.com>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Community Add-ons" \
    org.opencontainers.image.authors="mar-eid <your-email@domain.com>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://addons.community" \
    org.opencontainers.image.source="https://github.com/mar-eid/ha-addon-mcp" \
    org.opencontainers.image.documentation="https://github.com/mar-eid/ha-addon-mcp/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    postgresql-client \
    curl \
    && rm -rf /var/cache/apk/*

# Create app directory
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application files
COPY server.py ./

# Copy service files
COPY rootfs /

# Make service files executable
RUN chmod a+x /etc/services.d/mcp/run
RUN chmod a+x /etc/services.d/mcp/finish

# Expose port (for documentation - Ingress handles actual port mapping)
EXPOSE 8099

# Health check using curl instead of requests
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1

# The S6 init system will handle running the service
CMD []