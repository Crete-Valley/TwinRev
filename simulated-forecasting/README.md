# Simulated Forecasting Cronjob Repository

This repository contains the source code for two cronjobs that together populate the Crete Valley digital twin with simulated energy data and hourly forecasts.

## Cronjobs

### simulated-data-fetch

Runs every hour at `:00`. For each device registered in the database, it generates deterministic simulated energy values (PV output, wind output, or city net consumption) for the past N hours and upserts them into the corresponding `staging.*_data` tables. The lookback window is controlled by the `HOURS_TO_BACKFILL` environment variable (default: 6 hours).

### simulated-forecasting

Runs every hour at `:01` — one minute after `simulated-data-fetch` to ensure fresh data is available. For each device, it reads the last 7 days of historical data from the database, calls the external forecasting API (Chronos model), and upserts the resulting 24-hour predictions with confidence intervals into the `staging.*_prediction` tables.

## Repository Structure

<ins>builder/</ins> — source code and container definition

- <ins>Dockerfile</ins>: Container image definition. Both cronjobs use the same image, differentiated by the entrypoint command in the Kubernetes manifests.
- <ins>pv_data_fetch.py</ins>: Entrypoint for the `simulated-data-fetch` cronjob.
- <ins>pv_forecasting.py</ins>: Entrypoint for the `simulated-forecasting` cronjob.
- <ins>forecasting_client.py</ins>: HTTP client for the external forecasting API.
- <ins>requirements.txt</ins>: Python dependencies installed inside the container.

<ins>k8s/</ins> — Kubernetes manifests

- <ins>data_fetch_cron.yaml</ins>: CronJob manifest for `simulated-data-fetch` (schedule: `0 * * * *`).
- <ins>forecasting_cron.yaml</ins>: CronJob manifest for `simulated-forecasting` (schedule: `1 * * * *`).

## Deployment

### Build the container image

Run from the repository root (see also `scripts/build-images.sh`):

```bash
docker build -t cvdt/forecasting:local simulated-forecasting/builder
```

### Deploy to the Kubernetes cluster

The CronJob manifests live in [`deploy/k8s/`](../deploy/k8s/):

```bash
kubectl apply -f deploy/k8s/06-cronjob-data-fetch.yaml
kubectl apply -f deploy/k8s/07-cronjob-forecasting.yaml
```

### Monitor

```bash
# List cronjobs and their last schedule time
kubectl get cronjobs

# Inspect a specific cronjob
kubectl describe cronjob simulated-data-fetch
kubectl describe cronjob simulated-forecasting

# View logs from the most recent job pod
kubectl logs -l job-name=<job-name>
```

## Reprocessing historical data

When a simulation function changes, previously stored values become stale. The fetch job upserts with `ON CONFLICT DO UPDATE`, so re-running it over a past window overwrites the old values.

1. Edit `HOURS_TO_BACKFILL` in `deploy/k8s/06-cronjob-data-fetch.yaml` to cover the window you want to rewrite (e.g. `"168"` for the last 7 days).
2. Apply the updated manifest:
   ```bash
   kubectl apply -f deploy/k8s/06-cronjob-data-fetch.yaml
   ```
3. Trigger a one-off run immediately instead of waiting for the next hour:
   ```bash
   kubectl create job --from=cronjob/simulated-data-fetch simulated-data-fetch-reprocess
   ```
4. Once the run completes, revert `HOURS_TO_BACKFILL` to its normal value and re-apply.

To also regenerate forecasts off the rewritten history, trigger the forecasting job the same way:

```bash
kubectl create job --from=cronjob/simulated-forecasting simulated-forecasting-reprocess
```

## Configuration

Both cronjobs read database credentials from the `dt-secrets` Kubernetes secret (see `deploy/k8s/01-secrets.example.yaml`).

The `simulated-forecasting` cronjob additionally requires the `forecasting-simulation-secrets` secret with `FORECASTING_API_ENDPOINT` and `FORECASTING_API_KEY`.

The `simulated-data-fetch` cronjob accepts an optional `HOURS_TO_BACKFILL` environment variable (set in `deploy/k8s/06-cronjob-data-fetch.yaml`, default here: 168).
