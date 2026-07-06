#!/usr/bin/env bash
# Import the locally built docker images into k3s's containerd store.
# k3s does not share docker's image store, so this is required after building.
# Usage: sudo ./scripts/k3s-import-images.sh
set -euo pipefail

# -n k8s.io is required: kubelet only sees images in containerd's k8s.io
# namespace, while ctr defaults to the "default" namespace.
for img in cvdt/db:local cvdt/dt-backend:local cvdt/optimizer:local cvdt/forecasting:local; do
  echo "Importing $img ..."
  docker save "$img" | k3s ctr -n k8s.io images import -
done

k3s ctr -n k8s.io images ls | grep cvdt/ || true
