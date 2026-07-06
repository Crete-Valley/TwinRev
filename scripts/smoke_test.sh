#!/usr/bin/env bash
# End-to-end smoke test for a deployed stack (defaults to the local k3s NodePorts).
# Run `make fetch-now` first so the synthetic time-series data exists.
# Usage: ./scripts/smoke_test.sh
set -uo pipefail

API="${API_URL:-http://localhost:30080}"
OPT="${OPTIMIZER_URL:-http://localhost:30082}"

pass=0; fail=0
check() { # name  expected_regex  actual
  if echo "$3" | grep -qE "$2"; then echo "  ok   $1"; pass=$((pass+1));
  else echo "  FAIL $1 (got: $(echo "$3" | head -c 200))"; fail=$((fail+1)); fi
}

echo "== backend =="
check "openapi"                 '"openapi"'        "$(curl -s $API/openapi.json)"
check "/get_schema/"            'energy_type'      "$(curl -s "$API/get_schema/")"
check "/unique_column_values/"  'pv'               "$(curl -s "$API/unique_column_values/?table=energy_type&column=name")"

echo "== production =="
check "production-analytics"    '\[|\{'            "$(curl -s "$API/production-analytics/production/?cel_id=cel3-pv")"
check "production-forecasting"  '\[|\{'            "$(curl -s "$API/production-forecasting/?cel_id=cel1-pv")"

echo "== maintenance =="
check "scheduled_events"        '\[|\{'            "$(curl -s "$API/scheduled_events/?cel_id=cel1-pv")"

echo "== TSO / DSO (tables ship empty; endpoints must respond) =="
check "tso /buses"              '\[|\{'            "$(curl -s "$API/buses")"
check "dso /buses (cell 3)"     '\[|\{|does not exist' "$(curl -s "$API/dso/buses?cell=3")"

echo "== optimizer =="
# A full /optimize needs plant_forecast rows, which the forecasting CronJob only
# produces once the external forecasting API token is configured. Without them
# the service returns an error — here we only require the service to be up.
check "optimizer /docs up"      'swagger|openapi|html' "$(curl -s "$OPT/docs")"
OPT_BODY="$(curl -s --max-time 300 "$OPT/optimize")"
if echo "$OPT_BODY" | grep -q '"status"'; then
  echo "  ok   /optimize (full run)"; pass=$((pass+1))
else
  echo "  note /optimize returned no result — expected until the forecasting job has run (needs API token)"
fi

echo
echo "Passed: $pass   Failed: $fail"
[ "$fail" -eq 0 ]
