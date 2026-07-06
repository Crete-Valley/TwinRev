# System-of-Systems Digital Twin

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LF Energy](https://img.shields.io/badge/LF%20Energy-Sandbox%20candidate-blue.svg)](https://lfenergy.org/)

A grid-level **system-of-systems digital twin** for the island of Crete, Greece,
developed at the Electric Power Systems Laboratory (EPU), National Technical
University of Athens (NTUA), within the [CRETE VALLEY](https://cretevalley.eu/)
project.

Everything deploys on **Kubernetes** (tested on single-node [k3s](https://k3s.io)):

| Component | Folder | Role |
|---|---|---|
| **Digital Twin Backend** | [`digital_twin_backend/`](digital_twin_backend/) | FastAPI REST API: production analytics, forecast reads, maintenance, TSO/DSO power-flow pipelines |
| **DPsim** | ([public image](https://github.com/sogno-platform/dpsim)) | Power-flow simulation service used by the TSO/DSO pipelines |
| **Multi-Energy Optimization** | [`t4.3-optimization/`](t4.3-optimization/) | Pyomo day-ahead optimization service (`GET /optimize`) |
| **Simulated Forecasting** | [`simulated-forecasting/`](simulated-forecasting/) | CronJobs: synthetic data generation + Chronos forecasting pipeline |
| **Database** | [`db/`](db/) | Seeded PostgreSQL 17 (production schema, synthetic demo seed) |
| **Manifests** | [`deploy/k8s/`](deploy/k8s/) | Hardened Kubernetes manifests for the whole stack |

Architecture details: [`docs/architecture.md`](docs/architecture.md).

---

## Quick start (single-node k3s)

### 1. Prerequisites

- Docker ≥ 24 (to build the images)
- [k3s](https://docs.k3s.io/quick-start) — install with:

```bash
curl -sfL https://get.k3s.io | sudo sh -s - --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

> ~2 CPU / 4 GB RAM free is enough for the full stack.

### 2. Build & import images

```bash
sudo ./scripts/build-images.sh        # builds cvdt/{db,dt-backend,optimizer,forecasting}:local
sudo ./scripts/k3s-import-images.sh   # k3s uses its own containerd image store
```

### 3. Create secrets

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml ./scripts/create-secrets.sh
```

This generates a random database password and creates the two Secrets the stack
uses (`dt-secrets`, `forecasting-simulation-secrets`). Alternatively copy
[`deploy/k8s/01-secrets.example.yaml`](deploy/k8s/01-secrets.example.yaml) to a
file **outside git**, fill it in, and `kubectl apply -f` it.

### 4. Deploy

```bash
kubectl apply -k deploy/k8s
kubectl -n digital-twin get pods -w   # wait until everything is Running
```

### 5. Generate data & try it

```bash
# One-off synthetic-data run (also runs hourly; backfills the last 7 days)
kubectl -n digital-twin create job --from=cronjob/simulated-data-fetch data-fetch-now

curl http://localhost:30080/docs                                        # backend Swagger UI
curl "http://localhost:30080/production-analytics/production/?cel_id=1" # analytics
curl http://localhost:30082/optimize                                    # day-ahead optimization

./scripts/smoke_test.sh   # or: make smoke
```

A `Makefile` wraps all of the above (`make images import secrets deploy fetch-now smoke`).

---

## Forecasting requires an access token

The forecasting CronJob (`simulated-forecasting`, running `pv_forecasting.py`)
calls an **external forecasting API** (Chronos time-series model). This needs an
endpoint and an access token which are **not distributed** with this repository.

> **Contact the maintainers (see [MAINTAINERS.md](MAINTAINERS.md)) to obtain an
> endpoint and token**, then re-run:
>
> ```bash
> FORECASTING_API_ENDPOINT=<endpoint> FORECASTING_API_KEY=<token> ./scripts/create-secrets.sh
> ```

Without them, synthetic data generation and every other service still work;
only the forecasting job fails until configured. Never commit the endpoint or
token anywhere.

## What is intentionally NOT included

To keep the repository free of proprietary and sensitive data:

- **The database ships with the real schema but synthetic reference rows only**
  (4 demo CELs, 12 demo plants/devices — see [`db/01_seed_reference.sql`](db/01_seed_reference.sql)).
  Time-series tables start empty and are filled by the `simulated-data-fetch`
  CronJob (deterministic synthetic data, 7-day backfill).
- **DSO/TSO measurement and power-flow datasets** — the tables exist (schema is
  reproduced from production) but ship empty, so the DSO/TSO read endpoints
  return empty results until you load your own data.
- **DPsim network archives** (`dpsim_assets/*.zip`) and the **real grid
  topology** (`component_to_exact_bus.json` and `tso_topology.json` are
  placeholders) — the DPsim simulation pipelines need these proprietary assets
  to run; supply your own network models to use them.

See **[docs/bring-your-own.md](docs/bring-your-own.md)** for the complete list
of what works out of the box, what each missing piece unlocks, and the exact
formats to provide.
- **Credentials, tokens, and service endpoints** — supplied only at deploy time
  via Kubernetes Secrets (see [`deploy/k8s/01-secrets.example.yaml`](deploy/k8s/01-secrets.example.yaml)).

## Security

Hardening applied out of the box (details in
[`docs/architecture.md`](docs/architecture.md)): non-root pods with dropped
capabilities and seccomp, CPU/memory limits everywhere, namespace-wide
default-deny NetworkPolicies, ClusterIP-only database, secrets only via
Kubernetes Secrets. The two NodePorts (30080/30082) are for local testing —
never expose them from an internet-facing host without an Ingress + TLS and a
host firewall in front.

See [SECURITY.md](SECURITY.md) to report vulnerabilities.

## Project health & governance

[GOVERNANCE.md](GOVERNANCE.md) · [MAINTAINERS.md](MAINTAINERS.md) ·
[CONTRIBUTING.md](CONTRIBUTING.md) (with DCO sign-off) ·
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [SECURITY.md](SECURITY.md)

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Developed as part of the [CRETE VALLEY](https://cretevalley.eu/) project, funded
by the European Union's Horizon Europe programme. Power-flow simulation by
[DPsim](https://github.com/sogno-platform/dpsim) (LF Energy SOGNO).
