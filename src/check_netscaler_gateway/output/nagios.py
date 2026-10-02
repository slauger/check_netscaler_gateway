"""
Nagios/Icinga plugin output formatter
"""

from typing import Any, Dict, List, Optional

from check_netscaler_gateway.constants import SHORTNAME, STATE_NAMES


class NagiosOutput:
    """Format output according to Nagios plugin guidelines"""

    @staticmethod
    def format_output(
        status: int,
        message: str,
        perfdata: Optional[Dict[str, Any]] = None,
        long_output: Optional[List[str]] = None,
    ) -> str:
        """
        Format complete plugin output

        Format:
            SHORTNAME STATUS_NAME - message | perfdata
            long_output_line_1
        """
        status_name = STATE_NAMES.get(status, "UNKNOWN")
        output_parts = [f"{SHORTNAME} {status_name} - {message}"]

        if perfdata:
            perfdata_str = NagiosOutput.format_perfdata(perfdata)
            if perfdata_str:
                output_parts[0] += f" | {perfdata_str}"

        if long_output:
            output_parts.extend(long_output)

        return "\n".join(output_parts)

    @staticmethod
    def format_perfdata(data: Dict[str, Any]) -> str:
        """
        Format performance data according to Nagios format

        Format:
            'label'=value[UOM];[warn];[crit];[min];[max]
        """
        if not data:
            return ""

        perfdata_parts = []

        for label, value in data.items():
            if isinstance(value, dict):
                perfdata_parts.append(
                    NagiosOutput.format_perfdata_item(
                        label=label,
                        value=value.get("value", ""),
                        uom=value.get("uom", ""),
                        warn=value.get("warn"),
                        crit=value.get("crit"),
                        min_val=value.get("min"),
                        max_val=value.get("max"),
                    )
                )
            else:
                perfdata_parts.append(f"'{label}'={value};;")

        return " ".join(perfdata_parts)

    @staticmethod
    def format_perfdata_item(
        label: str,
        value: Any,
        uom: str = "",
        warn: Optional[str] = None,
        crit: Optional[str] = None,
        min_val: Optional[str] = None,
        max_val: Optional[str] = None,
    ) -> str:
        """Format a single performance data item"""
        perfdata = f"'{label}'={value}{uom}"

        thresholds = [
            warn or "",
            crit or "",
            min_val or "",
            max_val or "",
        ]

        if any(thresholds):
            perfdata += ";" + ";".join(thresholds)

        return perfdata
