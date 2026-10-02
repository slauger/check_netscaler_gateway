# Contributing

## Development setup

Requires Python 3.12 or later.

```bash
git clone https://github.com/slauger/check_netscaler_gateway.git
cd check_netscaler_gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Verify your changes

```bash
make ci
```

This runs ruff, black, mypy and the test suite with coverage. The tests use a bundled Flask mock server, no real NetScaler is required.

## Branches and commits

- Branch naming: `feature/`, `fix/`, `docs/`, `refactor/`
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, ...), releases and the changelog are generated automatically by semantic-release
- Open a pull request against `master`
