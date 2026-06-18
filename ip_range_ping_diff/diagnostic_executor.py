"""Advanced diagnostic ping executor for IP Range Ping Diff.

This module implements the DiagnosticExecutor class which executes
multi-ping diagnostic operations (Packet Loss, Jitter, Response Under Load)
against a single host using the system's ping command via subprocess.

The executor reuses the same subprocess/platform approach as PingExecutor
and adds statistical analysis of multiple ping responses.
"""

from __future__ import annotations

import platform
import re
import statistics
import subprocess
import time

from ip_range_ping_diff.models import (
    JitterResult,
    LoadClassification,
    LoadResult,
    PacketLossResult,
)

# Regex pattern to extract round-trip time from ping stdout.
# Matches patterns like "time=1.23 ms" or "time<1ms" (both Linux and Windows).
_RTT_PATTERN = re.compile(r"time[=<](\d+\.?\d*)\s*ms", re.IGNORECASE)


class DiagnosticExecutor:
    """Executes advanced diagnostic ping modes for a single host.

    Supports three diagnostic modes:
    - Packet Loss: sends multiple pings and computes loss percentage.
    - Jitter: sends multiple pings and computes response time statistics.
    - Response Under Load: sends a rapid burst of pings and classifies
      the host's responsiveness.

    Attributes:
        timeout: Timeout in seconds for each individual ping attempt.
        ping_count: Number of pings for Packet Loss and Jitter modes.
        burst_count: Number of pings in the burst for Response Under Load.
        burst_interval: Interval in seconds between consecutive burst pings.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        ping_count: int = 10,
        burst_count: int = 5,
        burst_interval: float = 0.1,
    ) -> None:
        """Initialize diagnostic executor.

        Args:
            timeout: Timeout in seconds for each individual ping attempt.
            ping_count: Number of pings for Packet Loss and Jitter modes.
                        Must be > 0.
            burst_count: Number of pings in the burst for Response Under
                         Load mode. Must be > 0.
            burst_interval: Interval in seconds between consecutive burst
                            pings for Response Under Load mode. Must be >= 0.

        Raises:
            ValueError: If ping_count <= 0, burst_count <= 0, or
                        burst_interval < 0.
        """
        if ping_count <= 0:
            raise ValueError(
                f"ping_count must be greater than 0, got {ping_count}"
            )
        if burst_count <= 0:
            raise ValueError(
                f"burst_count must be greater than 0, got {burst_count}"
            )
        if burst_interval < 0:
            raise ValueError(
                f"burst_interval must be >= 0, got {burst_interval}"
            )

        self.timeout = timeout
        self.ping_count = ping_count
        self.burst_count = burst_count
        self.burst_interval = burst_interval

    def packet_loss(
        self, ip_address: str, octet: int, subnet: str
    ) -> PacketLossResult:
        """Send ping_count pings and compute packet loss percentage.

        Sends ping_count individual pings to the target host and counts
        how many receive a reply. Loss percentage is computed as:
        (sent - received) / sent * 100

        Args:
            ip_address: The IP address to ping (e.g., "192.168.1.10").
            octet: The host octet (last segment of the IP, 0-255).
            subnet: The subnet prefix this IP belongs to (e.g., "192.168.1").

        Returns:
            PacketLossResult with sent count, received count, and
            loss_percent (0.0–100.0).
        """
        sent = self.ping_count
        received = 0

        for _ in range(sent):
            success, _ = self._execute_ping(ip_address)
            if success:
                received += 1

        loss_percent = (sent - received) / sent * 100.0

        return PacketLossResult(
            ip_address=ip_address,
            octet=octet,
            subnet=subnet,
            sent=sent,
            received=received,
            loss_percent=loss_percent,
        )

    def jitter(
        self, ip_address: str, octet: int, subnet: str
    ) -> JitterResult:
        """Send ping_count pings and compute response time statistics.

        Sends ping_count individual pings and collects the round-trip
        times of successful responses. Computes min, avg, max, and
        standard deviation of the response times.

        stddev is None if fewer than 2 successful responses are received
        (standard deviation requires at least 2 data points).

        Args:
            ip_address: The IP address to ping (e.g., "192.168.1.10").
            octet: The host octet (last segment of the IP, 0-255).
            subnet: The subnet prefix this IP belongs to (e.g., "192.168.1").

        Returns:
            JitterResult with min_ms, avg_ms, max_ms, stddev_ms.
            All timing fields are None if no successful responses.
            stddev_ms is None if fewer than 2 successful responses.
        """
        sent = self.ping_count
        response_times: list[float] = []

        for _ in range(sent):
            success, delay_ms = self._execute_ping(ip_address)
            if success and delay_ms is not None:
                response_times.append(delay_ms)

        received = len(response_times)

        if received == 0:
            # No successful responses — all timing fields are None
            return JitterResult(
                ip_address=ip_address,
                octet=octet,
                subnet=subnet,
                sent=sent,
                received=received,
                min_ms=None,
                avg_ms=None,
                max_ms=None,
                stddev_ms=None,
            )

        min_ms = min(response_times)
        avg_ms = sum(response_times) / len(response_times)
        max_ms = max(response_times)

        # Standard deviation requires at least 2 data points
        stddev_ms: float | None = None
        if received >= 2:
            stddev_ms = statistics.stdev(response_times)

        return JitterResult(
            ip_address=ip_address,
            octet=octet,
            subnet=subnet,
            sent=sent,
            received=received,
            min_ms=min_ms,
            avg_ms=avg_ms,
            max_ms=max_ms,
            stddev_ms=stddev_ms,
        )

    def response_under_load(
        self, ip_address: str, octet: int, subnet: str
    ) -> LoadResult:
        """Send burst_count pings at burst_interval spacing.

        Sends a rapid burst of pings to the target host with a specified
        interval between each ping. Counts how many are received and
        classifies the host's responsiveness:
        - DOWN: 0 responses received
        - DEGRADED: >0 but fewer than burst_count responses
        - HEALTHY: All burst_count pings received

        Args:
            ip_address: The IP address to ping (e.g., "192.168.1.10").
            octet: The host octet (last segment of the IP, 0-255).
            subnet: The subnet prefix this IP belongs to (e.g., "192.168.1").

        Returns:
            LoadResult with burst_sent, burst_received, burst_interval,
            and classification (DOWN, DEGRADED, or HEALTHY).
        """
        burst_sent = self.burst_count
        burst_received = 0

        for i in range(burst_sent):
            success, _ = self._execute_ping(ip_address)
            if success:
                burst_received += 1

            # Sleep between burst pings (but not after the last one)
            if i < burst_sent - 1 and self.burst_interval > 0:
                time.sleep(self.burst_interval)

        # Classify the host based on how many burst pings were received
        if burst_received == 0:
            classification = LoadClassification.DOWN
        elif burst_received < burst_sent:
            classification = LoadClassification.DEGRADED
        else:
            classification = LoadClassification.HEALTHY

        return LoadResult(
            ip_address=ip_address,
            octet=octet,
            subnet=subnet,
            burst_sent=burst_sent,
            burst_received=burst_received,
            burst_interval=self.burst_interval,
            classification=classification,
        )

    def _execute_ping(self, ip_address: str) -> tuple[bool, float | None]:
        """Execute a single ping subprocess.

        Builds a platform-appropriate ping command and runs it via
        subprocess.run with captured output. Parses the stdout to extract
        the round-trip time on success.

        Args:
            ip_address: The target IP address to ping.

        Returns:
            A tuple of (success, delay_ms).
            success is True if the ping received a reply.
            delay_ms is the round-trip time in milliseconds, or None if
            the ping failed or the RTT could not be parsed.
        """
        cmd = self._build_ping_command(ip_address)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 2,  # Extra buffer beyond ping's own timeout
            )
        except (subprocess.TimeoutExpired, OSError):
            # Subprocess timed out or failed to execute
            return (False, None)

        # A non-zero return code means the ping did not get a reply
        if result.returncode != 0:
            return (False, None)

        # Parse the response time from stdout
        delay_ms = self._parse_rtt(result.stdout)

        # Even with returncode 0, if we can't parse RTT, still treat as success
        # (some systems return 0 on success without easily parseable timing)
        return (True, delay_ms)

    def _build_ping_command(self, ip_address: str) -> list[str]:
        """Build platform-appropriate ping command.

        Linux/macOS: ping -c 1 -W <timeout_seconds> <ip>
        Windows:     ping -n 1 -w <timeout_ms> <ip>

        Args:
            ip_address: The target IP address.

        Returns:
            Command as a list of strings suitable for subprocess.run.
        """
        system = platform.system().lower()

        if system == "windows":
            # Windows -w flag expects timeout in milliseconds
            timeout_ms = int(self.timeout * 1000)
            return ["ping", "-n", "1", "-w", str(timeout_ms), ip_address]
        else:
            # Linux/macOS: -c 1 sends one packet, -W sets timeout in seconds.
            timeout_sec = max(1, int(self.timeout)) if self.timeout < 1 else int(self.timeout)
            return ["ping", "-c", "1", "-W", str(timeout_sec), ip_address]

    def _parse_rtt(self, stdout: str) -> float | None:
        """Parse round-trip time from ping command stdout.

        Searches for patterns like "time=1.23 ms" or "time<1ms" in the
        ping output.

        Args:
            stdout: The standard output from the ping subprocess.

        Returns:
            The round-trip time in milliseconds, or None if not parseable.
        """
        match = _RTT_PATTERN.search(stdout)
        if match:
            return float(match.group(1))
        return None
