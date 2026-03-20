#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/common.sh

IMAGE_INT="${IMAGE}-integration"

echo "==> Building integration test container ($RUNTIME)..."
echo "    This builds Nagios ${NAGIOS_VERSION:-4.5.11} from source — first run may take a few minutes."
$RUNTIME build \
    --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
    -f Dockerfile.integration \
    -t "$IMAGE_INT" .

echo "==> Running integration tests..."
$RUNTIME run --rm "$IMAGE_INT" "$@"
TEST_EXIT=$?

echo "==> Integration tests finished (exit code: $TEST_EXIT)"
exit $TEST_EXIT
