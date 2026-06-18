"""Ping executor with retry logic for IP Range Ping Diff.

This module implements the PingExecutor class which executes single-host
ping operations using the system's ping command via subprocess. It supports
configurable timeouts, retry counts, and inter-retry delays.

The executor handles platform differences (Linux vs Windows) in ping
command syntax and parses response times from stdout using regex patterns.
"""

from __future__ import annotations

import platform
import re
import subprocess
import time

from ip_range_ping_diff.models import PingResult, ReachabilityStatus

# Regex pattern to extract round-trip time from ping stdout.
# Matches patterns like "time=1.23 ms" (Linux) or "time=1ms" / "time<1ms" (Windows).
_RTT_PATTERN_LINUX = re.compile(r"time[=<](\d+\.?\d*)\s*ms", re.IGNORECASE)
_RTT_PATTERN_WINDOWS = re.compile(r"time[=<](\d+\.?\d*)\s*ms", re.IGNORECASE)


class PingExecutor:
    """Executes a single ping with optional retries.

    This class wraps the system ping command and provides a retry mechanism
    for transient failures. It uses subprocess.run to execute pings and
    parses the output to determine reachability and response time.

    Attributes:
        timeout: Timeout in seconds for each individual ping attempt.
        retries: Number of retry attempts after initial failure (0 = Ping Once).
        retry_delay_ms: Delay in milliseconds between consecutive retries.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        retries: int = 0,
        retry_delay_ms: float = 100.0,
    ) -> None:
        """Initialize executor.

        Args:
            timeout: Timeout in seconds for each individual ping attempt.
            retries: Number of retry attempts after initial failure.
                     0 = no retries ("Ping Once" mode).
            retry_delay_ms: Delay in milliseconds between consecutive retry
                            attempts. 0 = no delay. Default 100ms.
        """
        self.timeout = timeout
        self.retries = retries
        self.retry_delay_ms = retry_delay_ms

    def ping(self, ip_address: str, octet: int, subnet: str) -> PingResult:
        """Ping a single IP address with configured retries.

        Attempts to ping the target IP. If the first attempt fails and retries
        are configured, waits retry_delay_ms between each subsequent attempt.
        Classifies as REACHABLE if ANY attempt succeeds. Classifies as
        UNREACHABLE only after all attempts (initial + retries) are exhausted.

        Args:
            ip_address: The IP address to ping (e.g., "192.168.1.10").
            octet: The host octet (last segment of the IP, 0-255).
            subnet: The subnet prefix this IP belongs to (e.g., "192.168.1").

        Returns:
            PingResult with reachability status, timing, and attempt count.
        """
        # Total attempts = 1 (initial) + retries
        max_attempts = 1 + self.retries
        delay_ms: float | None = None

        for attempt in range(1, max_attempts + 1):
            success, rtt = self._execute_ping(ip_address)

            if success:
                # Host responded — classify as REACHABLE immediately.
                # No further retries are needed.
                return PingResult(
                    ip_address=ip_address,
                    octet=octet,
                    subnet=subnet,
                    status=ReachabilityStatus.REACHABLE,
                    attempts=attempt,
                    delay_ms=rtt,
                )

            # Ping failed. If retries remain, wait before the next attempt.
            if attempt < max_attempts:
                # Apply retry delay between consecutive attempts
                if self.retry_delay_ms > 0:
                    time.sleep(self.retry_delay_ms / 1000.0)

        # All attempts exhausted without a successful response
        return PingResult(
            ip_address=ip_address,
            octet=octet,
            subnet=subnet,
            status=ReachabilityStatus.UNREACHABLE,
            attempts=max_attempts,
            delay_ms=None,
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
            # On Linux, -W accepts seconds (integer). On macOS, -W is in ms
            # but -t is in seconds. We use -W with ceiling to nearest second.
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
        # Both Linux and Windows use "time=X ms" or "time<X ms" format
        match = _RTT_PATTERN_LINUX.search(stdout)
        if match:
            return float(match.group(1))
        return None
