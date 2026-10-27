#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="${SQLAB_IMAGE:-sqlab}"

usage() {
  cat <<'EOF'
Usage:
  bash sqlab.sh create
  bash sqlab.sh shell
  bash sqlab.sh <adventure-dir> create
  bash sqlab.sh <adventure-dir> shell

Examples:
  bash sqlab.sh wd/knowhere create
  bash sqlab.sh wd/knowhere shell

Notes:
  - If no adventure directory is provided, the current directory is used.
  - Override the Docker image name with SQLAB_IMAGE=<image>.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

WORKSPACE_HOST="$PWD"

if [[ -d "$1" ]]; then
  WORKSPACE_HOST="$(cd "$1" && pwd)"
  shift
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

docker run --rm -it \
  -v "$WORKSPACE_HOST":/workspace \
  "$IMAGE_NAME" /workspace "$@"
