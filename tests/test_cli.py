"""
Tests for the command-line interface
"""

import pytest

from check_netscaler_gateway import __version__, cli
from check_netscaler_gateway.check import CheckResult
from check_netscaler_gateway.cli import create_parser, main
from check_netscaler_gateway.client.exceptions import (
    GatewayAuthenticationError,
    GatewayTimeoutError,
    UnsupportedAuthFlowError,
)
from check_netscaler_gateway.constants import STATE_OK

ARGS = ["-H", "gw.example.com", "-u", "user", "-p", "pass"]


class TestParser:
    def test_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["-H", "gw.example.com", "-u", "user", "-p", "pass"])
        assert args.hostname == "gw.example.com"
        assert args.store == "Store"
        assert args.timeout == 15
        assert args.auth_mode == "auto"
        assert args.verify is False
        assert args.verbose is False
        assert args.debug is False
        assert args.warning is None
        assert args.critical is None

    def test_all_options(self):
        parser = create_parser()
        args = parser.parse_args(
            [
                "-H", "gw.example.com",
                "-u", "user",
                "-p", "pass",
                "-S", "Lab",
                "-w", "5",
                "-c", "2",
                "-t", "30",
                "--auth-mode", "nfactor",
                "--verify",
                "-v",
                "-d",
            ]
        )  # fmt: skip
        assert args.store == "Lab"
        assert args.warning == 5
        assert args.critical == 2
        assert args.timeout == 30
        assert args.auth_mode == "nfactor"
        assert args.verify is True
        assert args.verbose is True
        assert args.debug is True

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            create_parser().parse_args(["--version"])
        assert excinfo.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_invalid_auth_mode(self):
        with pytest.raises(SystemExit):
            create_parser().parse_args(["-H", "gw", "-u", "u", "-p", "p", "--auth-mode", "bogus"])


class TestMain:
    def test_missing_required_arguments(self, monkeypatch):
        for var in ("NETSCALER_GATEWAY_HOST", "NETSCALER_GATEWAY_USER", "NETSCALER_GATEWAY_PASS"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(SystemExit) as excinfo:
            main([])
        assert excinfo.value.code == 2

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("NETSCALER_GATEWAY_HOST", "gw.example.com")
        monkeypatch.setenv("NETSCALER_GATEWAY_USER", "user")
        monkeypatch.setenv("NETSCALER_GATEWAY_PASS", "pass")
        parser = create_parser()
        args = parser.parse_args([])
        assert args.hostname == "gw.example.com"
        assert args.username == "user"
        assert args.password == "pass"

    def test_ok_run(self, monkeypatch, capsys):
        result = CheckResult(STATE_OK, "App1; App2;", perfdata={"resources": 2})
        monkeypatch.setattr(cli, "run_check", lambda session, **kwargs: result)
        assert main(ARGS) == 0
        out = capsys.readouterr().out
        assert out.startswith("NetScaler Gateway OK - App1; App2;")
        assert "'resources'=2;;" in out

    def test_authentication_error_is_critical(self, monkeypatch, capsys):
        def raise_auth_error(session, **kwargs):
            raise GatewayAuthenticationError("authentication failed")

        monkeypatch.setattr(cli, "run_check", raise_auth_error)
        assert main(ARGS) == 2
        assert "NetScaler Gateway CRITICAL - authentication failed" in capsys.readouterr().out

    def test_timeout_is_critical(self, monkeypatch, capsys):
        def raise_timeout(session, **kwargs):
            raise GatewayTimeoutError("request timed out")

        monkeypatch.setattr(cli, "run_check", raise_timeout)
        assert main(ARGS) == 2
        assert "CRITICAL" in capsys.readouterr().out

    def test_unsupported_flow_is_unknown(self, monkeypatch, capsys):
        def raise_unsupported(session, **kwargs):
            raise UnsupportedAuthFlowError("multi-factor setup")

        monkeypatch.setattr(cli, "run_check", raise_unsupported)
        assert main(ARGS) == 3
        assert "NetScaler Gateway UNKNOWN - multi-factor setup" in capsys.readouterr().out

    def test_unexpected_error_is_unknown(self, monkeypatch, capsys):
        def raise_value_error(session, **kwargs):
            raise ValueError("boom")

        monkeypatch.setattr(cli, "run_check", raise_value_error)
        assert main(ARGS) == 3
        assert "UNKNOWN - Unexpected error: boom" in capsys.readouterr().out
