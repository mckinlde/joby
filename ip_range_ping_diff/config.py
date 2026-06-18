"""Default configuration constants for IP Range Ping Diff.

This module centralizes all default values used throughout the application.
These defaults are applied when no explicit user configuration is provided
via the GUI fields or CLI arguments.

Referenced by:
    - PingScanner (subnets, thread_count, timeout)
    - PingExecutor (timeout, retries, retry_delay_ms)
    - DiagnosticExecutor (timeout, ping_count, burst_count, burst_interval)
    - CLI argument parser (all defaults)
    - GUI control panel (pre-populated field values)
"""

# --- Subnet Configuration ---
# Default /24 subnets to scan. The scanner pings octets 1–254 in each.
DEFAULT_SUBNET_A: str = "192.168.1.0/24"
DEFAULT_SUBNET_B: str = "192.168.2.0/24"

# --- Concurrency ---
# Number of threads in the ThreadPoolExecutor. 64 threads provides good
# parallelism for I/O-bound ping subprocess calls without overwhelming
# the OS process table.
DEFAULT_THREAD_COUNT: int = 64

# --- Ping Timing ---
# Timeout in seconds for each individual ping attempt. 1 second is generous
# for LAN hosts (typical RTT < 1ms) while still completing scans promptly.
DEFAULT_TIMEOUT: float = 1.0

# --- Retry Configuration ---
# Number of retry attempts after an initial ping failure.
# 0 = "Ping Once" mode (no retries).
DEFAULT_RETRIES: int = 0

# Delay in milliseconds between consecutive retry attempts.
# 100ms balances responsiveness on a LAN with enough time to exceed
# subprocess overhead (~5–20ms) and allow brief network recovery.
# See design notes for rationale on meaningful delay values.
DEFAULT_RETRY_DELAY_MS: float = 100.0

# --- Diagnostic Mode: Packet Loss & Jitter ---
# Number of pings sent per host in Packet Loss and Jitter modes.
# 10 pings provides a statistically useful sample while keeping
# scan duration reasonable across 254 hosts per subnet.
DEFAULT_PING_COUNT: int = 10

# --- Diagnostic Mode: Response Under Load ---
# Number of pings in a rapid burst for Response Under Load mode.
# 5 pings is enough to distinguish healthy hosts from degraded ones
# without generating excessive ICMP traffic.
DEFAULT_BURST_COUNT: int = 5

# Interval in seconds between consecutive burst pings.
# 0.1s (100ms) is fast enough to stress hosts while staying within
# typical ICMP rate limits on LAN equipment.
DEFAULT_BURST_INTERVAL: float = 0.1
