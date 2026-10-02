"""
Tests for the check orchestration (thresholds, logout handling)
"""

import pytest

from check_netscaler_gateway import check
from check_netscaler_gateway.constants import STATE_CRITICAL, STATE_OK, STATE_WARNING


@pytest.fixture
def patched_flow(monkeypatch):
    """Patch login/resources/logout so run_check needs no HTTP"""
    state = {
        "resources": ["App1", "App2", "App3"],
        "logout_ok": True,
    }
    monkeypatch.setattr(check.gateway, "login", lambda session, mode: "classic")
    monkeypatch.setattr(check.storefront, "list_resources", lambda session: state["resources"])
    monkeypatch.setattr(check.gateway, "logout", lambda session: state["logout_ok"])
    return state


class TestRunCheck:
    def test_ok(self, patched_flow):
        result = check.run_check(session=None)
        assert result.status == STATE_OK
        assert result.message == "App1; App2; App3;"
        assert result.perfdata["resources"]["value"] == 3

    def test_warning_threshold(self, patched_flow):
        result = check.run_check(session=None, warning=5)
        assert result.status == STATE_WARNING
        assert "expected at least 5" in result.message

    def test_critical_threshold(self, patched_flow):
        result = check.run_check(session=None, warning=5, critical=4)
        assert result.status == STATE_CRITICAL
        assert "expected at least 4" in result.message

    def test_thresholds_satisfied(self, patched_flow):
        result = check.run_check(session=None, warning=3, critical=2)
        assert result.status == STATE_OK

    def test_zero_resources(self, patched_flow):
        patched_flow["resources"] = []
        result = check.run_check(session=None, critical=1)
        assert result.status == STATE_CRITICAL
        assert result.perfdata["resources"]["value"] == 0

    def test_logout_failure_is_warning(self, patched_flow):
        patched_flow["logout_ok"] = False
        result = check.run_check(session=None)
        assert result.status == STATE_WARNING
        assert "Logout failed" in result.message

    def test_logout_failure_keeps_critical(self, patched_flow):
        patched_flow["logout_ok"] = False
        result = check.run_check(session=None, critical=10)
        assert result.status == STATE_CRITICAL
