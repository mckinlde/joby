"""Diff reporter for asymmetric reachability between two subnet scan results.

This module compares ping results from two /24 subnets and identifies hosts
that are reachable on one subnet but not the other (asymmetric reachability).
It provides human-readable formatting and JSON serialization of the results.

Referenced by:
    - PingScanner (after scan completion)
    - CLI mode (for JSON output)
    - GUI ResultsPanel (for display)
"""

from __future__ import annotations

import json

from ip_range_ping_diff.models import (
    AsymmetricDiff,
    DiffEntry,
    PingResult,
    ReachabilityStatus,
    ScanStats,
)


class DiffReporter:
    """Computes asymmetric reachability between two subnet scan results.

    Given ping results for two subnets (keyed by host octet), identifies
    octets where one subnet is reachable and the other is not, and produces
    structured diff reports.
    """

    def compute_diff(
        self,
        results_a: dict[int, PingResult],
        results_b: dict[int, PingResult],
    ) -> AsymmetricDiff:
        """Compute asymmetric differences between two subnet results.

        For each octet present in both result dictionaries, checks if one
        subnet reports REACHABLE while the other reports UNREACHABLE. Such
        octets are classified as asymmetric and added to the appropriate
        direction list.

        Args:
            results_a: Mapping of host octet to PingResult for subnet A.
            results_b: Mapping of host octet to PingResult for subnet B.

        Returns:
            AsymmetricDiff containing hosts reachable on one subnet only.
            only_in_a: octets reachable in A but unreachable in B.
            only_in_b: octets reachable in B but unreachable in A.
        """
        only_in_a: list[DiffEntry] = []
        only_in_b: list[DiffEntry] = []

        # Check all octets present in both result sets
        common_octets = sorted(set(results_a.keys()) & set(results_b.keys()))

        for octet in common_octets:
            result_a = results_a[octet]
            result_b = results_b[octet]

            a_reachable = result_a.status == ReachabilityStatus.REACHABLE
            b_reachable = result_b.status == ReachabilityStatus.REACHABLE

            if a_reachable and not b_reachable:
                # Reachable on subnet A only
                only_in_a.append(
                    DiffEntry(
                        octet=octet,
                        reachable_ip=result_a.ip_address,
                        unreachable_ip=result_b.ip_address,
                        reachable_subnet=result_a.subnet,
                        unreachable_subnet=result_b.subnet,
                    )
                )
            elif b_reachable and not a_reachable:
                # Reachable on subnet B only
                only_in_b.append(
                    DiffEntry(
                        octet=octet,
                        reachable_ip=result_b.ip_address,
                        unreachable_ip=result_a.ip_address,
                        reachable_subnet=result_b.subnet,
                        unreachable_subnet=result_a.subnet,
                    )
                )

        return AsymmetricDiff(only_in_a=only_in_a, only_in_b=only_in_b)

    def format_report(self, diff: AsymmetricDiff, stats: ScanStats) -> str:
        """Format the diff as a human-readable report string.

        The report is grouped by direction:
        - Hosts reachable only on subnet A
        - Hosts reachable only on subnet B
        - Summary statistics

        Args:
            diff: The computed asymmetric diff to format.
            stats: Scan statistics to include in the report.

        Returns:
            A multi-line human-readable string representation of the diff.
        """
        lines: list[str] = []

        lines.append("=" * 60)
        lines.append("ASYMMETRIC REACHABILITY REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Section: Reachable only on subnet A
        lines.append(f"--- Reachable only on subnet A ({len(diff.only_in_a)} hosts) ---")
        if diff.only_in_a:
            for entry in diff.only_in_a:
                lines.append(
                    f"  Octet {entry.octet}: "
                    f"{entry.reachable_ip} (reachable) vs "
                    f"{entry.unreachable_ip} (unreachable)"
                )
        else:
            lines.append("  (none)")
        lines.append("")

        # Section: Reachable only on subnet B
        lines.append(f"--- Reachable only on subnet B ({len(diff.only_in_b)} hosts) ---")
        if diff.only_in_b:
            for entry in diff.only_in_b:
                lines.append(
                    f"  Octet {entry.octet}: "
                    f"{entry.reachable_ip} (reachable) vs "
                    f"{entry.unreachable_ip} (unreachable)"
                )
        else:
            lines.append("  (none)")
        lines.append("")

        # Summary statistics
        lines.append("--- Statistics ---")
        lines.append(f"  Total hosts scanned: {stats.total_hosts_scanned}")
        lines.append(f"  Reachable on A: {stats.hosts_reachable_a}")
        lines.append(f"  Reachable on B: {stats.hosts_reachable_b}")
        lines.append(f"  Unreachable on A: {stats.hosts_unreachable_a}")
        lines.append(f"  Unreachable on B: {stats.hosts_unreachable_b}")
        lines.append(f"  Asymmetric differences: {stats.asymmetric_count}")
        lines.append(f"  Scan duration: {stats.duration_seconds:.3f}s")
        lines.append(f"  Min delay: {_format_delay(stats.min_delay_ms)}")
        lines.append(f"  Median delay: {_format_delay(stats.median_delay_ms)}")
        lines.append(f"  Mode delay: {_format_delay(stats.mode_delay_ms)}")
        lines.append(f"  Max delay: {_format_delay(stats.max_delay_ms)}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_json(self, diff: AsymmetricDiff, stats: ScanStats) -> str:
        """Serialize diff and stats to a JSON string for CLI output.

        Produces a valid JSON document containing the asymmetric IP entries
        and all scan metrics. Each DiffEntry includes full IP addresses.

        Args:
            diff: The computed asymmetric diff to serialize.
            stats: Scan statistics to include in the output.

        Returns:
            A valid JSON string representing the diff and stats.
        """
        # Serialize diff entries
        only_in_a_list = [
            {
                "octet": entry.octet,
                "reachable_ip": entry.reachable_ip,
                "unreachable_ip": entry.unreachable_ip,
                "reachable_subnet": entry.reachable_subnet,
                "unreachable_subnet": entry.unreachable_subnet,
            }
            for entry in diff.only_in_a
        ]

        only_in_b_list = [
            {
                "octet": entry.octet,
                "reachable_ip": entry.reachable_ip,
                "unreachable_ip": entry.unreachable_ip,
                "reachable_subnet": entry.reachable_subnet,
                "unreachable_subnet": entry.unreachable_subnet,
            }
            for entry in diff.only_in_b
        ]

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
            "asymmetric_diff": {
                "only_in_a": only_in_a_list,
                "only_in_b": only_in_b_list,
                "total_differences": diff.total_differences,
            },
            "stats": stats_dict,
        }

        return json.dumps(output, indent=2)


def _format_delay(delay_ms: float | None) -> str:
    """Format a delay value for display, handling None gracefully.

    Args:
        delay_ms: Delay in milliseconds, or None if no data available.

    Returns:
        Formatted string like "1.234ms" or "N/A".
    """
    if delay_ms is None:
        return "N/A"
    return f"{delay_ms:.3f}ms"
