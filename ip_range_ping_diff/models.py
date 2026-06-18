"""Data models for IP Range Ping Diff.

This module defines all enums, frozen dataclasses, and type aliases used
throughout the application. Models are designed as immutable value objects
where appropriate (frozen dataclasses for results) and mutable containers
for aggregated state (ScanResults, ScanStats, AsymmetricDiff).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Union


class ScanMode(Enum):
    """Available scan modes.

    Each mode determines how the scanner probes hosts and what
    results are collected.
    """

    PING_ONCE = "ping-once"
    PING_RETRY = "ping-retry"
    SEQUENTIAL = "sequential"
    SEQUENTIAL_LOOP = "sequential-loop"
    PACKET_LOSS = "packet-loss"
    JITTER = "jitter"
    RESPONSE_UNDER_LOAD = "load"


class ReachabilityStatus(Enum):
    """Host reachability classification.

    A host is classified as REACHABLE if any ping attempt succeeds,
    UNREACHABLE only after all attempts are exhausted.
    """

    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"


class LoadClassification(Enum):
    """Host classification for Response Under Load mode.

    Categorizes how a host responds to a rapid burst of pings.
    """

    DOWN = "down"  # 0 responses received
    DEGRADED = "degraded"  # >0 but less than burst_count responses
    HEALTHY = "healthy"  # All burst pings received


class DotStatus(Enum):
    """Visual status for a dot in the grid.

    Maps to specific colors in the GUI dot grid visualization.
    """

    NOT_SCANNED = "grey"  # Not yet scanned
    REACHABLE_BOTH = "green"  # Reachable on both subnets
    ASYMMETRIC = "red"  # Reachable on one subnet only
    UNREACHABLE_BOTH = "white"  # Unreachable on both subnets
    # Packet Loss gradient coloring
    LOSS_NONE = "green"  # 0% packet loss
    LOSS_LOW = "yellow"  # 1–49% packet loss
    LOSS_HIGH = "red"  # 50–99% packet loss
    LOSS_TOTAL = "white"  # 100% packet loss (host down)


@dataclass(frozen=True)
class PingResult:
    """Result of pinging a single IP address.

    Contains the reachability classification, timing information,
    and metadata about which host was pinged.
    """

    ip_address: str
    octet: int
    subnet: str
    status: ReachabilityStatus
    attempts: int  # Total number of ping attempts made
    delay_ms: float | None  # Response time in ms (None if unreachable)


@dataclass(frozen=True)
class PacketLossResult:
    """Result of a Packet Loss diagnostic scan for a single host.

    Reports how many pings were sent, how many replies were received,
    and the computed loss percentage.
    """

    ip_address: str
    octet: int
    subnet: str
    sent: int  # Number of pings sent
    received: int  # Number of replies received
    loss_percent: float  # Packet loss percentage (0.0–100.0)


@dataclass(frozen=True)
class JitterResult:
    """Result of a Jitter diagnostic scan for a single host.

    Reports response time statistics across multiple pings. Fields are
    None when insufficient responses are received to compute them.
    """

    ip_address: str
    octet: int
    subnet: str
    sent: int  # Number of pings sent
    received: int  # Number of replies received
    min_ms: float | None  # Minimum response time (None if <1 response)
    avg_ms: float | None  # Average response time (None if <1 response)
    max_ms: float | None  # Maximum response time (None if <1 response)
    stddev_ms: float | None  # Std deviation (None if <2 responses)


@dataclass(frozen=True)
class LoadResult:
    """Result of a Response Under Load scan for a single host.

    Reports how many burst pings were sent and received, and classifies
    the host's responsiveness under load.
    """

    ip_address: str
    octet: int
    subnet: str
    burst_sent: int  # Number of burst pings sent
    burst_received: int  # Number of replies received
    burst_interval: float  # Interval used between burst pings (seconds)
    classification: LoadClassification  # DOWN, DEGRADED, or HEALTHY


# Union type for all diagnostic results
DiagnosticResult = Union[PacketLossResult, JitterResult, LoadResult]


@dataclass(frozen=True)
class DiffEntry:
    """A single asymmetric reachability entry.

    Represents one host octet that is reachable on one subnet but
    unreachable on the other.
    """

    octet: int
    reachable_ip: str
    unreachable_ip: str
    reachable_subnet: str
    unreachable_subnet: str


@dataclass
class AsymmetricDiff:
    """Complete asymmetric reachability report.

    Contains lists of DiffEntry objects grouped by direction:
    only_in_a for hosts reachable only on subnet A, and
    only_in_b for hosts reachable only on subnet B.
    """

    only_in_a: list[DiffEntry] = field(default_factory=list)
    only_in_b: list[DiffEntry] = field(default_factory=list)

    @property
    def total_differences(self) -> int:
        """Return the total number of asymmetric differences."""
        return len(self.only_in_a) + len(self.only_in_b)

    @property
    def has_differences(self) -> bool:
        """Return True if any asymmetric differences exist."""
        return self.total_differences > 0


@dataclass
class ScanStats:
    """Statistics about the completed scan.

    Aggregates timing and count information from the full scan
    of both subnets.
    """

    total_hosts_scanned: int
    hosts_reachable_a: int
    hosts_reachable_b: int
    hosts_unreachable_a: int
    hosts_unreachable_b: int
    asymmetric_count: int
    duration_seconds: float
    min_delay_ms: float | None
    median_delay_ms: float | None
    mode_delay_ms: float | None
    max_delay_ms: float | None


@dataclass
class ScanResults:
    """Complete results from scanning both subnets.

    Contains per-host results for both standard ping modes and
    advanced diagnostic modes, along with aggregate statistics.
    """

    subnet_a: str
    subnet_b: str
    scan_mode: ScanMode = ScanMode.PING_ONCE
    results_a: dict[int, PingResult] = field(default_factory=dict)
    results_b: dict[int, PingResult] = field(default_factory=dict)
    diagnostic_results_a: dict[int, DiagnosticResult] = field(default_factory=dict)
    diagnostic_results_b: dict[int, DiagnosticResult] = field(default_factory=dict)
    stats: ScanStats | None = None


@dataclass
class CLIConfig:
    """Parsed CLI arguments.

    Holds all configuration values parsed from command-line arguments
    for running a scan in CLI mode.
    """

    subnet_a: str
    subnet_b: str
    excluded_octets: set[int]
    thread_count: int
    timeout: float
    retries: int
    retry_delay_ms: float
    scan_mode: ScanMode = ScanMode.PING_ONCE
    ping_count: int = 10
    burst_count: int = 5
    burst_interval: float = 0.1
