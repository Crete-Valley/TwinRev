#!/usr/bin/env bash
# Create the two Secrets the stack needs, without ever writing them to disk.
#
#   DB password        : generated randomly (or pass DB_PASSWORD=...)
#   Forecasting API    : taken from FORECASTING_API_ENDPOINT / FORECASTING_API_KEY
#                        env vars if set — contact the maintainers to obtain them.
#                        Left empty otherwise (data generation still works).
#
# Usage:
#   KUBECONFIG=/etc/rancher/k3s/k3s.yaml ./scripts/create-secrets.sh
set -euo pipefail

NS="${NAMESPACE:-digital-twin}"
DB_PASSWORD="${DB_PASSWORD:-$(head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 24)}"

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

kubectl -n "$NS" create secret generic dt-secrets \
  --from-literal=DB_POST_HOST=postgres \
  --from-literal=DB_POST_PORT=5432 \
  --from-literal=DB_POST_NAME=postgres \
  --from-literal=DB_POST_USER=postgres \
  --from-literal=DB_POST_PASSWORD="$DB_PASSWORD" \
  --from-literal=KEYCLOAK_TOKEN_URL="${KEYCLOAK_TOKEN_URL:-}" \
  --from-literal=CLIENT_KEY="${CLIENT_KEY:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NS" create secret generic forecasting-simulation-secrets \
  --from-literal=FORECASTING_API_ENDPOINT="${FORECASTING_API_ENDPOINT:-}" \
  --from-literal=FORECASTING_API_KEY="${FORECASTING_API_KEY:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets created in namespace '$NS'."
if [ -z "${FORECASTING_API_ENDPOINT:-}" ]; then
  echo "NOTE: forecasting endpoint/token not set — the forecasting CronJob will"
  echo "fail until you re-run this with FORECASTING_API_ENDPOINT / FORECASTING_API_KEY."
fi
