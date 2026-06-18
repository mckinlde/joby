"""PingScanner orchestration for IP Range Ping Diff.

This module implements the PingScanner class which coordinates concurrent
ping scanning of two /24 subnets using ThreadPoolExecutor. It validates
subnet formats, generates host addresses, integrates exclusion filtering,
and computes aggregate scan statistics.

The scanner supports all five scan modes: PING_ONCE, PING_RETRY,
PACKET_LOSS, JITTER, and RESPONSE_UNDER_LOAD. For the three advanced
diagnostic modes, it uses DiagnosticExecutor instead of PingExecutor.
"""

from __future__ import annotations

import re
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from ip_range_ping_diff.config import (
    DEFAULT_BURST_COUNT,
    DEFAULT_BURST_INTERVAL,
    DEFAULT_PING_COUNT,
    DEFAULT_RETRY_DELAY_MS,
    DEFAULT_RETRIES,
    DEFAULT_SUBNET_A,
    DEFAULT_SUBNET_B,
    DEFAULT_THREAD_COUNT,
    DEFAULT_TIMEOUT,
)
from ip_range_ping_diff.diagnostic_executor import DiagnosticExecutor
from ip_range_ping_diff.exclusion import ExclusionFilter
from ip_range_ping_diff.executor import PingExecutor
from ip_range_ping_diff.models import (
    DiagnosticResult,
    PingResult,
    ReachabilityStatus,
    ScanMode,
    ScanResults,
    ScanStats,
)

# Regex pattern for validating /24 CIDR subnet format.
# Matches X.X.X.0/24 where X are valid octet values (0-255).
_SUBNET_PATTERN = re.compile(
    r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.0/24$"
)


