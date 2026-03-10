#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/common.sh

echo "==> Building dev container ($RUNTIME, python $PYTHON_VERSION)..."
$RUNTIME build --build-arg PYTHON_VERSION="$PYTHON_VERSION" -f Dockerfile.dev -t "$IMAGE" .

echo "==> Verifying package install..."
$RUNTIME run --rm "$IMAGE" python -c "import nagios; print('nagios package version:', nagios.version)"

echo "==> Build OK"
