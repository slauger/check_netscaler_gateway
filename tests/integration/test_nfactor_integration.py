"""
Integration tests for the nFactor authentication flow (13.1+ firmware)
"""

import pytest

from check_netscaler_gateway.check import run_check
from check_netscaler_gateway.client.exceptions import (
    GatewayAuthenticationError,
    UnexpectedResponseError,
    UnsupportedAuthFlowError,
)
from check_netscaler_gateway.client.session import GatewaySession
from check_netscaler_gateway.constants import STATE_OK
from tests.integration.test_classic_integration import make_session


class TestNFactorFlow:
    def test_auto_detection(self, mock_nfactor_server):
        result = run_check(make_session(mock_nfactor_server))
        assert result.status == STATE_OK
        assert "Admin Desktop;" in result.message
        assert result.perfdata["resources"]["value"] == 5

    def test_explicit_nfactor_mode(self, mock_nfactor_server):
        result = run_check(make_session(mock_nfactor_server), auth_mode="nfactor")
        assert result.status == STATE_OK

    def test_wrong_credentials(self, mock_nfactor_server):
        session = make_session(mock_nfactor_server, password="wrong")
        with pytest.raises(GatewayAuthenticationError, match="Incorrect user name or password"):
            run_check(session)

    def test_multifactor_setup_is_unsupported(self, mock_nfactor_server):
        mock_nfactor_server.multifactor = True
        with pytest.raises(UnsupportedAuthFlowError, match="multi-factor"):
            run_check(make_session(mock_nfactor_server))

    def test_unsupported_first_factor(self, mock_nfactor_server):
        mock_nfactor_server.multifactor = "first-factor"
        with pytest.raises(UnsupportedAuthFlowError, match="passcode"):
            run_check(make_session(mock_nfactor_server))

    def test_nfactor_mode_against_classic_gateway(self, mock_classic_server):
        with pytest.raises(GatewayAuthenticationError, match="404"):
            run_check(make_session(mock_classic_server), auth_mode="nfactor")

    def test_broken_resources_json(self, mock_nfactor_server):
        mock_nfactor_server.broken_resources_json = True
        with pytest.raises(UnexpectedResponseError, match="invalid JSON"):
            run_check(make_session(mock_nfactor_server))


class TestDebugMasking:
    def test_debug_output_masks_password(self, mock_nfactor_server, capsys):
        session = GatewaySession(
            hostname=mock_nfactor_server.host,
            username=mock_nfactor_server.username,
            password=mock_nfactor_server.password,
            store=mock_nfactor_server.store,
            ssl=False,
            port=mock_nfactor_server.port,
            debug=True,
        )
        run_check(session)
        captured = capsys.readouterr()
        assert mock_nfactor_server.password not in captured.err
        assert "passwd=********" in captured.err

    def test_verbose_output(self, mock_nfactor_server, capsys):
        session = GatewaySession(
            hostname=mock_nfactor_server.host,
            username=mock_nfactor_server.username,
            password=mock_nfactor_server.password,
            store=mock_nfactor_server.store,
            ssl=False,
            port=mock_nfactor_server.port,
            verbose=True,
        )
        run_check(session)
        captured = capsys.readouterr()
        assert "** POST" in captured.err
        assert "/Resources/List ==> 200" in captured.err
