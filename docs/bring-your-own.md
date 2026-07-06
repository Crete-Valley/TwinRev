# What you must provide (and what works out of the box)

This repository is fully deployable as-is, but several capabilities depend on
**proprietary or deployment-specific assets that are not distributed**. This
page lists exactly what works immediately, what needs something from you, and
the expected format of each missing piece.

## Works out of the box (nothing to provide)

| Capability | Notes |
|---|---|
| Full Kubernetes deployment (all 5 services) | `deploy/k8s/`, single-node k3s tested |
| Database with production schema + synthetic demo seed | 4 CELs, 12 plants, 11 devices, all 6 energy types |
| Synthetic time-series generation | `simulated-data-fetch` CronJob, deterministic, 7-day backfill |
| All read/analytics API endpoints | production analytics, forecast reads, maintenance CRUD, schema utilities |
| DPsim service itself | public image from RWTH Aachen ACS |

## Needs something from you

### 1. External forecasting API (endpoint + token)
- **Unlocks:** the `simulated-forecasting` CronJob (`*_prediction` tables,
  `plant_forecast`) and, downstream, the optimizer's PV-forecast input and the
  `/production-forecasting*` endpoints returning non-empty data.
- **You provide:** `FORECASTING_API_ENDPOINT` and `FORECASTING_API_KEY` in the
  `forecasting-simulation-secrets` Secret (`scripts/create-secrets.sh`).
- **How to get it:** contact the maintainers ([MAINTAINERS.md](../MAINTAINERS.md)).
- **Without it:** forecasting jobs fail fast; `GET /optimize` returns an error
  (it requires 24 hourly `plant_forecast` rows for the current day).

### 2. DPsim network archives (TSO + DSO grid models)
- **Unlocks:** `POST /dpsim/run-pipeline` (TSO) and `POST /dso/dpsim/run-pipeline`.
- **You provide**, in `digital_twin_backend/fast_api/apisrc/dpsim_assets/`
  (baked into the backend image at build time):
  - `Crete_2030.zip` — TSO network model (CIM/CGMES XMLs) with exactly this
    file name. Despite the name, supply whatever transmission model matches
    your data.
  - `cel{N}_<name>.zip` — one per DSO cell, discovered by naming convention;
    must contain `cel{N}_<name>_TP.xml`, `_SSH.xml`, `_EQ.xml`.
- **Without them:** the pipeline endpoints return a descriptive 404/500.

### 3. Grid topology mappings
- **Unlocks:** meaningful component→bus resolution and per-bus/per-line
  post-processed simulation results.
- **You provide**, in the same `dpsim_assets/` directory (placeholders ship in
  their place; keep the same JSON shape):
  - `component_to_exact_bus.json` — `{ "<component_id>": "<bus name>" }`,
    matching your network archives. A second copy lives one directory up
    (`apisrc/component_to_exact_bus.json`).
  - `tso_topology.json` — `base_kv`, `buses` (`{"<name>": {"re": "<result
    key>", "im": "<result key>"}}`), and `lines` (`name`, `prefixes`,
    `i_rated_ka`, `parallel_count`), all matching your archive's DPsim result
    keys.
- **Without them:** simulations still run; post-processing returns raw time
  axis plus a `topology_note` explaining why buses/lines are empty.

### 4. TSO/DSO profile datasets
- **Unlocks:** the TSO/DSO read endpoints (`/buses`, `/bus-power-data`,
  `/tso/year-extreme-days`, `/dso/*`) and the input profiles the DPsim
  pipelines feed into the simulation.
- **You provide:** rows in `tso_bus_mapping_new`, `tso_power_profiles_data_new`,
  `dso_power_profiles_data_cel{N}`, `dso_network_head_cel{N}` (schema ships;
  tables are empty).
- **Note:** if your profile data uses a specific label for the conventional
  balancing unit, set `TSO_BALANCING_PROFILE_TYPE` (default: `BALANCING_UNIT`)
  in the backend's environment.

### 5. Identity provider (optional)
- **Unlocks:** `POST /user/signin` (used by the CRETE VALLEY frontend login).
- **You provide:** `KEYCLOAK_TOKEN_URL` (OIDC token endpoint) and `CLIENT_KEY`
  (confidential client secret) in the `dt-secrets` Secret; optionally
  `KEYCLOAK_CLIENT_ID` (default `digital_twin`).
- **Without it:** sign-in returns 503; every other endpoint is unaffected
  (the API itself is unauthenticated).

### 6. Real device telemetry (optional)
- **Unlocks:** inverter/weather-based endpoints with real data:
  `/production-analytics/emission-reduction/`, `/Inverter_*`,
  `/production-analytics/weather/`, `/Power+Date/` and friends (they read
  `inverter_data` / `weather_data`).
- **You provide:** your own ingestion into those tables (the CRETE VALLEY
  deployment uses separate, non-bundled retriever services).
- **Without it:** these endpoints respond but with empty/zero results (one
  returns a division-by-zero error message by design of the upstream code).
