#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/common.sh

# Build if image doesn't exist
if ! $RUNTIME image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "==> Dev image not found, building..."
    $RUNTIME build --build-arg PYTHON_VERSION="$PYTHON_VERSION" -f Dockerfile.dev -t "$IMAGE" .
fi

rc=0

echo "==> Checking all dependencies are installed..."
missing=$($RUNTIME run --rm -v "$PWD:/app" -w /app "$IMAGE" \
    python -c "
import re, sys
installed = {}
from importlib.metadata import distributions
for d in distributions():
    installed[d.metadata['Name'].lower()] = d.version

with open('requirements.txt') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name = re.split('[=<>!~]', line)[0].strip().lower()
        if name not in installed:
            print(name)
")

if [ -n "$missing" ]; then
    echo "FAIL: the following dependencies are not installed:"
    for pkg in $missing; do
        echo "  - $pkg"
    done
    rc=1
else
    echo "  All dependencies installed."
fi

echo ""
echo "==> Auditing dependencies for known vulnerabilities..."
if ! $RUNTIME run --rm "$IMAGE" \
    pip-audit --local --desc "$@"; then
    rc=1
fi

echo ""
echo "==> Checking for outdated packages..."
$RUNTIME run --rm "$IMAGE" \
    pip list --outdated --format columns 2>/dev/null || true

echo ""
if [ $rc -ne 0 ]; then
    echo "==> Audit FAILED"
else
    echo "==> Audit complete"
fi
exit $rc
