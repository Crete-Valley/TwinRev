# Contributing

Thank you for your interest in contributing to the System-of-Systems Digital Twin.

## Getting Started

1. Fork the repository and clone your fork.
2. Follow the [Quick start](README.md#quick-start-single-node-k3s) to build the
   images and deploy the stack on a local single-node Kubernetes (k3s).
3. The backend API is at `http://localhost:30080` (docs at `/docs`); the
   optimizer is at `http://localhost:30082`.

## Development Workflow

- Create a branch from `main` for your changes.
- Keep pull requests focused: one feature or fix per PR.
- Add or update tests/docs where applicable.
- Ensure the stack deploys and `./scripts/smoke_test.sh` passes before opening a PR.

## Reporting Issues

Open a GitHub issue with a clear title, steps to reproduce (if a bug), and
expected vs. actual behaviour.

## Developer Certificate of Origin (DCO)

All contributions must be signed off in accordance with the
[Developer Certificate of Origin](https://developercertificate.org/). Add a
`Signed-off-by` line with your real name and email to each commit:

```bash
git commit -s -m "Your commit message"
```

Pull requests with unsigned commits will be asked to amend them before merge.

## Code Style

- Python: follow [PEP 8](https://peps.python.org/pep-0008/).
- SQL: uppercase keywords, lowercase identifiers.

## Never commit

- Real credentials, tokens, API endpoints, or `.env` files.
- Proprietary data (DSO datasets, network `.zip` archives, real grid topology).

All contributors must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
