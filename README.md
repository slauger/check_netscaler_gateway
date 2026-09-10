# check_netscaler_gateway

[![CI](https://github.com/slauger/check_netscaler_gateway/actions/workflows/lint-and-type-check.yml/badge.svg)](https://github.com/slauger/check_netscaler_gateway/actions/workflows/lint-and-type-check.yml)
[![PyPI version](https://img.shields.io/pypi/v/check_netscaler_gateway)](https://pypi.org/project/check_netscaler_gateway/)
[![Python versions](https://img.shields.io/pypi/pyversions/check_netscaler_gateway)](https://pypi.org/project/check_netscaler_gateway/)
[![License](https://img.shields.io/github/license/slauger/check_netscaler_gateway)](LICENSE-2.0.txt)

Nagios/Icinga monitoring plugin for Citrix NetScaler Gateway. The plugin emulates a full login process on a NetScaler Gateway vServer, authenticates against StoreFront through the gateway and checks if there are any resources (published applications and desktops) available for the monitoring user.

## Features

- 🔑 Simulates a complete end-user login through the gateway, not just a TCP or HTTP check
- 🔀 Supports both authentication flows: classic (`/cgi/login`) and nFactor (firmware 13.1 and later) with automatic detection
- 📦 Lists the published resources and checks minimum thresholds (`-w`/`-c`)
- 📊 Emits performance data (number of available resources)
- 🐍 Pure Python with a single runtime dependency (`requests`), also available as standalone binaries
- 🛠️ Debug mode prints all HTTP requests and responses with credentials masked

## Quick Start

```bash
pip install check_netscaler_gateway

check_netscaler_gateway -H citrix.example.com -u monitoring -p password -S Store
NetScaler Gateway OK - Admin Desktop; CAD Desktop; Calculator; HDX Desktop; | 'resources'=4;;;0;
```

## Usage

```
check_netscaler_gateway -H <hostname> -u <username> -p <password> [-S <store>]
                        [-w <warning>] [-c <critical>] [-t <timeout>]
                        [--auth-mode {auto,classic,nfactor}]
                        [--verify] [--ca-file <path>] [-v] [-d]
```

| Option | Description |
|--------|-------------|
| `-H, --hostname` | Hostname of the NetScaler Gateway vServer (env: `NETSCALER_GATEWAY_HOST`) |
| `-u, --username` | Username for the login simulation (env: `NETSCALER_GATEWAY_USER`) |
| `-p, --password` | Password for the login username (env: `NETSCALER_GATEWAY_PASS`) |
| `-S, --store` | Name of the store in StoreFront (default: `Store`) |
| `-w, --warning` | Warning threshold: minimum number of expected applications |
| `-c, --critical` | Critical threshold: minimum number of expected applications |
| `-t, --timeout` | Request timeout in seconds (default: 15) |
| `--auth-mode` | Authentication flow: `auto` (default), `classic` or `nfactor` |
| `--verify` | Verify TLS certificates (disabled by default, like v1.x) |
| `--ca-file` | Path to a CA bundle for TLS verification |
| `-v, --verbose` | Print one line per HTTP request to stderr |
| `-d, --debug` | Print all HTTP requests and responses to stderr (credentials masked) |

### Authentication flows

The plugin emulates a real browser session: it loads the login page first and sends an `Origin` header with the login request. Firmware builds since 13.1-63.x reject bare `POST /cgi/login` requests without this (redirect to `/vpn/index.html` with `NSC_VPNERR=4001`), which is what broke the Perl version of this plugin. Gateways using the RfWebUI theme speak the nFactor protocol instead of the classic `/cgi/login` flow; the plugin detects this automatically, use `--auth-mode` to pin a flow explicitly. Multi-factor setups (OTP, EULA, more than one factor) are not supported and are reported as UNKNOWN.

## Migration from v1.x (Perl)

The command line options `-H`, `-u`, `-p`, `-S`, `-w`, `-c`, `-t`, `-v` and `-d` are compatible, existing Nagios and Icinga command definitions keep working after replacing `check_netscaler_gateway.pl` with the new binary or console script. TLS certificate verification stays disabled by default; enable it with `--verify` or `--ca-file`.

## Icinga 2

See [examples/icinga2/check_netscaler_gateway.conf](examples/icinga2/check_netscaler_gateway.conf) for a CheckCommand definition.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
make ci
```

The test suite runs against a bundled mock gateway server (Flask) that implements both authentication flows, no real NetScaler required:

```bash
python -m tests.mocks.gateway_server --port 8080 --mode nfactor
```

## License

Licensed under the [Apache License, Version 2.0](LICENSE-2.0.txt).
