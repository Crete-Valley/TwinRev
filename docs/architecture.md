# Architecture

The system-of-systems digital twin is composed of five services deployed on
Kubernetes in the `digital-twin` namespace:

```
                       NodePort :30080
                             │
                             ▼
                   ┌───────────────────┐   http://dpsim-service:5000   ┌────────┐
                   │  dt-backend       │ ────────────────────────────▶ │ DPsim  │
                   │  (FastAPI)        │      TSO/DSO power-flow       │ :5000  │
                   └───────┬───────────┘                               └────────┘
                           │ SQL
                           ▼
                   ┌───────────────────┐        SQL     ┌──────────────────────┐
                   │  PostgreSQL       │ ◀───────────── │ optimizer (Pyomo)    │
                   │  (seeded image)   │                │ /optimize  :30082    │
                   └───────▲───────────┘                └──────────────────────┘
                           │ SQL
        ┌──────────────────┴─────────────────┐
        │ CronJob simulated-data-fetch       │  deterministic synthetic
        │ CronJob simulated-forecasting ─────┼─▶ external forecasting API
        └────────────────────────────────────┘   (endpoint + token required)
```

## Components

| Service | Image | Role |
|---|---|---|
| `dt-backend` | `cvdt/dt-backend:local` | REST API: analytics, forecast reads, maintenance, TSO/DSO pipelines |
| `dpsim-backend` | `registry.git.rwth-aachen.de/acs/public/dpsv:latest` | Power-flow simulation engine (RWTH Aachen ACS) |
| `multi-energy-optimization-model-fastapi` | `cvdt/optimizer:local` | Day-ahead multi-energy optimization (Pyomo + CBC) |
| `postgres` | `cvdt/db:local` | PostgreSQL 17, production schema + synthetic demo seed |
| CronJobs | `cvdt/forecasting:local` | `simulated-data-fetch` (synthetic time series, hourly), `simulated-forecasting` (Chronos forecasts via external API, hourly) |

## Data model (high level)

- `energy_type` (pv, wind, hydrogen, biogas, biomass, geothermal) ← `plant` ← `device`,
  grouped into `cel` (Community Energy Lab).
- Per-type time series: `<type>_data` (measurements) and `<type>_prediction`
  (forecasts), keyed on `(timestamp, device_id)`.
- TSO tables (`tso_bus_mapping*`, `tso_power_profiles_data*`, `tso_sim_results*`)
  and per-cell DSO tables (`dso_power_profiles_data_cel<N>`,
  `dso_network_head_cel<N>`, `dso_powerflow_*`) feed the DPsim pipelines.

See `db_schema.png` for the full diagram.

## Security posture

- All pods run as non-root with `allowPrivilegeEscalation: false`, dropped
  capabilities, seccomp `RuntimeDefault`, and CPU/memory limits.
- Namespace-wide **default-deny** NetworkPolicy; only the documented flows are
  allowed. Only Job pods may reach the internet (external forecasting API).
- PostgreSQL is ClusterIP-only. The two NodePorts (30080 backend, 30082
  optimizer) exist for local single-node testing; front them with an
  Ingress + TLS in any real deployment.
- All credentials live in Kubernetes Secrets created at deploy time; nothing
  sensitive is committed to the repository.
