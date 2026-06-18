"""Main application window for IP Range Ping Diff.

This module provides the MainWindow (QMainWindow) that composes the
DotGridWidget, ControlPanel, ResultsPanel, and ScanController into
a complete application interface. It handles button signal connections,
real-time dot updates, and scan lifecycle management.

Referenced requirements: 8.4, 8.6, 8.11, 8.12, 8.13, 8.15, 8.19
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ip_range_ping_diff.benchmark.harness import (
    run_bash_benchmark,
    run_c_benchmark,
    run_python_benchmark,
    run_rust_benchmark,
)
from ip_range_ping_diff.diff_reporter import DiffReporter
from ip_range_ping_diff.gui.color_legend import ColorLegend
from ip_range_ping_diff.gui.control_panel import ControlPanel
from ip_range_ping_diff.gui.dot_grid import DotGridWidget
from ip_range_ping_diff.gui.results_panel import ResultsPanel
from ip_range_ping_diff.gui.scan_controller import ScanController
from ip_range_ping_diff.models import (
    DiagnosticResult,
    DotStatus,
    PacketLossResult,
    PingResult,
    ReachabilityStatus,
    ScanMode,
    ScanResults,
)


class MainWindow(QMainWindow):
    """Primary application window.

    Composes the dot grid (left), control panel (right), and results
    panel (bottom) into a unified layout. Connects button signals to
    scan initiation, handles real-time dot updates via ScanController
    signals, and manages button state during scans.
    """

    def __init__(self) -> None:
        """Initialize window with dot grid, control panel, and results panel."""
        super().__init__()
        self.setWindowTitle("IP Range Ping Diff")
        self.setMinimumSize(900, 700)

        # Track ping results by octet for dot status determination
        self._results_a: dict[int, ReachabilityStatus] = {}
        self._results_b: dict[int, ReachabilityStatus] = {}

        # Create the scan controller
        self._scan_controller = ScanController(self)

        # Build UI components
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Build the main window layout.

        Layout structure:
            ┌──────────────────────────────┐
            │  [DotGrid]  │  [ControlPanel] │
            │             │                 │
            ├─────────────┴─────────────────┤
            │         [ResultsPanel]        │
            └───────────────────────────────┘
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout: top section + results panel
        main_layout = QVBoxLayout(central_widget)

        # Top section: dot grid (left) + control panel (right)
        top_layout = QHBoxLayout()

        # Left column: dot grid + color legend
        left_layout = QVBoxLayout()
        self._dot_grid = DotGridWidget()
        left_layout.addWidget(self._dot_grid)

        # Color legend below the dot grid
        self._color_legend = ColorLegend()
        left_layout.addWidget(self._color_legend)

        top_layout.addLayout(left_layout)

        # Control panel
        self._control_panel = ControlPanel()
        top_layout.addWidget(self._control_panel)

        main_layout.addLayout(top_layout)

        # Results panel below both
        self._results_panel = ResultsPanel()
        main_layout.addWidget(self._results_panel)

    def _connect_signals(self) -> None:
        """Connect control panel buttons and scan controller signals."""
        # Button signals → scan initiation
        self._control_panel.ping_once_clicked.connect(self._on_ping_once)
        self._control_panel.ping_retry_clicked.connect(self._on_ping_retry)
        self._control_panel.sequential_clicked.connect(self._on_sequential)
        self._control_panel.sequential_loop_clicked.connect(self._on_sequential_loop)
        self._control_panel.packet_loss_clicked.connect(self._on_packet_loss)
        self._control_panel.jitter_clicked.connect(self._on_jitter)
        self._control_panel.response_under_load_clicked.connect(
            self._on_response_under_load
        )

        # Benchmark button signals
        self._control_panel.bench_python_clicked.connect(
            lambda: self._run_benchmark("python")
        )
        self._control_panel.bench_bash_clicked.connect(
            lambda: self._run_benchmark("bash")
        )
        self._control_panel.bench_c_clicked.connect(
            lambda: self._run_benchmark("c")
        )
        self._control_panel.bench_rust_clicked.connect(
            lambda: self._run_benchmark("rust")
        )
        self._control_panel.bench_all_clicked.connect(
            lambda: self._run_benchmark("all")
        )

        # Scan controller signals → UI updates
        self._scan_controller.result_received.connect(
            self._on_result_received
        )
        self._scan_controller.diagnostic_result_received.connect(
            self._on_diagnostic_result_received
        )
        self._scan_controller.scan_completed.connect(
            self._on_scan_completed
        )
        self._scan_controller.scan_error.connect(self._on_scan_error)

    # --- Scan Initiation Methods ---

    def _on_ping_once(self) -> None:
        """Handle Ping Once button click."""
        self._start_scan(ScanMode.PING_ONCE)

    def _on_ping_retry(self) -> None:
        """Handle Ping Retry button click."""
        self._start_scan(ScanMode.PING_RETRY)

    def _on_sequential(self) -> None:
        """Handle Sequential button click."""
        self._start_scan(ScanMode.SEQUENTIAL)

    def _on_sequential_loop(self) -> None:
        """Handle Sequential Loop button click."""
        self._start_scan(ScanMode.SEQUENTIAL_LOOP)

    def _on_packet_loss(self) -> None:
        """Handle Packet Loss button click."""
        self._start_scan(ScanMode.PACKET_LOSS)

    def _on_jitter(self) -> None:
        """Handle Jitter button click."""
        self._start_scan(ScanMode.JITTER)

    def _on_response_under_load(self) -> None:
        """Handle Response Under Load button click."""
        self._start_scan(ScanMode.RESPONSE_UNDER_LOAD)

    def _run_benchmark(self, strategy: str) -> None:
        """Run a benchmark for the specified language/strategy.

        Runs on a background thread to keep the GUI responsive.
        Results are displayed in the results panel.

        Args:
            strategy: One of "python", "bash", "c", "rust", or "all".
        """
        import threading

        # Extract subnet prefixes from the GUI fields
        subnet_a = self._control_panel.get_subnet_a().split(".0/24")[0]
        subnet_b = self._control_panel.get_subnet_b().split(".0/24")[0]

        self._set_buttons_enabled(False)
        self._results_panel.clear()
        self._results_panel.set_benchmark_status("Running benchmark...")

        def _worker() -> None:
            results: dict[str, float | str] = {}
            strategies = {
                "python": ("Python (subprocess)", run_python_benchmark),
                "bash": ("Bash (xargs)", run_bash_benchmark),
                "c": ("C (fork/exec)", run_c_benchmark),
                "rust": ("Rust (threads)", run_rust_benchmark),
            }

            if strategy == "all":
                targets = list(strategies.items())
            else:
                targets = [(strategy, strategies[strategy])]

            for key, (name, runner) in targets:
                try:
                    elapsed = runner(subnet_a, subnet_b)
                    results[name] = f"{elapsed:.3f}s"
                except (FileNotFoundError, RuntimeError) as e:
                    results[name] = f"SKIPPED ({e})"

            # Update GUI from main thread via signal-safe approach
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            # Use a simple approach: store results and trigger update
            self._bench_results = results
            QMetaObject.invokeMethod(
                self, "_on_benchmark_done", Qt.ConnectionType.QueuedConnection
            )

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    @Slot()
    def _on_benchmark_done(self) -> None:
        """Handle benchmark completion — update UI with results."""
        results = getattr(self, "_bench_results", {})
        self._results_panel.set_benchmark_results(results)
        self._set_buttons_enabled(True)

    def _start_scan(self, mode: ScanMode) -> None:
        """Initiate a scan with the given mode using control panel values.

        Resets the dot grid, clears previous results, disables buttons,
        updates the color legend, and starts the scan on the background thread.

        Args:
            mode: The ScanMode to use for this scan.
        """
        # Reset state for new scan
        self._dot_grid.reset()
        self._results_panel.clear()
        self._results_a.clear()
        self._results_b.clear()

        # Update color legend to reflect current mode
        self._color_legend.set_mode(mode)

        # Disable buttons during scan
        self._set_buttons_enabled(False)

        # Read parameters from control panel
        self._scan_controller.start_scan(
            subnet_a=self._control_panel.get_subnet_a(),
            subnet_b=self._control_panel.get_subnet_b(),
            excluded_octets=self._control_panel.get_excluded_octets(),
            thread_count=self._control_panel.get_thread_count(),
            timeout=self._control_panel.get_timeout(),
            retries=self._control_panel.get_retry_count(),
            retry_delay_ms=self._control_panel.get_retry_delay_ms(),
            scan_mode=mode,
            ping_count=self._control_panel.get_ping_count(),
            burst_count=self._control_panel.get_burst_count(),
            burst_interval=self._control_panel.get_burst_interval(),
        )

    # --- Real-time Update Handlers ---

    def _on_result_received(self, result: PingResult) -> None:
        """Update dot colors in real time as ping results arrive.

        Determines the DotStatus based on whether both subnets have
        reported for the same octet. If only one subnet has reported,
        the dot remains in a transitional state until both are available.

        Args:
            result: The PingResult that just arrived.
        """
        octet = result.octet
        subnet_prefix = result.subnet

        # Track which subnet this result belongs to
        if subnet_prefix == self._control_panel.get_subnet_a().split("/")[0].rsplit(".", 1)[0]:
            self._results_a[octet] = result.status
        else:
            self._results_b[octet] = result.status

        # Determine dot status based on available results
        status = self._compute_dot_status(octet)
        self._dot_grid.update_dot(octet, status)

    def _on_diagnostic_result_received(
        self, result: DiagnosticResult
    ) -> None:
        """Update dot colors with gradient/threshold for diagnostic modes.

        For Packet Loss mode, maps loss_percent to LOSS_NONE/LOSS_LOW/
        LOSS_HIGH/LOSS_TOTAL. For other diagnostic modes, uses a simple
        reachability mapping.

        Args:
            result: The DiagnosticResult that just arrived.
        """
        octet = result.octet

        if isinstance(result, PacketLossResult):
            # Map packet loss percentage to dot status
            status = self._loss_percent_to_status(result.loss_percent)
        else:
            # For Jitter and Load modes, use a basic mapping:
            # If we got any response data, show as green; otherwise white
            status = DotStatus.REACHABLE_BOTH

        self._dot_grid.update_dot(octet, status)

    def _on_scan_completed(self, results: ScanResults) -> None:
        """Display final results and metrics when scan completes.

        For ping modes, computes and displays the asymmetric diff.
        For diagnostic modes, displays per-host diagnostic results.
        Always displays scan metrics and re-enables buttons.

        Args:
            results: The complete ScanResults from the scan.
        """
        # Determine mode category
        diagnostic_modes = {
            ScanMode.PACKET_LOSS,
            ScanMode.JITTER,
            ScanMode.RESPONSE_UNDER_LOAD,
        }

        if results.scan_mode in diagnostic_modes:
            # Display diagnostic results for subnet A
            if results.diagnostic_results_a:
                self._results_panel.set_diagnostic_results(
                    results.diagnostic_results_a,
                    results.scan_mode,
                )
            # Display diagnostic results for subnet B
            if results.diagnostic_results_b:
                self._results_panel.set_diagnostic_results(
                    results.diagnostic_results_b,
                    results.scan_mode,
                )
        else:
            # Compute and display asymmetric diff for ping modes
            reporter = DiffReporter()
            diff = reporter.compute_diff(results.results_a, results.results_b)
            self._results_panel.set_asymmetric_results(diff)

        # Display metrics
        if results.stats is not None:
            self._results_panel.set_metrics(results.stats)

        # Re-enable buttons
        self._set_buttons_enabled(True)

    def _on_scan_error(self, error_message: str) -> None:
        """Handle scan error by showing a message and re-enabling buttons.

        Args:
            error_message: Description of the error that occurred.
        """
        QMessageBox.critical(self, "Scan Error", error_message)
        self._set_buttons_enabled(True)

    # --- Helper Methods ---

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all scan buttons.

        Delegates to the ControlPanel's set_buttons_enabled method.

        Args:
            enabled: True to enable buttons, False to disable.
        """
        self._control_panel.set_buttons_enabled(enabled)

    def _compute_dot_status(self, octet: int) -> DotStatus:
        """Compute the DotStatus for an octet based on available results.

        If both subnets have reported:
            - Both REACHABLE → GREEN
            - Both UNREACHABLE → WHITE
            - One reachable, one not → RED (asymmetric)
        If only one subnet has reported, show a temporary status based
        on what's known so far.

        Args:
            octet: The host octet to compute status for.

        Returns:
            The appropriate DotStatus for this octet.
        """
        has_a = octet in self._results_a
        has_b = octet in self._results_b

        if has_a and has_b:
            status_a = self._results_a[octet]
            status_b = self._results_b[octet]

            if (
                status_a == ReachabilityStatus.REACHABLE
                and status_b == ReachabilityStatus.REACHABLE
            ):
                return DotStatus.REACHABLE_BOTH
            elif (
                status_a == ReachabilityStatus.UNREACHABLE
                and status_b == ReachabilityStatus.UNREACHABLE
            ):
                return DotStatus.UNREACHABLE_BOTH
            else:
                return DotStatus.ASYMMETRIC
        elif has_a:
            # Only subnet A reported so far - show partial status
            if self._results_a[octet] == ReachabilityStatus.REACHABLE:
                return DotStatus.REACHABLE_BOTH  # Tentative green
            else:
                return DotStatus.UNREACHABLE_BOTH  # Tentative white
        elif has_b:
            # Only subnet B reported so far - show partial status
            if self._results_b[octet] == ReachabilityStatus.REACHABLE:
                return DotStatus.REACHABLE_BOTH  # Tentative green
            else:
                return DotStatus.UNREACHABLE_BOTH  # Tentative white
        else:
            return DotStatus.NOT_SCANNED

    @staticmethod
    def _loss_percent_to_status(loss_percent: float) -> DotStatus:
        """Map a packet loss percentage to a DotStatus.

        Thresholds:
            - 0% loss → LOSS_NONE (green)
            - 1–49% loss → LOSS_LOW (yellow)
            - 50–99% loss → LOSS_HIGH (red)
            - 100% loss → LOSS_TOTAL (white)

        Args:
            loss_percent: Packet loss as a percentage (0.0–100.0).

        Returns:
            The corresponding DotStatus for gradient coloring.
        """
        if loss_percent == 0.0:
            return DotStatus.LOSS_NONE
        elif loss_percent < 50.0:
            return DotStatus.LOSS_LOW
        elif loss_percent < 100.0:
            return DotStatus.LOSS_HIGH
        else:
            return DotStatus.LOSS_TOTAL
