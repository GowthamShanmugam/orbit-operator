#!/usr/bin/env bash
set -euo pipefail

IMAGE_REGISTRY="${IMAGE_REGISTRY:-quay.io}"
IMAGE_ORG="${IMAGE_ORG:-gshanmug-quay}"
VERSION="${VERSION:-0.1.0}"

usage() {
    echo "Usage: $0 [-v VERSION] [-r REGISTRY] [-o ORG]"
    echo ""
    echo "  -v, --version   Image tag          (default: ${VERSION})"
    echo "  -r, --registry  Container registry  (default: ${IMAGE_REGISTRY})"
    echo "  -o, --org       Registry org/user   (default: ${IMAGE_ORG})"
    echo "  -h, --help      Show this help"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--version)  VERSION="$2";        shift 2 ;;
        -r|--registry) IMAGE_REGISTRY="$2"; shift 2 ;;
        -o|--org)      IMAGE_ORG="$2";      shift 2 ;;
        -h|--help)     usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

IMAGE="${IMAGE_REGISTRY}/${IMAGE_ORG}/orbit-operator:${VERSION}"

echo "==> Building ${IMAGE} (linux/amd64)"
START=$(date +%s)

podman build --platform linux/amd64 -t "${IMAGE}" -f Containerfile .

BUILD_END=$(date +%s)
echo "==> Build completed in $(( BUILD_END - START ))s"

echo "==> Pushing ${IMAGE}"
podman push "${IMAGE}"

PUSH_END=$(date +%s)
echo "==> Push completed in $(( PUSH_END - BUILD_END ))s"
echo "==> Total: $(( PUSH_END - START ))s"
echo "==> Done: ${IMAGE}"
