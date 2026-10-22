#!/usr/bin/env bash
# Copyright Solace Corporation
# SPDX-License-Identifier: Apache-2.0

# Builds the Python tool bundle in AWS-Lambda-Layer style. The pip-install
# step downloads wheels for the deployment's target platform. That target
# is a property of the deployment, not this toolset, so it is never
# defaulted: sam config apply discovers it from the platform the manifest
# points at and exports SAM_TOOL_TARGET_OS / SAM_TOOL_TARGET_ARCH; for a
# manual build, export both first.
set -euo pipefail

OUT_DIR="${SAM_TOOL_BUILD_OUT:-dist}"
: "${SAM_TOOL_TARGET_OS:?must be set by sam config apply, or exported for a manual build (e.g. linux)}"
: "${SAM_TOOL_TARGET_ARCH:?must be set by sam config apply, or exported for a manual build (e.g. amd64)}"
TARGET_OS="$SAM_TOOL_TARGET_OS"
TARGET_ARCH="$SAM_TOOL_TARGET_ARCH"
# Default tracks the STR runtime container's Python (3.11). Native wheels
# built for another version (e.g. 3.13) fail to load at discovery time.
PYTHON_VERSION="${SAM_TOOL_PYTHON_VERSION:-3.11}"

HOST_OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "$HOST_OS" in
  darwin) HOST_OS=darwin ;;
  linux)  HOST_OS=linux ;;
  *)      HOST_OS=unknown ;;
esac
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  x86_64|amd64)  HOST_ARCH=amd64 ;;
  arm64|aarch64) HOST_ARCH=arm64 ;;
  *)             HOST_ARCH=unknown ;;
esac
HOST_PYTHON_VERSION="$(python3 --version 2>&1 | sed 's/Python \([0-9]*\.[0-9]*\).*/\1/')"

PLATFORM_ARGS=()
# Apply --platform when OS/arch differ OR when the host python minor
# differs from the target (same-arch Python version mismatch still
# produces ABI-incompatible wheels).
if [ "$TARGET_OS-$TARGET_ARCH" != "$HOST_OS-$HOST_ARCH" ] || [ "$HOST_PYTHON_VERSION" != "$PYTHON_VERSION" ]; then
  case "$TARGET_OS-$TARGET_ARCH" in
    linux-arm64)   PLATFORM=manylinux2014_aarch64 ;;
    linux-amd64)   PLATFORM=manylinux2014_x86_64 ;;
    darwin-arm64)  PLATFORM=macosx_11_0_arm64 ;;
    darwin-amd64)  PLATFORM=macosx_10_9_x86_64 ;;
    *)
      echo "unsupported target $TARGET_OS-$TARGET_ARCH" >&2
      exit 1
      ;;
  esac
  PLATFORM_ARGS=(--platform "$PLATFORM" --python-version "$PYTHON_VERSION" --only-binary=:all:)
fi

mkdir -p "$OUT_DIR/python"
# ${PLATFORM_ARGS[@]+...} guards the empty-array expansion: bare
# "${PLATFORM_ARGS[@]}" trips 'set -u' on bash < 4.4 (e.g. macOS's system
# bash 3.2) when the native-build path leaves the array empty.
python3 -m pip install --target "$OUT_DIR/python" \
  ${PLATFORM_ARGS[@]+"${PLATFORM_ARGS[@]}"} \
  --upgrade \
  .

cp manifest.yaml "$OUT_DIR/manifest.yaml"
echo "built ${TARGET_OS}/${TARGET_ARCH} tool: $OUT_DIR/python/bin/sla-clock"
