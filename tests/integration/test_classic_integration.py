"""
Integration tests for the classic authentication flow
"""

import pytest
import requests

from check_netscaler_gateway.check import run_check
from check_netscaler_gateway.client.exceptions import (
    CsrfTokenError,
    GatewayAuthenticationError,
    GatewayConnectionError,
    UnexpectedResponseError,
)
from check_netscaler_gateway.client.session import GatewaySession
from check_netscaler_gateway.constants import STATE_CRITICAL, STATE_OK, STATE_WARNING


def make_session(server, **kwargs):
    return GatewaySession(
        hostname=server.host,
        username=kwargs.pop("username", server.username),
        password=kwargs.pop("password", server.password),
        store=kwargs.pop("store", server.store),
        ssl=False,
        port=server.port,
        **kwargs,
    )


class TestClassicFlow:
    def test_successful_check(self, mock_classic_server):
        result = run_check(make_session(mock_classic_server))
        assert result.status == STATE_OK
        assert "Admin Desktop;" in result.message
        assert "Calculator;" in result.message
        assert result.perfdata["resources"]["value"] == 5

    def test_explicit_classic_mode(self, mock_classic_server):
        result = run_check(make_session(mock_classic_server), auth_mode="classic")
        assert result.status == STATE_OK

    def test_wrong_credentials(self, mock_classic_server):
        session = make_session(mock_classic_server, password="wrong")
        with pytest.raises(GatewayAuthenticationError, match="/vpn/index.html"):
            run_check(session, auth_mode="classic")

    def test_wrong_credentials_reports_gateway_error_code(self, mock_classic_server):
        session = make_session(mock_classic_server, password="wrong")
        with pytest.raises(GatewayAuthenticationError, match="gateway error code 4001"):
            run_check(session)

    def test_bare_login_post_is_rejected(self, mock_classic_server):
        # the old Perl plugin failed on 13.1-63.x exactly like this: no login
        # page cookies, no Origin header (issue #7)
        response = requests.post(
            f"{mock_classic_server.get_url()}/cgi/login",
            data={
                "login": mock_classic_server.username,
                "passwd": mock_classic_server.password,
            },
            allow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"] == "/vpn/index.html"

    def test_warning_threshold(self, mock_classic_server):
        result = run_check(make_session(mock_classic_server), warning=10)
        assert result.status == STATE_WARNING

    def test_critical_threshold(self, mock_classic_server):
        result = run_check(make_session(mock_classic_server), warning=10, critical=6)
        assert result.status == STATE_CRITICAL

    def test_missing_csrf_token(self, mock_classic_server):
        mock_classic_server.csrf_enabled = False
        with pytest.raises(CsrfTokenError):
            run_check(make_session(mock_classic_server))

    def test_logout_failure_is_warning(self, mock_classic_server):
        mock_classic_server.fail_logout = True
        result = run_check(make_session(mock_classic_server))
        assert result.status == STATE_WARNING
        assert "Logout failed" in result.message

    def test_unknown_store(self, mock_classic_server):
        session = make_session(mock_classic_server, store="DoesNotExist")
        with pytest.raises(UnexpectedResponseError):
            run_check(session)

    def test_connection_refused(self):
        session = GatewaySession(
            hostname="127.0.0.1",
            username="user",
            password="pass",
            ssl=False,
            port=1,
            timeout=2,
        )
        with pytest.raises(GatewayConnectionError):
            run_check(session)
