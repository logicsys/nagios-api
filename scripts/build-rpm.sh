#!/usr/bin/env bash
# Build an .rpm package for nagios-api inside a container.
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/common.sh

VERSION=${1:-${VERSION:?VERSION not set in vars.env}}
RELEASE=${2:-1}
OUTDIR="$(pwd)/dist"
IMAGE_PKG="nagios-api-rpm-builder"

echo "==> Building rpm package for nagios-api ${VERSION}-${RELEASE} ..."

mkdir -p "$OUTDIR"

$RUNTIME build -f - -t "$IMAGE_PKG" . <<'DOCKERFILE'
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ruby ruby-dev gcc make rpm && \
    gem install fpm --no-document && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /build
DOCKERFILE

$RUNTIME run --rm \
    -v "$(pwd):/src:ro" \
    -v "$OUTDIR:/out" \
    "$IMAGE_PKG" bash -c "
set -euo pipefail

# Install into a staging root
STAGING=/tmp/staging
mkdir -p \$STAGING

# Install Python deps + package into staging
pip install --no-cache-dir -r /src/requirements.txt --prefix=/usr --root=\$STAGING
cp -r /src/nagios \$STAGING/usr/lib/python3.11/site-packages/ 2>/dev/null || \
    cp -r /src/nagios \$(python3 -c 'import sysconfig; print(sysconfig.get_paths()[\"purelib\"])' | sed \"s|^/|\$STAGING/|\") /

# Install executables
mkdir -p \$STAGING/usr/bin
install -m 755 /src/nagios-api \$STAGING/usr/bin/nagios-api
install -m 755 /src/nagios-cli \$STAGING/usr/bin/nagios-cli

# Install systemd unit
mkdir -p \$STAGING/usr/lib/systemd/system
cat > \$STAGING/usr/lib/systemd/system/nagios-api.service <<'UNIT'
[Unit]
Description=Nagios API Server
After=network.target nagios.service

[Service]
Type=simple
User=nagios
Group=nagios
ExecStart=/usr/bin/nagios-api -p 8080 -s /var/cache/nagios3/status.dat -c /var/lib/nagios3/rw/nagios.cmd -l /var/log/nagios3/nagios.log -q
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# Install default config
mkdir -p \$STAGING/etc/sysconfig
cat > \$STAGING/etc/sysconfig/nagios-api <<'CONF'
# Configuration for nagios-api service
# Uncomment and modify as needed, then update the systemd unit's ExecStart.
#NAGIOS_API_PORT=8080
#NAGIOS_API_BIND=127.0.0.1
#NAGIOS_STATUS_FILE=/var/cache/nagios3/status.dat
#NAGIOS_CMD_FILE=/var/lib/nagios3/rw/nagios.cmd
#NAGIOS_LOG_FILE=/var/log/nagios3/nagios.log
CONF

fpm -s dir -t rpm \
    -n nagios-api \
    -v ${VERSION} \
    --iteration ${RELEASE} \
    --architecture noarch \
    --description 'REST-like JSON API for Nagios' \
    --url 'https://github.com/xb95/nagios-api' \
    --license 'BSD-3-Clause' \
    --maintainer 'Mark Smith <mark@qq.is>' \
    --depends python3 \
    --depends python3-flask \
    --depends python3-requests \
    --depends python3-waitress \
    --config-files /etc/sysconfig/nagios-api \
    --after-install /dev/stdin \
    -C \$STAGING \
    -p /out/nagios-api-${VERSION}-${RELEASE}.noarch.rpm \
    . <<'POSTINST'
#!/bin/sh
systemctl daemon-reload || true
POSTINST
"

echo "==> Package built: $OUTDIR/nagios-api-${VERSION}-${RELEASE}.noarch.rpm"
