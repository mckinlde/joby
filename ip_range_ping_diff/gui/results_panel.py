"""Results panel for displaying scan output.

This module provides the ResultsPanel widget that displays:
- Asymmetric IP list grouped by direction (only in A / only in B)
- Scan metrics: total runtime, min/median/mode/max delay
- Per-host diagnostic results for advanced modes (loss%, jitter, burst)

Uses a read-only QTextEdit with monospace font for aligned tabular output.

Referenced requirements: 8.7, 8.8, 8.19
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from ip_range_ping_diff.models import (
    AsymmetricDiff,
    DiagnosticResult,
    JitterResult,
    LoadResult,
    PacketLossResult,
    ScanMode,
    ScanStats,
)


class ResultsPanel(QWidget):
    """Results panel displaying scan output in a read-only text area.

    Provides methods to update the display with asymmetric reachability
    results, scan metrics, and per-host diagnostic data for advanced modes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the results panel with an empty read-only text area."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the results panel layout."""
        layout = QVBoxLayout(self)

        # Header label
        self._header_label = QLabel("Results")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(12)
        self._header_label.setFont(header_font)
        layout.addWidget(self._header_label)

        # Read-only text area with monospace font for aligned output
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        mono_font = QFont("Courier New", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_edit.setFont(mono_font)
        self._text_edit.setPlaceholderText(
            "Scan results will appear here after a scan completes."
        )
        layout.addWidget(self._text_edit)

    def clear(self) -> None:
        """Clear all displayed results."""
        self._text_edit.clear()

    def set_asymmetric_results(self, diff: AsymmetricDiff) -> None:
        """Display asymmetric IP list grouped by direction.

        Shows hosts reachable only on subnet A and hosts reachable only
        on subnet B in separate sections.

        Args:
            diff: The AsymmetricDiff containing only_in_a and only_in_b lists.
        """
        lines: list[str] = []

        lines.append("=" * 60)
        lines.append("ASYMMETRIC REACHABILITY REPORT")
        lines.append("=" * 60)
        lines.append("")

        if not diff.has_differences:
            lines.append("No asymmetric differences found.")
            lines.append("All scanned hosts have symmetric reachability.")
        else:
            lines.append(
                f"Total asymmetric differences: {diff.total_differences}"
            )
            lines.append("")

            # Hosts reachable only on subnet A
            if diff.only_in_a:
                lines.append(
                    f"--- Reachable only on Subnet A ({len(diff.only_in_a)} hosts) ---"
                )
                lines.append(
                    f"{'Octet':<8}{'Reachable IP':<20}{'Unreachable IP':<20}"
                )
                lines.append("-" * 48)
                for entry in diff.only_in_a:
                    lines.append(
                        f"{entry.octet:<8}"
                        f"{entry.reachable_ip:<20}"
                        f"{entry.unreachable_ip:<20}"
                    )
                lines.append("")

            # Hosts reachable only on subnet B
            if diff.only_in_b:
                lines.append(
                    f"--- Reachable only on Subnet B ({len(diff.only_in_b)} hosts) ---"
                )
                lines.append(
                    f"{'Octet':<8}{'Reachable IP':<20}{'Unreachable IP':<20}"
                )
                lines.append("-" * 48)
                for entry in diff.only_in_b:
                    lines.append(
                        f"{entry.octet:<8}"
                        f"{entry.reachable_ip:<20}"
                        f"{entry.unreachable_ip:<20}"
                    )

        self._text_edit.setPlainText("\n".join(lines))

    def set_metrics(self, stats: ScanStats) -> None:
        """Display scan metrics below the current content.

        Appends metrics section showing total runtime and delay statistics.

        Args:
            stats: The ScanStats containing timing and count information.
        """
        lines: list[str] = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("SCAN METRICS")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Total runtime:       {stats.duration_seconds:.3f} s")
        lines.append(f"Hosts scanned:       {stats.total_hosts_scanned}")
        lines.append(f"Reachable (A):       {stats.hosts_reachable_a}")
        lines.append(f"Reachable (B):       {stats.hosts_reachable_b}")
        lines.append(f"Unreachable (A):     {stats.hosts_unreachable_a}")
        lines.append(f"Unreachable (B):     {stats.hosts_unreachable_b}")
        lines.append(f"Asymmetric count:    {stats.asymmetric_count}")
        lines.append("")
        lines.append("--- Ping Delay Statistics ---")
        lines.append(
            f"  Min delay:    {_format_delay(stats.min_delay_ms)}"
        )
        lines.append(
            f"  Median delay: {_format_delay(stats.median_delay_ms)}"
        )
        lines.append(
            f"  Mode delay:   {_format_delay(stats.mode_delay_ms)}"
        )
        lines.append(
            f"  Max delay:    {_format_delay(stats.max_delay_ms)}"
        )

        # Append to existing content
        current = self._text_edit.toPlainText()
        self._text_edit.setPlainText(current + "\n".join(lines))

    def set_diagnostic_results(
        self,
        results: dict[int, DiagnosticResult],
        mode: ScanMode,
    ) -> None:
        """Display per-host diagnostic results for advanced scan modes.

        Formats results as a table appropriate for the scan mode:
        - Packet Loss: shows loss percentage per host
        - Jitter: shows min/avg/max/stddev per host
        - Response Under Load: shows received/sent and classification

        Args:
            results: Dict mapping octet to DiagnosticResult.
            mode: The ScanMode that produced these results.
        """
        lines: list[str] = []
        lines.append("")
        lines.append("=" * 60)

        if mode == ScanMode.PACKET_LOSS:
            lines.append("PACKET LOSS RESULTS")
            lines.append("=" * 60)
            lines.append("")
            lines.append(
                f"{'Octet':<8}{'IP Address':<20}{'Sent':<6}"
                f"{'Recv':<6}{'Loss %':<10}"
            )
            lines.append("-" * 50)
            for octet in sorted(results.keys()):
                result = results[octet]
                if isinstance(result, PacketLossResult):
                    lines.append(
                        f"{result.octet:<8}"
                        f"{result.ip_address:<20}"
                        f"{result.sent:<6}"
                        f"{result.received:<6}"
                        f"{result.loss_percent:.1f}%"
                    )

        elif mode == ScanMode.JITTER:
            lines.append("JITTER RESULTS")
            lines.append("=" * 60)
            lines.append("")
            lines.append(
                f"{'Octet':<8}{'IP Address':<20}{'Min ms':<10}"
                f"{'Avg ms':<10}{'Max ms':<10}{'StdDev':<10}"
            )
            lines.append("-" * 68)
            for octet in sorted(results.keys()):
                result = results[octet]
                if isinstance(result, JitterResult):
                    min_str = (
                        f"{result.min_ms:.2f}" if result.min_ms is not None
                        else "N/A"
                    )
                    avg_str = (
                        f"{result.avg_ms:.2f}" if result.avg_ms is not None
                        else "N/A"
                    )
                    max_str = (
                        f"{result.max_ms:.2f}" if result.max_ms is not None
                        else "N/A"
                    )
                    std_str = (
                        f"{result.stddev_ms:.2f}"
                        if result.stddev_ms is not None
                        else "N/A"
                    )
                    lines.append(
                        f"{result.octet:<8}"
                        f"{result.ip_address:<20}"
                        f"{min_str:<10}"
                        f"{avg_str:<10}"
                        f"{max_str:<10}"
                        f"{std_str:<10}"
                    )

        elif mode == ScanMode.RESPONSE_UNDER_LOAD:
            lines.append("RESPONSE UNDER LOAD RESULTS")
            lines.append("=" * 60)
            lines.append("")
            lines.append(
                f"{'Octet':<8}{'IP Address':<20}{'Recv/Sent':<12}"
                f"{'Classification':<15}"
            )
            lines.append("-" * 55)
            for octet in sorted(results.keys()):
                result = results[octet]
                if isinstance(result, LoadResult):
                    recv_sent = (
                        f"{result.burst_received}/{result.burst_sent}"
                    )
                    lines.append(
                        f"{result.octet:<8}"
                        f"{result.ip_address:<20}"
                        f"{recv_sent:<12}"
                        f"{result.classification.value:<15}"
                    )

        else:
            lines.append("DIAGNOSTIC RESULTS")
            lines.append("=" * 60)
            lines.append("")
            lines.append("No results to display for this mode.")

        # Append to existing content
        current = self._text_edit.toPlainText()
        self._text_edit.setPlainText(current + "\n".join(lines))

    def set_benchmark_status(self, message: str) -> None:
        """Display a benchmark status message.

        Args:
            message: Status text to display (e.g., "Running benchmark...").
        """
        self._text_edit.setPlainText(message)

    def set_benchmark_results(self, results: dict[str, str]) -> None:
        """Display benchmark comparison results.

        Shows a table of strategies and their timing or error status.

        Args:
            results: Dict mapping strategy name to timing string or error.
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("BENCHMARK RESULTS")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"{'Strategy':<25}{'Result':<35}")
        lines.append("-" * 60)

        for name, result in results.items():
            lines.append(f"{name:<25}{result:<35}")

        lines.append("-" * 60)

        # Find fastest for comparison
        times: list[tuple[str, float]] = []
        for name, result in results.items():
            if result.endswith("s") and not result.startswith("SKIPPED"):
                try:
                    t = float(result.rstrip("s"))
                    times.append((name, t))
                except ValueError:
                    pass

        if times:
            fastest_name, fastest_time = min(times, key=lambda x: x[1])
            lines.append("")
            lines.append(f"Fastest: {fastest_name} ({fastest_time:.3f}s)")
            if len(times) > 1:
                lines.append("")
                lines.append("Relative performance:")
                for name, t in sorted(times, key=lambda x: x[1]):
                    relative = t / fastest_time
                    lines.append(f"  {name:<23} {relative:.2f}x")

        self._text_edit.setPlainText("\n".join(lines))


def _format_delay(value: float | None) -> str:
    """Format a delay value in milliseconds for display.

    Args:
        value: The delay value in ms, or None if not available.

    Returns:
        Formatted string like "1.23 ms" or "N/A".
    """
    if value is None:
        return "N/A"
    return f"{value:.2f} ms"
