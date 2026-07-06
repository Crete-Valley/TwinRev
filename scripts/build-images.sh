#!/usr/bin/env bash
# Build all local images for the stack.
# Usage: sudo ./scripts/build-images.sh   (or without sudo if your user is in the docker group)
set -euo pipefail
cd "$(dirname "$0")/.."

docker build -t cvdt/db:local          db
docker build -t cvdt/dt-backend:local  digital_twin_backend/fast_api
docker build -t cvdt/optimizer:local   t4.3-optimization
docker build -t cvdt/forecasting:local simulated-forecasting/builder

echo
echo "Built images:"
docker images 'cvdt/*'
