"""
Tests for the Nagios output formatter
"""

from check_netscaler_gateway.constants import STATE_CRITICAL, STATE_OK
from check_netscaler_gateway.output.nagios import NagiosOutput


class TestNagiosOutput:
    def test_format_output_ok(self):
        output = NagiosOutput.format_output(STATE_OK, "App1; App2;")
        assert output == "NetScaler Gateway OK - App1; App2;"

    def test_format_output_critical(self):
        output = NagiosOutput.format_output(STATE_CRITICAL, "something broke")
        assert output == "NetScaler Gateway CRITICAL - something broke"

    def test_format_output_with_perfdata(self):
        output = NagiosOutput.format_output(
            STATE_OK,
            "App1;",
            perfdata={"resources": {"value": 1, "warn": "2", "crit": "1", "min": "0"}},
        )
        assert output == "NetScaler Gateway OK - App1; | 'resources'=1;2;1;0;"

    def test_format_output_with_long_output(self):
        output = NagiosOutput.format_output(STATE_OK, "ok", long_output=["line1", "line2"])
        assert output == "NetScaler Gateway OK - ok\nline1\nline2"

    def test_format_perfdata_scalar(self):
        assert NagiosOutput.format_perfdata({"count": 5}) == "'count'=5;;"

    def test_format_perfdata_empty(self):
        assert NagiosOutput.format_perfdata({}) == ""

    def test_format_perfdata_item_without_thresholds(self):
        assert NagiosOutput.format_perfdata_item("resources", 3) == "'resources'=3"
