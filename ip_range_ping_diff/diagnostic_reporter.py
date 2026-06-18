"""Diagnostic reporter for advanced scan mode results.

This module formats and serializes results from the three advanced diagnostic
scan modes (Packet Loss, Jitter, Response Under Load) for both human-readable
display and JSON output in CLI mode.

Referenced by:
    - PingScanner (after diagnostic scan completion)
    - CLI mode (for JSON output of diagnostic results)
    - GUI ResultsPanel (for per-host diagnostic display)

Requirements: 12.12, 6.3
"""

from __future__ import annotations

import json
from dataclasses import asdict

from ip_range_ping_diff.models import (
    DiagnosticResult,
    JitterResult,
    LoadClassification,
    LoadResult,
    PacketLossResult,
    ScanMode,
    ScanStats,
)


class DiagnosticReporter:
    """Formats and serializes advanced diagnostic scan results.

    Provides human-readable table formatting for each diagnostic mode
    and JSON serialization for CLI output. Each format method produces
    a multi-line string suitable for terminal or GUI display.
    """

    def format_packet_loss_report(
        self, results: dict[int, PacketLossResult], subnet: str
    ) -> str:
        """Format packet loss results as a human-readable table.

        Produces a table with columns for octet, IP address, sent/received
        counts, and loss percentage. Results are sorted by octet.

        Args:
            results: Mapping of host octet to PacketLossResult.
            subnet: The subnet prefix string for the report header.

        Returns:
            A multi-line string with a formatted table of packet loss data.
        """
        lines: list[str] = []

        lines.append("=" * 70)
        lines.append(f"PACKET LOSS REPORT — {subnet}")
        lines.append("=" * 70)
        lines.append("")
        lines.append(
            f"{'Octet':<7}{'IP Address':<20}{'Sent':<6}{'Recv':<6}{'Loss %':<10}"
        )
        lines.append("-" * 49)

        for octet in sorted(results.keys()):
            result = results[octet]
            lines.append(
                f"{result.octet:<7}"
                f"{result.ip_address:<20}"
                f"{result.sent:<6}"
                f"{result.received:<6}"
                f"{result.loss_percent:.1f}%"
            )

        lines.append("")
        lines.append(f"Total hosts: {len(results)}")
        lines.append("=" * 70)

        return "\n".join(lines)

    def format_jitter_report(
        self, results: dict[int, JitterResult], subnet: str
    ) -> str:
        """Format jitter results as a human-readable table.

        Produces a table with columns for octet, IP address, sent/received
        counts, and response time statistics (min, avg, max, stddev).
        Values are displayed as "N/A" when insufficient responses exist.

        Args:
            results: Mapping of host octet to JitterResult.
            subnet: The subnet prefix string for the report header.

        Returns:
            A multi-line string with a formatted table of jitter data.
        """
        lines: list[str] = []

        lines.append("=" * 80)
        lines.append(f"JITTER REPORT — {subnet}")
        lines.append("=" * 80)
        lines.append("")
        lines.append(
            f"{'Octet':<7}{'IP Address':<20}"
            f"{'Min(ms)':<10}{'Avg(ms)':<10}{'Max(ms)':<10}{'StdDev(ms)':<12}"
        )
        lines.append("-" * 69)

        for octet in sorted(results.keys()):
            result = results[octet]
            min_str = _format_ms(result.min_ms)
            avg_str = _format_ms(result.avg_ms)
            max_str = _format_ms(result.max_ms)
            stddev_str = _format_ms(result.stddev_ms)
            lines.append(
                f"{result.octet:<7}"
                f"{result.ip_address:<20}"
                f"{min_str:<10}"
                f"{avg_str:<10}"
                f"{max_str:<10}"
                f"{stddev_str:<12}"
            )

        lines.append("")
        lines.append(f"Total hosts: {len(results)}")
        lines.append("=" * 80)

        return "\n".join(lines)

    def format_load_report(
        self, results: dict[int, LoadResult], subnet: str
    ) -> str:
        """Format response-under-load results as a human-readable table.

        Produces a table with columns for octet, IP address, received/sent
        counts, and load classification (DOWN, DEGRADED, HEALTHY).

        Args:
            results: Mapping of host octet to LoadResult.
            subnet: The subnet prefix string for the report header.

        Returns:
            A multi-line string with a formatted table of load test data.
        """
        lines: list[str] = []

        lines.append("=" * 70)
        lines.append(f"RESPONSE UNDER LOAD REPORT — {subnet}")
        lines.append("=" * 70)
        lines.append("")
        lines.append(
            f"{'Octet':<7}{'IP Address':<20}"
            f"{'Recv/Sent':<12}{'Classification':<15}"
        )
        lines.append("-" * 54)

        for octet in sorted(results.keys()):
            result = results[octet]
            recv_sent = f"{result.burst_received}/{result.burst_sent}"
            lines.append(
                f"{result.octet:<7}"
                f"{result.ip_address:<20}"
                f"{recv_sent:<12}"
                f"{result.classification.value.upper():<15}"
            )

        lines.append("")
        lines.append(f"Total hosts: {len(results)}")
        lines.append("=" * 70)

        return "\n".join(lines)

    def to_json(
        self,
        results: dict[int, DiagnosticResult],
        mode: ScanMode,
        subnet: str,
        stats: ScanStats,
    ) -> str:
        """Serialize diagnostic results to a JSON string for CLI output.

        Produces a valid JSON document containing the scan mode, subnet,
        per-host diagnostic metrics, and scan statistics. Each host entry
        includes the IP address, octet, and mode-specific metrics.

        Args:
            results: Mapping of host octet to DiagnosticResult (any of the
                     three diagnostic result types).
            mode: The scan mode that produced these results.
            subnet: The subnet prefix string.
            stats: Scan statistics to include in the output.

        Returns:
            A valid JSON string representing the diagnostic results and stats.
        """
        # Serialize per-host results
        hosts_list = []
        for octet in sorted(results.keys()):
            result = results[octet]
            host_entry = _serialize_diagnostic_result(result)
            hosts_list.append(host_entry)

        # Serialize stats
        stats_dict = {
            "total_hosts_scanned": stats.total_hosts_scanned,
            "hosts_reachable_a": stats.hosts_reachable_a,
            "hosts_reachable_b": stats.hosts_reachable_b,
            "hosts_unreachable_a": stats.hosts_unreachable_a,
            "hosts_unreachable_b": stats.hosts_unreachable_b,
            "asymmetric_count": stats.asymmetric_count,
            "duration_seconds": stats.duration_seconds,
            "min_delay_ms": stats.min_delay_ms,
            "median_delay_ms": stats.median_delay_ms,
            "mode_delay_ms": stats.mode_delay_ms,
            "max_delay_ms": stats.max_delay_ms,
        }

        output = {
            "mode": mode.value,
            "subnet": subnet,
            "hosts": hosts_list,
            "stats": stats_dict,
        }

        return json.dumps(output, indent=2)


