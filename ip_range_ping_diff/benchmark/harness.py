"""Benchmark harness for comparing ping scan implementation strategies.

Orchestrates Python subprocess, Bash, C, and Rust implementations
and produces a comparison summary with wall-clock timing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Directory containing this module
BENCHMARK_DIR = Path(__file__).parent


def _get_subnets() -> tuple[str, str]:
    """Return the two /24 subnet prefixes to benchmark against."""
    subnet_a = os.environ.get("BENCH_SUBNET_A", "192.168.1")
    subnet_b = os.environ.get("BENCH_SUBNET_B", "192.168.2")
    return subnet_a, subnet_b


def run_python_benchmark(subnet_a: str, subnet_b: str) -> float:
    """Run the Python PingScanner and return wall-clock seconds.

    Uses the project's PingScanner with default settings (Ping Once mode,
    64 threads, 1s timeout).
    """
    from ip_range_ping_diff.scanner import PingScanner

    scanner = PingScanner(
        subnet_a=f"{subnet_a}.0/24",
        subnet_b=f"{subnet_b}.0/24",
        thread_count=64,
        timeout=1.0,
        retries=0,
    )
    start = time.time()
    scanner.scan()
    elapsed = time.time() - start
    return elapsed


def run_bash_benchmark(subnet_a: str, subnet_b: str) -> float:
    """Run the Bash ping script and return wall-clock seconds."""
    script_path = BENCHMARK_DIR / "ping_bash.sh"
    if not script_path.exists():
        raise FileNotFoundError(f"Bash benchmark script not found: {script_path}")

    start = time.time()
    result = subprocess.run(
        ["bash", str(script_path), subnet_a, subnet_b],
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"  [bash] stderr: {result.stderr.strip()}", file=sys.stderr)

    return elapsed


def run_c_benchmark(subnet_a: str, subnet_b: str) -> float:
    """Build and run the C ping implementation, return wall-clock seconds."""
    c_dir = BENCHMARK_DIR / "ping_c"
    binary = c_dir / "ping_scan"

    # Build if necessary
    if not binary.exists():
        if not (c_dir / "Makefile").exists():
            raise FileNotFoundError(f"C Makefile not found: {c_dir / 'Makefile'}")
        build_result = subprocess.run(
            ["make", "-C", str(c_dir)],
            capture_output=True,
            text=True,
        )
        if build_result.returncode != 0:
            raise RuntimeError(
                f"C build failed:\n{build_result.stderr}"
            )

    start = time.time()
    result = subprocess.run(
        [str(binary), subnet_a, subnet_b],
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"  [c] stderr: {result.stderr.strip()}", file=sys.stderr)

    return elapsed


def run_rust_benchmark(subnet_a: str, subnet_b: str) -> float:
    """Build and run the Rust ping implementation, return wall-clock seconds."""
    rust_dir = BENCHMARK_DIR / "ping_rust"
    cargo_toml = rust_dir / "Cargo.toml"

    if not cargo_toml.exists():
        raise FileNotFoundError(f"Rust Cargo.toml not found: {cargo_toml}")

    # Check if cargo is available
    if not shutil.which("cargo"):
        raise RuntimeError("cargo not found in PATH; install Rust toolchain")

    # Build in release mode
    build_result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=str(rust_dir),
        capture_output=True,
        text=True,
    )
    if build_result.returncode != 0:
        raise RuntimeError(f"Rust build failed:\n{build_result.stderr}")

    binary = rust_dir / "target" / "release" / "ping_rust"
    if not binary.exists():
        # Try Windows naming
        binary = rust_dir / "target" / "release" / "ping_rust.exe"

    start = time.time()
    result = subprocess.run(
        [str(binary), subnet_a, subnet_b],
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"  [rust] stderr: {result.stderr.strip()}", file=sys.stderr)

    return elapsed


def print_comparison(results: dict[str, float | None]) -> None:
    """Print a formatted comparison table of benchmark results.

    Args:
        results: Mapping of strategy name to elapsed seconds (None if skipped).
    """
    print("\n" + "=" * 60)
    print("PING SCAN BENCHMARK COMPARISON")
    print("=" * 60)
    print(f"{'Strategy':<20} {'Time (s)':<12} {'Relative':<12} {'Status'}")
    print("-" * 60)

    # Find the fastest time for relative comparison
    valid_times = [t for t in results.values() if t is not None]
    fastest = min(valid_times) if valid_times else None

    for name, elapsed in results.items():
        if elapsed is None:
            print(f"{name:<20} {'N/A':<12} {'N/A':<12} SKIPPED")
        else:
            relative = f"{elapsed / fastest:.2f}x" if fastest else "N/A"
            print(f"{name:<20} {elapsed:<12.3f} {relative:<12} OK")

    print("-" * 60)
    if fastest is not None:
        print(f"Fastest: {fastest:.3f}s")
    print("=" * 60 + "\n")


def run_benchmarks() -> dict[str, float | None]:
    """Run all benchmark strategies and return timing results.

    Returns:
        Dictionary mapping strategy name to wall-clock seconds,
        or None if the strategy was skipped due to an error.
    """
    subnet_a, subnet_b = _get_subnets()
    results: dict[str, float | None] = {}

    strategies = [
        ("Python (subprocess)", run_python_benchmark),
        ("Bash (xargs)", run_bash_benchmark),
        ("C (fork/exec)", run_c_benchmark),
        ("Rust (threads)", run_rust_benchmark),
    ]

    print(f"Benchmarking ping scan of {subnet_a}.0/24 and {subnet_b}.0/24")
    print(f"Scanning octets 1-254 on each subnet (508 hosts total)\n")

    for name, runner in strategies:
        print(f"Running: {name}...", end=" ", flush=True)
        try:
            elapsed = runner(subnet_a, subnet_b)
            results[name] = elapsed
            print(f"{elapsed:.3f}s")
        except (FileNotFoundError, RuntimeError) as e:
            results[name] = None
            print(f"SKIPPED ({e})")

    print_comparison(results)
    return results


def main() -> None:
    """Entry point for the benchmark harness."""
    run_benchmarks()


if __name__ == "__main__":
    main()
