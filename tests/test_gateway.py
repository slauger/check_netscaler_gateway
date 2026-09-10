"""
Tests for the nFactor XML handling in the gateway client
"""

import pytest

from check_netscaler_gateway.client import gateway
from check_netscaler_gateway.client.exceptions import (
    GatewayAuthenticationError,
    UnexpectedResponseError,
    UnsupportedAuthFlowError,
)
from tests.mocks.gateway_server import (
    FAILURE_XML,
    MORE_INFO_XML,
    REQUIREMENTS_OTP_XML,
    REQUIREMENTS_XML,
    STATE_CONTEXT,
    SUCCESS_XML,
)


class FakeSession:
    """Just enough session for _check_authentication_result"""

    def __init__(self, cookies=None):
        self._cookies = cookies or {}

    def cookie(self, name):
        return self._cookies.get(name)


class TestParseRequirements:
    def test_username_password_factor(self):
        state_context, postback = gateway._parse_requirements(REQUIREMENTS_XML)
        assert state_context == STATE_CONTEXT
        assert postback == "/nf/auth/doAuthentication.do"

    def test_unsupported_factor(self):
        with pytest.raises(UnsupportedAuthFlowError, match="passcode"):
            gateway._parse_requirements(REQUIREMENTS_OTP_XML)

    def test_invalid_xml(self):
        with pytest.raises(UnexpectedResponseError):
            gateway._parse_requirements("this is not xml")


class TestCheckAuthenticationResult:
    def test_success_with_cookie(self):
        session = FakeSession({"NSC_AAAC": "value"})
        gateway._check_authentication_result(session, SUCCESS_XML)

    def test_success_without_cookie(self):
        with pytest.raises(GatewayAuthenticationError, match="NSC_AAAC"):
            gateway._check_authentication_result(FakeSession(), SUCCESS_XML)

    def test_wrong_credentials(self):
        with pytest.raises(GatewayAuthenticationError, match="Incorrect user name or password"):
            gateway._check_authentication_result(FakeSession(), FAILURE_XML)

    def test_second_factor_requested(self):
        with pytest.raises(UnsupportedAuthFlowError, match="multi-factor"):
            gateway._check_authentication_result(FakeSession(), MORE_INFO_XML)

    def test_invalid_xml(self):
        with pytest.raises(UnexpectedResponseError):
            gateway._check_authentication_result(FakeSession(), "this is not xml")
