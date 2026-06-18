"""Command-line interface for IP Range Ping Diff.

This module provides argument parsing and CLI execution for running
scans without the GUI. It outputs structured JSON to stdout for
integration with scripts and automation pipelines.

Referenced by:
    - __main__.py (when --cli flag is passed)

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 12.11, 12.12
"""

from __future__ import annotations

import argparse
import json
import sys

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
from ip_range_ping_diff.diagnostic_reporter import DiagnosticReporter
from ip_range_ping_diff.diff_reporter import DiffReporter
from ip_range_ping_diff.models import CLIConfig, ScanMode
from ip_range_ping_diff.scanner import PingScanner


def parse_cli_args(argv: list[str] | None = None) -> CLIConfig:
    """Parse command-line arguments for CLI mode.

    Supports modes: ping-once, ping-retry, packet-loss, jitter, load.
    Mode-specific arguments:
      --mode packet-loss: --ping-count (default 10)
      --mode jitter: --ping-count (default 10)
      --mode load: --burst-count (default 5), --burst-interval (default 0.1)

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        CLIConfig with parsed parameters.

    Raises:
        SystemExit: If invalid arguments (argparse handles error + exit).
    """
    parser = argparse.ArgumentParser(
        prog="ip-range-ping-diff",
        description="Scan two /24 subnets and report asymmetric reachability.",
    )

    parser.add_argument(
        "--subnet-a",
        type=str,
        default=DEFAULT_SUBNET_A,
        help=f"First /24 subnet in CIDR notation (default: {DEFAULT_SUBNET_A})",
    )
    parser.add_argument(
        "--subnet-b",
        type=str,
        default=DEFAULT_SUBNET_B,
        help=f"Second /24 subnet in CIDR notation (default: {DEFAULT_SUBNET_B})",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of octets to exclude (e.g., '0,255')",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREAD_COUNT,
        help=f"Number of concurrent threads (default: {DEFAULT_THREAD_COUNT})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-ping timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Number of retry attempts per failed ping (default: {DEFAULT_RETRIES})",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY_MS,
        help=f"Delay in milliseconds between retries (default: {DEFAULT_RETRY_DELAY_MS})",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["ping-once", "ping-retry", "sequential", "packet-loss", "jitter", "load"],
        default="ping-once",
        help="Scan mode (default: ping-once)",
    )
    parser.add_argument(
        "--ping-count",
        type=int,
        default=DEFAULT_PING_COUNT,
        help=f"Number of pings per host for packet-loss/jitter modes (default: {DEFAULT_PING_COUNT})",
    )
    parser.add_argument(
        "--burst-count",
        type=int,
        default=DEFAULT_BURST_COUNT,
        help=f"Number of burst pings for load mode (default: {DEFAULT_BURST_COUNT})",
    )
    parser.add_argument(
        "--burst-interval",
        type=float,
        default=DEFAULT_BURST_INTERVAL,
        help=f"Interval in seconds between burst pings (default: {DEFAULT_BURST_INTERVAL})",
    )

    # Filter out the --cli flag that __main__.py uses for mode dispatch
    if argv is not None:
        argv = [arg for arg in argv if arg != "--cli"]

    args = parser.parse_args(argv)

    # Parse excluded octets from comma-separated string
    excluded_octets: set[int] = set()
    if args.exclude.strip():
        try:
            for part in args.exclude.split(","):
                part = part.strip()
                if part:
                    octet = int(part)
                    if octet < 0 or octet > 255:
                        parser.error(
                            f"Excluded octet {octet} is outside valid range 0-255"
                        )
                    excluded_octets.add(octet)
        except ValueError:
            parser.error(
                f"Invalid exclusion list: '{args.exclude}'. "
                "Expected comma-separated integers (0-255)."
            )

    # Map mode string to ScanMode enum
    scan_mode = ScanMode(args.mode)

    return CLIConfig(
        subnet_a=args.subnet_a,
        subnet_b=args.subnet_b,
        excluded_octets=excluded_octets,
        thread_count=args.threads,
        timeout=args.timeout,
        retries=args.retries,
        retry_delay_ms=args.retry_delay,
        scan_mode=scan_mode,
        ping_count=args.ping_count,
        burst_count=args.burst_count,
        burst_interval=args.burst_interval,
    )


def run_cli(config: CLIConfig) -> None:
    """Execute scan in CLI mode and output JSON to stdout.

    For PING_ONCE and PING_RETRY modes, computes the asymmetric diff
    and outputs it with scan statistics. For diagnostic modes (PACKET_LOSS,
    JITTER, RESPONSE_UNDER_LOAD), outputs per-host diagnostic results
    for both subnets.

    Args:
        config: Parsed CLI configuration from parse_cli_args.
    """
    try:
        # Create the scanner with all configured parameters
        scanner = PingScanner(
            subnet_a=config.subnet_a,
            subnet_b=config.subnet_b,
            excluded_octets=config.excluded_octets,
            thread_count=config.thread_count,
            timeout=config.timeout,
            retries=config.retries,
            retry_delay_ms=config.retry_delay_ms,
            scan_mode=config.scan_mode,
            ping_count=config.ping_count,
            burst_count=config.burst_count,
            burst_interval=config.burst_interval,
        )

        # Execute the scan
        results = scanner.scan()

        # Determine output format based on scan mode
        diagnostic_modes = {
            ScanMode.PACKET_LOSS,
            ScanMode.JITTER,
            ScanMode.RESPONSE_UNDER_LOAD,
        }

        if config.scan_mode in diagnostic_modes:
            # For diagnostic modes, output per-host results for both subnets
            reporter = DiagnosticReporter()

            output_a = json.loads(
                reporter.to_json(
                    results.diagnostic_results_a,
                    config.scan_mode,
                    config.subnet_a,
                    results.stats,
                )
            )
            output_b = json.loads(
                reporter.to_json(
                    results.diagnostic_results_b,
                    config.scan_mode,
                    config.subnet_b,
                    results.stats,
                )
            )

            # Combine both subnet results into a single JSON document
            combined_output = {
                "mode": config.scan_mode.value,
                "subnet_a": output_a,
                "subnet_b": output_b,
            }
            print(json.dumps(combined_output, indent=2))
        else:
            # For ping modes, compute diff and output with stats
            reporter = DiffReporter()
            diff = reporter.compute_diff(results.results_a, results.results_b)
            output = reporter.to_json(diff, results.stats)
            print(output)

    except ValueError as e:
        # Handle invalid subnet format or other validation errors
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Handle unexpected errors gracefully
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
