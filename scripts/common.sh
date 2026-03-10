#!/usr/bin/env bash
# Shared settings for dev scripts

set -a
source "$(dirname "$0")/../vars.env"
set +a

if command -v podman >/dev/null 2>&1; then
    RUNTIME=podman
elif command -v docker >/dev/null 2>&1; then
    RUNTIME=docker
else
    echo "Error: neither podman nor docker found" >&2
    exit 1
fi
