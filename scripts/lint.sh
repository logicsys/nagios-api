#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/common.sh

# Build if image doesn't exist
if ! $RUNTIME image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "==> Dev image not found, building..."
    $RUNTIME build -f Dockerfile.dev -t "$IMAGE" .
fi

echo "==> Running flake8..."
$RUNTIME run --rm -v "$PWD:/app" -w /app "$IMAGE" \
    flake8 nagios-api nagios-cli nagios/ \
        --max-line-length=120 \
        --count \
        --show-source \
        --statistics

echo "==> Lint OK"