def _serialize_diagnostic_result(result: DiagnosticResult) -> dict:
    """Serialize a single diagnostic result to a dictionary.

    Handles each diagnostic result type with appropriate field mapping.
    Enum values are converted to their string representations.

    Args:
        result: A PacketLossResult, JitterResult, or LoadResult instance.

    Returns:
        A dictionary suitable for JSON serialization.
    """
    if isinstance(result, PacketLossResult):
        return {
            "ip_address": result.ip_address,
            "octet": result.octet,
            "subnet": result.subnet,
            "sent": result.sent,
            "received": result.received,
            "loss_percent": result.loss_percent,
        }
    elif isinstance(result, JitterResult):
        return {
            "ip_address": result.ip_address,
            "octet": result.octet,
            "subnet": result.subnet,
            "sent": result.sent,
            "received": result.received,
            "min_ms": result.min_ms,
            "avg_ms": result.avg_ms,
            "max_ms": result.max_ms,
            "stddev_ms": result.stddev_ms,
        }
    elif isinstance(result, LoadResult):
        return {
            "ip_address": result.ip_address,
            "octet": result.octet,
            "subnet": result.subnet,
            "burst_sent": result.burst_sent,
            "burst_received": result.burst_received,
            "burst_interval": result.burst_interval,
            "classification": result.classification.value,
        }
    else:
        # Fallback: use dataclass asdict (shouldn't reach here for valid input)
        return asdict(result)


def _format_ms(value: float | None) -> str:
    """Format a millisecond value for table display, handling None.

    Args:
        value: A value in milliseconds, or None if not available.

    Returns:
        Formatted string like "1.234" or "N/A".
    """
    if value is None:
        return "N/A"
    return f"{value:.3f}"
