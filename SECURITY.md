# Security Policy

## Reporting a Vulnerability

We take the security of this project seriously. If you believe you have found a
security vulnerability, please report it **privately**. **Do not open a public
GitHub issue for security vulnerabilities.**

Report it by emailing the maintainers listed in [MAINTAINERS.md](MAINTAINERS.md),
or use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature for this repository.

Please include a description and impact, steps to reproduce, affected
components/versions, and any suggested remediation.

## Response

We will acknowledge your report within **5 business days** and aim to provide an
initial assessment within **10 business days**.

## Scope

This policy covers the code in this repository:

- `digital_twin_backend/` — the FastAPI backend
- `simulated-forecasting/` — synthetic data generation + forecasting service
- `t4.3-optimization/` — the multi-energy optimization service
- `db/` — the seeded PostgreSQL schema and synthetic data

### Non-production data and local defaults

The seeded database (`db/`) contains **synthetic, non-production data** only.
Database credentials are generated at deploy time by `scripts/create-secrets.sh`
(or supplied via your own Secret manifest kept outside git); the placeholder
values in `deploy/k8s/01-secrets.example.yaml` must never be used as-is in any
deployed environment.

### Deployment hardening (built in)

The Kubernetes manifests in `deploy/k8s/` ship hardened defaults: pods run as
non-root with `allowPrivilegeEscalation: false`, dropped Linux capabilities and
seccomp `RuntimeDefault`; every container has CPU/memory limits; the namespace
has default-deny NetworkPolicies with explicit allows only; the database is
ClusterIP-only. The external forecasting token and any identity provider
settings are supplied at runtime via Kubernetes Secrets and are never committed.

## Disclosure

We follow a coordinated disclosure process and ask for reasonable time to address
an issue before public disclosure.