class PingScanner:
    """Orchestrates concurrent ping scanning of two subnets.

    The PingScanner validates subnet inputs, applies exclusion filtering,
    and uses a ThreadPoolExecutor to ping all non-excluded hosts in both
    subnets concurrently. It computes aggregate statistics (min, median,
    mode, max delay, duration, counts) and invokes callbacks as results
    arrive for real-time GUI updates.

    Attributes:
        subnet_a: First subnet in CIDR /24 notation.
        subnet_b: Second subnet in CIDR /24 notation.
        thread_count: Number of concurrent threads for scanning.
        timeout: Per-ping timeout in seconds.
        retries: Number of retries per failed ping.
        retry_delay_ms: Delay in milliseconds between retry attempts.
        scan_mode: The scan mode to use.
        ping_count: Number of pings per host for diagnostic modes.
        burst_count: Number of pings in burst for load mode.
        burst_interval: Interval between burst pings in seconds.
        on_result: Callback invoked for each completed ping result.
        on_diagnostic_result: Callback for diagnostic mode results.
    """

    def __init__(
        self,
        subnet_a: str = DEFAULT_SUBNET_A,
        subnet_b: str = DEFAULT_SUBNET_B,
        excluded_octets: set[int] | None = None,
        thread_count: int = DEFAULT_THREAD_COUNT,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        retry_delay_ms: float = DEFAULT_RETRY_DELAY_MS,
        scan_mode: ScanMode = ScanMode.PING_ONCE,
        ping_count: int = DEFAULT_PING_COUNT,
        burst_count: int = DEFAULT_BURST_COUNT,
        burst_interval: float = DEFAULT_BURST_INTERVAL,
        on_result: Callable[[PingResult], None] | None = None,
        on_diagnostic_result: Callable[[DiagnosticResult], None] | None = None,
    ) -> None:
        """Initialize scanner.

        Args:
            subnet_a: First subnet in CIDR /24 notation.
            subnet_b: Second subnet in CIDR /24 notation.
            excluded_octets: Octets to skip in both subnets.
            thread_count: Number of concurrent threads.
            timeout: Per-ping timeout in seconds.
            retries: Number of retries per failed ping (0 = Ping Once mode).
            retry_delay_ms: Delay in milliseconds between retry attempts.
                            0 = no delay. Default 100ms.
            scan_mode: The scan mode to use (PING_ONCE, PING_RETRY,
                       PACKET_LOSS, JITTER, RESPONSE_UNDER_LOAD).
            ping_count: Number of pings per host for Packet Loss and Jitter modes.
            burst_count: Number of pings in the burst for Response Under Load mode.
            burst_interval: Interval in seconds between burst pings for
                            Response Under Load mode.
            on_result: Optional callback invoked for each completed ping
                       (Ping Once / Ping Retry modes).
            on_diagnostic_result: Optional callback invoked for each completed
                                  diagnostic scan (advanced modes).

        Raises:
            ValueError: If subnet format is invalid.
        """
        # Validate both subnets before storing
        self._prefix_a = self._validate_subnet(subnet_a)
        self._prefix_b = self._validate_subnet(subnet_b)

        self.subnet_a = subnet_a
        self.subnet_b = subnet_b
        self.thread_count = thread_count
        self.timeout = timeout
        self.retries = retries
        self.retry_delay_ms = retry_delay_ms
        self.scan_mode = scan_mode
        self.ping_count = ping_count
        self.burst_count = burst_count
        self.burst_interval = burst_interval
        self.on_result = on_result
        self.on_diagnostic_result = on_diagnostic_result

        # Set up exclusion filter
        self._exclusion_filter = ExclusionFilter(excluded_octets or set())

    def scan(self) -> ScanResults:
        """Execute the full scan of both subnets concurrently.

        Uses ThreadPoolExecutor to ping all non-excluded hosts in both
        subnets. For PING_ONCE and PING_RETRY modes, uses PingExecutor.
        For PACKET_LOSS, JITTER, and RESPONSE_UNDER_LOAD modes, uses
        DiagnosticExecutor. Computes aggregate ScanStats after all results
        are collected.

        Returns:
            ScanResults containing all ping/diagnostic results and
            computed statistics.
        """
        start_time = time.time()

        # Filter octets based on exclusion list (scan range is 1-254)
        active_octets = self._exclusion_filter.filter_octets(range(1, 255))

        # Generate full IP addresses for both subnets
        hosts_a = self._generate_hosts(self._prefix_a, active_octets)
        hosts_b = self._generate_hosts(self._prefix_b, active_octets)

        # Determine if this is a diagnostic mode
        diagnostic_modes = {
            ScanMode.PACKET_LOSS,
            ScanMode.JITTER,
            ScanMode.RESPONSE_UNDER_LOAD,
        }
        is_diagnostic = self.scan_mode in diagnostic_modes

        if is_diagnostic:
            return self._scan_diagnostic(hosts_a, hosts_b, start_time)
        else:
            return self._scan_ping(hosts_a, hosts_b, start_time)

    def _scan_ping(
        self,
        hosts_a: list[tuple[str, int]],
        hosts_b: list[tuple[str, int]],
        start_time: float,
    ) -> ScanResults:
        """Execute a standard ping scan (PING_ONCE, PING_RETRY, or SEQUENTIAL).

        Uses PingExecutor to ping each host. For SEQUENTIAL mode, pings
        are executed one at a time in a single thread to minimize system
        resource usage. For other modes, uses ThreadPoolExecutor.

        Args:
            hosts_a: List of (ip_address, octet) tuples for subnet A.
            hosts_b: List of (ip_address, octet) tuples for subnet B.
            start_time: Timestamp when the scan started.

        Returns:
            ScanResults with results_a and results_b populated.
        """
        # Create the executor with appropriate retry settings
        if self.scan_mode == ScanMode.PING_ONCE:
            executor = PingExecutor(
                timeout=self.timeout,
                retries=0,
                retry_delay_ms=0,
            )
        elif self.scan_mode == ScanMode.SEQUENTIAL:
            # Sequential mode: single-thread, respects user retry settings
            executor = PingExecutor(
                timeout=self.timeout,
                retries=self.retries,
                retry_delay_ms=self.retry_delay_ms,
            )
        else:
            # PING_RETRY mode
            executor = PingExecutor(
                timeout=self.timeout,
                retries=self.retries,
                retry_delay_ms=self.retry_delay_ms,
            )

        # Collect results for both subnets
        results_a: dict[int, PingResult] = {}
        results_b: dict[int, PingResult] = {}

        if self.scan_mode in (ScanMode.SEQUENTIAL, ScanMode.SEQUENTIAL_LOOP):
            # Sequential mode: single thread, one host at a time.
            # Minimal CPU/memory footprint — suitable for machines
            # running other critical software.
            # SEQUENTIAL_LOOP continuously iterates until stopped externally.
            loop_forever = self.scan_mode == ScanMode.SEQUENTIAL_LOOP
            iteration = 0

            while True:
                iteration += 1
                for ip, octet in hosts_a:
                    result = executor.ping(ip, octet, self._prefix_a)
                    results_a[octet] = result
                    if self.on_result is not None:
                        self.on_result(result)

                for ip, octet in hosts_b:
                    result = executor.ping(ip, octet, self._prefix_b)
                    results_b[octet] = result
                    if self.on_result is not None:
                        self.on_result(result)

                if not loop_forever:
                    break
        else:
            # Concurrent mode: scan both subnets using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.thread_count) as pool:
                # Submit all ping tasks for both subnets
                future_to_info: dict = {}

                for ip, octet in hosts_a:
                    future = pool.submit(
                        executor.ping, ip, octet, self._prefix_a
                    )
                    future_to_info[future] = ("a", octet)

                for ip, octet in hosts_b:
                    future = pool.submit(
                        executor.ping, ip, octet, self._prefix_b
                    )
                    future_to_info[future] = ("b", octet)

                # Collect results as they complete
                for future in as_completed(future_to_info):
                    subnet_key, octet = future_to_info[future]
                    result = future.result()

                    if subnet_key == "a":
                        results_a[octet] = result
                    else:
                        results_b[octet] = result

                    # Invoke callback for real-time GUI updates
                    if self.on_result is not None:
                        self.on_result(result)

        # Compute scan duration
        duration = time.time() - start_time

        # Compute aggregate statistics
        stats = self._compute_stats(results_a, results_b, duration)

        return ScanResults(
            subnet_a=self.subnet_a,
            subnet_b=self.subnet_b,
            scan_mode=self.scan_mode,
            results_a=results_a,
            results_b=results_b,
            stats=stats,
        )

    def _scan_diagnostic(
        self,
        hosts_a: list[tuple[str, int]],
        hosts_b: list[tuple[str, int]],
        start_time: float,
    ) -> ScanResults:
        """Execute a diagnostic scan (PACKET_LOSS, JITTER, or RESPONSE_UNDER_LOAD).

        Uses DiagnosticExecutor to perform advanced diagnostic operations
        on each host, storing results in diagnostic_results_a and
        diagnostic_results_b.

        Args:
            hosts_a: List of (ip_address, octet) tuples for subnet A.
            hosts_b: List of (ip_address, octet) tuples for subnet B.
            start_time: Timestamp when the scan started.

        Returns:
            ScanResults with diagnostic_results_a and diagnostic_results_b
            populated.
        """
        # Create the diagnostic executor with configured parameters
        diag_executor = DiagnosticExecutor(
            timeout=self.timeout,
            ping_count=self.ping_count,
            burst_count=self.burst_count,
            burst_interval=self.burst_interval,
        )

        # Select the appropriate diagnostic method based on scan mode
        if self.scan_mode == ScanMode.PACKET_LOSS:
            diag_method = diag_executor.packet_loss
        elif self.scan_mode == ScanMode.JITTER:
            diag_method = diag_executor.jitter
        else:
            # RESPONSE_UNDER_LOAD
            diag_method = diag_executor.response_under_load

        # Collect diagnostic results for both subnets
        diagnostic_results_a: dict[int, DiagnosticResult] = {}
        diagnostic_results_b: dict[int, DiagnosticResult] = {}

        # Scan both subnets concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.thread_count) as pool:
            # Submit all diagnostic tasks for both subnets
            future_to_info: dict = {}

            for ip, octet in hosts_a:
                future = pool.submit(
                    diag_method, ip, octet, self._prefix_a
                )
                future_to_info[future] = ("a", octet)

            for ip, octet in hosts_b:
                future = pool.submit(
                    diag_method, ip, octet, self._prefix_b
                )
                future_to_info[future] = ("b", octet)

            # Collect results as they complete
            for future in as_completed(future_to_info):
                subnet_key, octet = future_to_info[future]
                result = future.result()

                if subnet_key == "a":
                    diagnostic_results_a[octet] = result
                else:
                    diagnostic_results_b[octet] = result

                # Invoke diagnostic callback for real-time GUI updates
                if self.on_diagnostic_result is not None:
                    self.on_diagnostic_result(result)

        # Compute scan duration
        duration = time.time() - start_time

        # For diagnostic modes, stats are computed with empty ping results
        # since we don't have PingResult objects
        stats = self._compute_stats({}, {}, duration)

        return ScanResults(
            subnet_a=self.subnet_a,
            subnet_b=self.subnet_b,
            scan_mode=self.scan_mode,
            diagnostic_results_a=diagnostic_results_a,
            diagnostic_results_b=diagnostic_results_b,
            stats=stats,
        )

    def _validate_subnet(self, subnet: str) -> str:
        """Validate /24 CIDR format and return the subnet prefix.

        Verifies that the subnet matches the X.X.X.0/24 format where
        each X is a valid octet value (0-255). Returns the first three
        octets as the prefix string (e.g., "192.168.1").

        Args:
            subnet: Subnet string to validate (e.g., "192.168.1.0/24").

        Returns:
            The subnet prefix as a string (e.g., "192.168.1").

        Raises:
            ValueError: If the subnet format is invalid or contains
                        out-of-range octet values.
        """
        match = _SUBNET_PATTERN.match(subnet)
        if not match:
            raise ValueError(
                f"Invalid subnet format: '{subnet}'. "
                f"Expected format: X.X.X.0/24 where X are valid octet values (0-255)."
            )

        # Validate that each octet in the prefix is within 0-255
        octets = [int(match.group(i)) for i in range(1, 4)]
        for i, octet_val in enumerate(octets):
            if octet_val < 0 or octet_val > 255:
                raise ValueError(
                    f"Invalid subnet format: '{subnet}'. "
                    f"Octet {i + 1} value {octet_val} is outside the valid range 0-255."
                )

        # Return the prefix (first three octets joined with dots)
        return f"{octets[0]}.{octets[1]}.{octets[2]}"

    def _generate_hosts(
        self, prefix: str, octets: list[int]
    ) -> list[tuple[str, int]]:
        """Generate full IP addresses from prefix and host octets.

        Combines the subnet prefix with each active octet to produce
        complete IPv4 addresses for scanning.

        Args:
            prefix: The subnet prefix (e.g., "192.168.1").
            octets: List of host octets to generate addresses for.

        Returns:
            A list of tuples (ip_address, octet) for each host.
        """
        return [(f"{prefix}.{octet}", octet) for octet in octets]

    def _compute_stats(
        self,
        results_a: dict[int, PingResult],
        results_b: dict[int, PingResult],
        duration: float,
    ) -> ScanStats:
        """Compute aggregate scan statistics from results.

        Calculates min, median, mode, and max delay from all successful
        pings across both subnets. Also counts reachable/unreachable hosts
        and asymmetric differences.

        Args:
            results_a: Ping results for subnet A keyed by octet.
            results_b: Ping results for subnet B keyed by octet.
            duration: Total scan duration in seconds.

        Returns:
            ScanStats with all computed metrics.
        """
        # Count reachable/unreachable for each subnet
        reachable_a = sum(
            1 for r in results_a.values()
            if r.status == ReachabilityStatus.REACHABLE
        )
        unreachable_a = len(results_a) - reachable_a

        reachable_b = sum(
            1 for r in results_b.values()
            if r.status == ReachabilityStatus.REACHABLE
        )
        unreachable_b = len(results_b) - reachable_b

        # Count asymmetric differences
        asymmetric_count = 0
        common_octets = set(results_a.keys()) & set(results_b.keys())
        for octet in common_octets:
            status_a = results_a[octet].status
            status_b = results_b[octet].status
            if status_a != status_b:
                asymmetric_count += 1

        # Collect all successful delay values for statistics
        delays: list[float] = []
        for r in results_a.values():
            if r.delay_ms is not None:
                delays.append(r.delay_ms)
        for r in results_b.values():
            if r.delay_ms is not None:
                delays.append(r.delay_ms)

        # Compute delay statistics (None if no successful pings)
        if delays:
            min_delay = min(delays)
            max_delay = max(delays)
            median_delay = statistics.median(delays)
            try:
                mode_delay = statistics.mode(delays)
            except statistics.StatisticsError:
                # mode raises StatisticsError if no unique mode (Python < 3.8)
                # In Python 3.8+, mode returns the first encountered value
                mode_delay = None
        else:
            min_delay = None
            max_delay = None
            median_delay = None
            mode_delay = None

        total_hosts = len(results_a) + len(results_b)

        return ScanStats(
            total_hosts_scanned=total_hosts,
            hosts_reachable_a=reachable_a,
            hosts_reachable_b=reachable_b,
            hosts_unreachable_a=unreachable_a,
            hosts_unreachable_b=unreachable_b,
            asymmetric_count=asymmetric_count,
            duration_seconds=duration,
            min_delay_ms=min_delay,
            median_delay_ms=median_delay,
            mode_delay_ms=mode_delay,
            max_delay_ms=max_delay,
        )
