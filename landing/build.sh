#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-xenage-landing}"

REGISTRY_FIRST="${REGISTRY_FIRST:-first.registry.wtf.dton.io}"
REGISTRY_SECOND="${REGISTRY_SECOND:-second.registry.wtf.dton.io}"
TAG="${TAG:-latest}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "Building image for ${IMAGE_NAME}:${TAG}"

# Build local image and tag for both registries
docker build \
  -t "${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}" \
  -t "${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}" \
  "${SCRIPT_DIR}"

# Push both tags
docker push "${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}"
docker push "${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}"

echo "Pushed:"
echo " - ${REGISTRY_FIRST}/${IMAGE_NAME}:${TAG}"
echo " - ${REGISTRY_SECOND}/${IMAGE_NAME}:${TAG}"
