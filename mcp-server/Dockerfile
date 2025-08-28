ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system dependencies in one layer
RUN apk add --no-cache \
    postgresql-dev=15.4-r0 \
    gcc=12.2.1_git20220924-r10 \
    musl-dev=1.2.4-r2 \
    python3-dev=3.11.6-r1

# Create app directory
WORKDIR /app

# Copy Python requirements
COPY requirements.txt /tmp/requirements.txt

# Install Python packages using the method recommended by HA guidelines
RUN \
    pip3 install --no-cache-dir --find-links \
    "https://wheels.home-assistant.io/alpine-$(cut -d '.' -f 1-2 /etc/alpine-release)/" \
    -r /tmp/requirements.txt \
    && rm -rf /tmp/requirements.txt

# Copy application code
COPY server.py ./

# Copy root filesystem
COPY rootfs /

# Build arguments (provided by Home Assistant Builder)
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels following HA guidelines
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="mar-eid" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Community Add-ons" \
    org.opencontainers.image.authors="mar-eid" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/mar-eid/ha-addon-mcp" \
    org.opencontainers.image.source="https://github.com/mar-eid/ha-addon-mcp" \
    org.opencontainers.image.documentation="https://github.com/mar-eid/ha-addon-mcp/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

# Healthcheck (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8099/health || exit 1