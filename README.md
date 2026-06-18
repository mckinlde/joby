# IP Range Ping Diff

A Python 3.11 tool that concurrently pings two /24 subnets and reports asymmetric reachability — hosts reachable on one range but not the other. Designed for single-hop LAN environments where detecting configuration drift, cable faults, and host degradation matters.

## Features

- **5 scan modes**: Ping Once, Ping Retry, Packet Loss, Jitter, Response Under Load
- **PySide6 GUI** with a 16×16 dot grid (256 hosts at a glance), color-coded by status
- **CLI mode** with JSON output for scripting and automation
- **Configurable**: subnets, thread count, timeout, retries, retry delay, exclusion octets
- **Performance benchmarking** across Python, Bash, C, and Rust implementations
- **PyInstaller packaging** for standalone distribution

## Quick Start

### GUI Mode (default)

```bash
python3 -m ip_range_ping_diff
```

### CLI Mode

```bash
python3 -m ip_range_ping_diff --cli --mode ping-once --threads 64 --timeout 1
```

### Run Benchmarks

```bash
python3 -m ip_range_ping_diff.benchmark.harness
```

## Installation

```bash
# Install dependencies
pip install PySide6 hypothesis pytest pytest-qt pytest-mock

# Optional: install Rust toolchain for Rust benchmark
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"

# Optional: build C benchmark
make -C ip_range_ping_diff/benchmark/ping_c/
```

## Usage Guide

### GUI Controls

The GUI is divided into three areas:

1. **Dot Grid** (top-left): 16×16 grid where each dot is a host octet (0–255). Colors update in real time as results arrive.

2. **Control Panel** (top-right): Configuration fields and scan buttons.

3. **Results Panel** (bottom): Asymmetric IP list, metrics, and diagnostic tables.

### Scan Modes

| Mode | What it does | Parameters |
|------|-------------|------------|
| **Ping Once** | Single ping per host, no retries | threads, timeout |
| **Ping Retry** | Retries failed pings N times | threads, timeout, retries, retry delay |
| **Packet Loss** | Sends N pings, reports % lost | threads, timeout, ping count |
| **Jitter** | Sends N pings, reports min/avg/max/stddev of RTT | threads, timeout, ping count |
| **Response Under Load** | Rapid burst, reports how many received | threads, timeout, burst count, burst interval |

### Dot Grid Color Key

**Standard modes (Ping Once / Ping Retry):**
- Grey — Not yet scanned
- Green — Reachable on both subnets
- Red — Asymmetric (reachable on one subnet only)
- White — Unreachable on both subnets

**Packet Loss mode:**
- Green — 0% loss
- Yellow — 1–49% loss
- Red — 50–99% loss
- White — 100% loss (host down)

### CLI Examples

```bash
# Basic scan with JSON output
python3 -m ip_range_ping_diff --cli

# Custom subnets, exclude gateway and broadcast
python3 -m ip_range_ping_diff --cli \
  --subnet-a 10.0.1.0/24 \
  --subnet-b 10.0.2.0/24 \
  --exclude 0,1,255

# Packet loss scan with 20 pings per host
python3 -m ip_range_ping_diff --cli \
  --mode packet-loss \
  --ping-count 20 \
  --threads 32

# Retry mode with 3 retries and 200ms delay
python3 -m ip_range_ping_diff --cli \
  --mode ping-retry \
  --retries 3 \
  --retry-delay 200

# Response under load: 10 pings at 50ms intervals
python3 -m ip_range_ping_diff --cli \
  --mode load \
  --burst-count 10 \
  --burst-interval 0.05
```

### Benchmark Buttons

The GUI includes benchmark buttons (Python, Bash, C, Rust, Run All) that measure total scan time for each implementation. Results show wall-clock time and relative performance.

```bash
# Or run from command line
python3 -m ip_range_ping_diff.benchmark.harness
```

### Excluding Octets

To skip specific hosts (e.g., gateways at .1, broadcast at .255):

- **GUI**: Enter comma-separated values in the "Excluded Octets" field (e.g., `0,1,255`)
- **CLI**: Use `--exclude 0,1,255`

This removes those octets from both subnets before scanning.

## Architecture

```
ip_range_ping_diff/
├── executor.py              # PingExecutor: single-host ping with retry
├── diagnostic_executor.py   # Packet loss, jitter, burst modes
├── scanner.py               # PingScanner: ThreadPoolExecutor orchestration
├── diff_reporter.py         # Asymmetric diff computation + JSON
├── diagnostic_reporter.py   # Diagnostic result formatting
├── exclusion.py             # Octet exclusion filter
├── models.py                # Data models (dataclasses, enums)
├── cli.py                   # CLI argument parsing + JSON output
├── config.py                # Default configuration constants
├── gui/                     # PySide6 GUI components
│   ├── main_window.py
│   ├── dot_grid.py          # 16×16 colored dot grid
│   ├── color_legend.py      # Color key widget
│   ├── control_panel.py     # Buttons + config fields
│   ├── results_panel.py     # Results display
│   └── scan_controller.py   # QThread bridge
└── benchmark/               # Performance comparison
    ├── harness.py           # Orchestration + reporting
    ├── ping_bash.sh         # Bash (xargs parallelism)
    ├── ping_c/              # C (fork/exec)
    └── ping_rust/           # Rust (std::thread)
```

## Design Direction: Measurement Accuracy

### The subprocess overhead problem

All current implementations (Python, Bash, C benchmark, Rust benchmark) use the same approach: spawn the system `ping` binary as a subprocess. This means the reported `delay_ms` values include subprocess overhead:

```
Reported delay = network RTT + process spawn + stdout capture + parsing
```

On a LAN where true RTT is <1ms, subprocess overhead (5–20ms in Python, 2–5ms in C/Rust fork+exec) dominates the measurement. A host responding in 0.3ms might be reported as 6ms.

### Next step: raw socket implementations

To demonstrate true measurement accuracy, the planned direction is:

1. **Python raw socket** — `socket.socket(AF_INET, SOCK_RAW, IPPROTO_ICMP)` eliminates subprocess overhead entirely. Measures `sendto → recvfrom` directly. Expected accuracy: ~0.1–1ms overhead (Python interpreter only).

2. **C raw socket** — Crafts ICMP packets directly, timestamps with `clock_gettime(CLOCK_MONOTONIC)` around `sendto/recvfrom`. Represents the true measurement floor. Expected accuracy: <0.01ms overhead.

3. **Rust raw socket** — Same approach via the `socket2` crate. Same accuracy as C with safer ergonomics.

The benchmark then tells a clear story:

```
Python (subprocess):   ~8ms avg "RTT"   ← 5-20ms overhead included
Python (raw socket):   ~0.8ms avg RTT   ← just interpreter + kernel
C (raw socket):        ~0.3ms avg RTT   ← true network RTT
Rust (raw socket):     ~0.3ms avg RTT   ← true network RTT
```

The gap between subprocess and raw-socket measurements quantifies exactly how much accuracy you sacrifice for the convenience of calling system `ping`.

**Note**: Raw socket implementations require `CAP_NET_RAW` capability or root privileges:
```bash
# Grant capability to a binary
sudo setcap cap_net_raw+ep ./ping_scan

# Or run with sudo
sudo python3 -m ip_range_ping_diff --cli --mode ping-once
```

## Requirements

- Python 3.11+
- PySide6 (GUI)
- pytest, hypothesis, pytest-qt, pytest-mock (testing)
- gcc (C benchmark, optional)
- Rust toolchain (Rust benchmark, optional)

## License

Internal tool — Joby Aviation
