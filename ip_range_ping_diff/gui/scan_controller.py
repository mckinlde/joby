"""Scan controller bridging GUI thread with background scan execution.

This module provides the ScanController (QObject) which manages the lifecycle
of a scan: launching it on a background QThread, bridging PingScanner callbacks
to Qt signals for safe cross-thread communication, and tracking running state.

Referenced requirements: 8.15
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from ip_range_ping_diff.models import (
    DiagnosticResult,
    PingResult,
    ScanMode,
    ScanResults,
)
from ip_range_ping_diff.scanner import PingScanner


class _ScanWorker(QThread):
    """Background QThread worker that executes PingScanner.scan().

    Emits signals as results arrive and when the scan completes or fails.
    The PingScanner callbacks are used to bridge individual results to
    Qt signals, which are thread-safe to emit from any thread.
    """

    # Signals emitted during scan execution
    result_received = Signal(object)  # PingResult
    diagnostic_result_received = Signal(object)  # DiagnosticResult
    scan_completed = Signal(object)  # ScanResults
    scan_error = Signal(str)  # Error message

    def __init__(
        self,
        scanner: PingScanner,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the worker with a configured PingScanner.

        Args:
            scanner: A fully-configured PingScanner instance ready to scan.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._scanner = scanner

    def run(self) -> None:
        """Execute PingScanner.scan() on this background thread.

        Catches exceptions and emits scan_error if the scan fails.
        On success, emits scan_completed with the full ScanResults.
        """
        try:
            results = self._scanner.scan()
            self.scan_completed.emit(results)
        except Exception as e:
            self.scan_error.emit(str(e))


class ScanController(QObject):
    """Bridges GUI thread with background scan execution.

    Creates and manages a QThread worker that runs PingScanner.scan().
    PingScanner callbacks are wired to emit Qt signals, ensuring safe
    cross-thread communication with the GUI. The controller tracks whether
    a scan is currently running.

    Signals:
        result_received: Emitted for each PingResult as it arrives.
        diagnostic_result_received: Emitted for each DiagnosticResult.
        scan_completed: Emitted when the scan finishes with ScanResults.
        scan_error: Emitted if the scan raises an exception.
    """

    result_received = Signal(object)  # PingResult
    diagnostic_result_received = Signal(object)  # DiagnosticResult
    scan_completed = Signal(object)  # ScanResults
    scan_error = Signal(str)  # Error message

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the scan controller with no active worker."""
        super().__init__(parent)
        self._worker: _ScanWorker | None = None

    def start_scan(
        self,
        subnet_a: str,
        subnet_b: str,
        excluded_octets: set[int],
        thread_count: int,
        timeout: float,
        retries: int,
        retry_delay_ms: float = 100.0,
        scan_mode: ScanMode = ScanMode.PING_ONCE,
        ping_count: int = 10,
        burst_count: int = 5,
        burst_interval: float = 0.1,
    ) -> None:
        """Launch a scan on a background QThread.

        Creates a PingScanner with the given parameters, wires its
        callbacks to emit Qt signals, and starts the worker thread.

        Args:
            subnet_a: First subnet in CIDR /24 notation.
            subnet_b: Second subnet in CIDR /24 notation.
            excluded_octets: Octets to skip in both subnets.
            thread_count: Number of concurrent threads.
            timeout: Per-ping timeout in seconds.
            retries: Number of retries per failed ping.
            retry_delay_ms: Delay in ms between retry attempts.
            scan_mode: The scan mode to use.
            ping_count: Number of pings for Packet Loss / Jitter modes.
            burst_count: Number of pings for Response Under Load mode.
            burst_interval: Interval between burst pings in seconds.
        """
        if self.is_running():
            return  # Don't start a new scan while one is in progress

        # Create the PingScanner with callbacks that emit Qt signals.
        # Qt signals are thread-safe to emit from any thread, so
        # the callbacks bridge the ThreadPoolExecutor results to the
        # GUI thread via the signal/slot mechanism.
        scanner = PingScanner(
            subnet_a=subnet_a,
            subnet_b=subnet_b,
            excluded_octets=excluded_octets,
            thread_count=thread_count,
            timeout=timeout,
            retries=retries,
            retry_delay_ms=retry_delay_ms,
            scan_mode=scan_mode,
            ping_count=ping_count,
            burst_count=burst_count,
            burst_interval=burst_interval,
            on_result=self._on_result_callback,
            on_diagnostic_result=self._on_diagnostic_result_callback,
        )

        # Create and configure the worker thread
        self._worker = _ScanWorker(scanner)
        self._worker.result_received.connect(self.result_received)
        self._worker.diagnostic_result_received.connect(
            self.diagnostic_result_received
        )
        self._worker.scan_completed.connect(self._on_worker_completed)
        self._worker.scan_error.connect(self._on_worker_error)
        self._worker.start()

    def is_running(self) -> bool:
        """Return True if a scan is currently in progress."""
        return self._worker is not None and self._worker.isRunning()

    def _on_result_callback(self, result: PingResult) -> None:
        """Callback passed to PingScanner.on_result.

        Emits the result_received signal from the worker thread.
        Qt signals are safe to emit across threads.
        """
        if self._worker is not None:
            self._worker.result_received.emit(result)

    def _on_diagnostic_result_callback(
        self, result: DiagnosticResult
    ) -> None:
        """Callback passed to PingScanner.on_diagnostic_result.

        Emits the diagnostic_result_received signal from the worker thread.
        """
        if self._worker is not None:
            self._worker.diagnostic_result_received.emit(result)

    def _on_worker_completed(self, results: ScanResults) -> None:
        """Handle scan completion from the worker thread.

        Forwards the scan_completed signal and cleans up the worker.
        """
        self.scan_completed.emit(results)
        self._cleanup_worker()

    def _on_worker_error(self, error_message: str) -> None:
        """Handle scan error from the worker thread.

        Forwards the scan_error signal and cleans up the worker.
        """
        self.scan_error.emit(error_message)
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        """Clean up the worker thread reference."""
        if self._worker is not None:
            self._worker.quit()
            self._worker.wait()
            self._worker = None
