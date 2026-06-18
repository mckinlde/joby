# Implementation Plan: IP Range Ping Diff

## Overview

This plan implements a Python 3.11 tool that concurrently pings two /24 subnets and reports asymmetric reachability. The implementation proceeds bottom-up: data models first, then core scan engine components, followed by advanced diagnostic modes, GUI, CLI, packaging, and benchmarks. Each task builds on previous ones, ensuring no orphaned code.

## Tasks

- [x] 1. Set up project structure, dependencies, and data models
  - [x] 1.1 Create project directory structure and configuration files
    - Create `ip_range_ping_diff/` package with `__init__.py`, `__main__.py`
    - Create `ip_range_ping_diff/gui/` subpackage with `__init__.py`
    - Create `ip_range_ping_diff/benchmark/` subpackage with `__init__.py`
    - Create `tests/` directory with `__init__.py` and `conftest.py`
    - Create `pyproject.toml` or `requirements.txt` with dependencies: PySide6, hypothesis, pytest, pytest-qt, pytest-mock
    - _Requirements: 6.1_

  - [x] 1.2 Implement data models (`models.py`)
    - Implement all enums: `ScanMode`, `ReachabilityStatus`, `LoadClassification`, `DotStatus`
    - Implement all frozen dataclasses: `PingResult`, `PacketLossResult`, `JitterResult`, `LoadResult`, `DiffEntry`, `AsymmetricDiff`, `ScanStats`, `ScanResults`, `CLIConfig`
    - Define `DiagnosticResult` union type
    - Include docstrings on all public classes
    - _Requirements: 6.3_

  - [x] 1.3 Implement configuration constants (`config.py`)
    - Define default values: subnets ("192.168.1.0/24", "192.168.2.0/24"), thread count (64), timeout (1.0s), retries (0), retry_delay_ms (100.0), ping_count (10), burst_count (5), burst_interval (0.1)
    - _Requirements: 5.3, 2.9_

- [x] 2. Implement ExclusionFilter
  - [x] 2.1 Implement `exclusion.py`
    - Implement `ExclusionFilter.__init__` with validation that all octets are in 0–255, raising `ValueError` for invalid values
    - Implement `filter_octets` to return octets not in the exclusion set
    - Implement `is_excluded` to check membership
    - Include docstrings and inline comments
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.3, 6.4_

  - [ ]* 2.2 Write property tests for ExclusionFilter
    - **Property 6: Exclusion filter removes all and only specified octets**
    - **Property 7: Exclusion filter rejects invalid octets**
    - **Validates: Requirements 4.1, 4.4**

  - [ ]* 2.3 Write unit tests for ExclusionFilter
    - Test empty exclusion set (all octets pass through)
    - Test full exclusion set (no octets pass through)
    - Test boundary octets (0, 255)
    - Test `ValueError` for octet < 0 and octet > 255
    - _Requirements: 7.3_

- [x] 3. Implement PingExecutor with retry logic
  - [x] 3.1 Implement `executor.py`
    - Implement `PingExecutor.__init__` storing timeout, retries, and retry_delay_ms
    - Implement `_execute_ping` using `subprocess.run` with platform-appropriate ping command (Linux: `ping -c 1 -W timeout`, Windows: `ping -n 1 -w timeout_ms`)
    - Parse stdout for response time (delay_ms)
    - Implement `ping` method with retry loop: attempt ping, if fails and retries remain, sleep retry_delay_ms then retry; classify as REACHABLE if any attempt succeeds, UNREACHABLE only after all attempts exhausted
    - Return `PingResult` with correct attempt count
    - Include docstrings and inline comments for retry logic
    - _Requirements: 1.1, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 6.3, 6.4_

  - [ ]* 3.2 Write property tests for PingExecutor
    - **Property 2: Attempt count correctness**
    - **Property 3: Reachability classification correctness**
    - **Property 14: Retry delay is applied between attempts**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.8**

  - [ ]* 3.3 Write unit tests for PingExecutor
    - Test Ping Once mode: single attempt, no retries
    - Test Ping Retry mode: successful on Nth attempt
    - Test all attempts fail → UNREACHABLE
    - Test first attempt succeeds → no further retries
    - Test subprocess failure counts as failed attempt
    - Mock `subprocess.run` for all tests
    - _Requirements: 7.1_

- [x] 4. Implement DiffReporter
  - [x] 4.1 Implement `diff_reporter.py`
    - Implement `compute_diff` comparing two result dictionaries by octet, producing `AsymmetricDiff` with `only_in_a` and `only_in_b` lists
    - Implement `format_report` producing a human-readable string grouped by direction
    - Implement `to_json` serializing `AsymmetricDiff` and `ScanStats` to a valid JSON string
    - Include full IP addresses in each `DiffEntry`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 6.3_

  - [ ]* 4.2 Write property tests for DiffReporter
    - **Property 4: Asymmetric diff correctness**
    - **Property 5: Diff entry contains valid full IP addresses**
    - **Property 9: Diff-then-format round-trip consistency**
    - **Property 13: CLI JSON output validity and round-trip**
    - **Validates: Requirements 3.1, 3.2, 3.4, 7.6, 10.3, 10.4, 10.5**

  - [ ]* 4.3 Write unit tests for DiffReporter
    - Test known diff scenario with specific expected output
    - Test symmetric results (no differences)
    - Test all asymmetric (every host differs)
    - Test JSON output is valid and parseable
    - _Requirements: 7.2_

- [x] 5. Implement PingScanner orchestration
  - [x] 5.1 Implement `scanner.py`
    - Implement `PingScanner.__init__` with all parameters (subnets, exclusions, thread_count, timeout, retries, retry_delay_ms, scan_mode, ping_count, burst_count, burst_interval, callbacks)
    - Implement `_validate_subnet` verifying /24 CIDR format, raising `ValueError` for invalid formats
    - Implement `_generate_hosts` producing full IP addresses from prefix and filtered octets
    - Implement `scan` method using `ThreadPoolExecutor` with configured thread count to scan both subnets concurrently
    - Integrate `ExclusionFilter` for pre-scan filtering
    - Compute `ScanStats` (min, median, mode, max delay, duration, counts)
    - Invoke `on_result` callback as each ping completes (for real-time GUI updates)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.3, 5.1, 5.2, 5.3, 6.3_

  - [ ]* 5.2 Write property tests for PingScanner
    - **Property 1: Scan completeness**
    - **Property 8: Subnet validation rejects invalid formats**
    - **Property 11: Metrics computation correctness**
    - **Validates: Requirements 1.1, 1.3, 5.2, 8.8**

  - [ ]* 5.3 Write unit tests for PingScanner
    - Test default subnet values
    - Test invalid subnet raises ValueError
    - Test exclusion integration (excluded octets not scanned)
    - Test result count matches expected (254 - excluded per subnet)
    - Mock subprocess for all tests
    - _Requirements: 7.4_

- [x] 6. Checkpoint - Core scan engine complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement DiagnosticExecutor
  - [x] 7.1 Implement `diagnostic_executor.py`
    - Implement `DiagnosticExecutor.__init__` with timeout, ping_count, burst_count, burst_interval; validate ping_count > 0, burst_count > 0, burst_interval >= 0
    - Implement `_execute_ping` (same subprocess approach as PingExecutor)
    - Implement `packet_loss`: send ping_count pings, compute loss_percent = (sent - received) / sent * 100
    - Implement `jitter`: send ping_count pings, compute min/avg/max/stddev of successful response times; stddev is None if fewer than 2 responses
    - Implement `response_under_load`: send burst_count pings at burst_interval spacing, count received, classify as DOWN/DEGRADED/HEALTHY
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10, 6.3_

  - [ ]* 7.2 Write property tests for DiagnosticExecutor
    - **Property 15: Packet loss computation correctness**
    - **Property 16: Jitter statistics computation correctness**
    - **Property 17: Burst received count correctness**
    - **Property 18: Load classification correctness**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8**

  - [ ]* 7.3 Write unit tests for DiagnosticExecutor
    - Test packet loss: 0% loss, 50% loss, 100% loss
    - Test jitter: 0 responses (all None), 1 response (stddev None), 2+ responses (all stats computed)
    - Test response under load: DOWN (0 received), DEGRADED (partial), HEALTHY (all received)
    - Test ValueError for ping_count <= 0, burst_count <= 0, burst_interval < 0
    - Mock subprocess for all tests
    - _Requirements: 7.1_

- [x] 8. Implement DiagnosticReporter
  - [x] 8.1 Implement `diagnostic_reporter.py`
    - Implement `format_packet_loss_report`: human-readable table of per-host loss percentages
    - Implement `format_jitter_report`: human-readable table of per-host min/avg/max/stddev
    - Implement `format_load_report`: human-readable table of per-host received/sent counts and classification
    - Implement `to_json`: serialize diagnostic results to valid JSON with per-host metrics
    - _Requirements: 12.12, 6.3_

  - [ ]* 8.2 Write property tests for DiagnosticReporter
    - **Property 19: Diagnostic results JSON serialization round-trip**
    - **Validates: Requirements 12.12**

  - [ ]* 8.3 Write unit tests for DiagnosticReporter
    - Test packet loss JSON contains loss_percent per host
    - Test jitter JSON contains min/avg/max/stddev per host
    - Test load JSON contains burst_received/burst_sent per host
    - _Requirements: 7.2_

- [x] 9. Integrate diagnostic modes into PingScanner
  - [x] 9.1 Extend `scanner.py` to support advanced scan modes
    - When scan_mode is PACKET_LOSS, JITTER, or RESPONSE_UNDER_LOAD, use DiagnosticExecutor instead of PingExecutor
    - Store results in `diagnostic_results_a` and `diagnostic_results_b` of ScanResults
    - Invoke `on_diagnostic_result` callback as each diagnostic completes
    - _Requirements: 12.9, 12.10_

  - [ ]* 9.2 Write integration tests for diagnostic scan pipeline
    - Test full packet loss scan with mocked subprocess
    - Test full jitter scan with mocked subprocess
    - Test full load scan with mocked subprocess
    - Verify result counts and callback invocations
    - _Requirements: 7.4_

- [x] 10. Checkpoint - All scan engine modes complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement GUI - DotGridWidget
  - [x] 11.1 Implement `gui/dot_grid.py`
    - Implement `DotGridWidget` as a QWidget subclass
    - Initialize 256 dots in NOT_SCANNED (grey) state
    - Implement `update_dot(octet, status)` mapping octet to grid position (row = octet // 16, col = octet % 16)
    - Implement `reset()` to set all dots back to grey
    - Implement `paintEvent` rendering 16x16 colored circles
    - Map DotStatus enum to colors: grey, green, red, white, yellow
    - Implement packet loss gradient coloring: LOSS_NONE=green, LOSS_LOW=yellow, LOSS_HIGH=red, LOSS_TOTAL=white
    - _Requirements: 8.1, 8.2, 8.11, 8.20_

  - [ ]* 11.2 Write property tests for dot status mapping
    - **Property 10: Dot status mapping correctness**
    - **Property 20: Packet loss dot color mapping**
    - **Validates: Requirements 8.2, 8.20**

  - [ ]* 11.3 Write unit tests for DotGridWidget
    - Test initial state: all dots grey
    - Test update_dot changes color correctly
    - Test reset returns all dots to grey
    - Test octet-to-grid mapping (0→(0,0), 255→(15,15))
    - _Requirements: 8.1_

- [x] 12. Implement GUI - ControlPanel and ResultsPanel
  - [x] 12.1 Implement `gui/control_panel.py`
    - Create input fields: subnet A, subnet B, excluded octets (comma-separated), thread count, timeout
    - Create mode-specific fields: retry count, retry delay (ms), ping count, burst count, burst interval (s)
    - Create buttons: "Ping Once", "Ping Retry", "Packet Loss", "Jitter", "Response Under Load"
    - Implement inline validation: non-integer exclusion octets, invalid subnet format, out-of-range values
    - Display validation error messages next to offending fields
    - _Requirements: 8.3, 8.5, 8.9, 8.10, 8.14, 8.16, 8.17, 8.18_

  - [x] 12.2 Implement `gui/results_panel.py`
    - Display asymmetric IP list grouped by direction
    - Display metrics section: total runtime, min/median/mode/max delay
    - Display per-host diagnostic results for advanced modes (loss%, jitter stats, burst counts)
    - _Requirements: 8.7, 8.8, 8.19_

  - [ ]* 12.3 Write property test for exclusion octet parsing
    - **Property 12: Exclusion octet string parsing round-trip**
    - **Validates: Requirements 8.10**

- [x] 13. Implement GUI - ScanController and MainWindow
  - [x] 13.1 Implement `gui/scan_controller.py`
    - Implement `ScanController` as QObject with Qt signals: result_received, diagnostic_result_received, scan_completed, scan_error
    - Implement `start_scan` creating a QThread worker that runs PingScanner.scan()
    - Bridge callbacks to Qt signals for cross-thread communication
    - Implement `is_running` check
    - _Requirements: 8.15_

  - [x] 13.2 Implement `gui/main_window.py`
    - Compose MainWindow with DotGridWidget, ControlPanel, ResultsPanel
    - Connect button signals to scan initiation methods
    - Implement `_on_result_received` to update dot colors in real time
    - Implement `_on_diagnostic_result_received` to update dot colors with gradient/threshold
    - Implement `_on_scan_completed` to display final results and metrics
    - Implement `_set_buttons_enabled` to disable during scan, re-enable after
    - _Requirements: 8.4, 8.6, 8.11, 8.12, 8.13, 8.15, 8.19_

  - [ ]* 13.3 Write unit tests for ScanController and MainWindow
    - Test button state toggling during scan lifecycle
    - Test signal emissions on scan complete
    - Test buttons disabled during scan, enabled after
    - Use pytest-qt's qtbot for widget testing
    - _Requirements: 7.4_

- [x] 14. Implement entry point (`__main__.py`)
  - Implement `__main__.py` with `--cli` flag: if present → CLI mode, else → launch GUI (QApplication + MainWindow)
  - _Requirements: 10.1_

- [x] 15. Checkpoint - GUI complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Implement CLI mode
  - [x] 16.1 Implement `cli.py`
    - Implement `parse_cli_args` using argparse: --subnet-a, --subnet-b, --exclude, --threads, --timeout, --retries, --retry-delay, --mode (ping-once|ping-retry|packet-loss|jitter|load), --ping-count, --burst-count, --burst-interval
    - Implement `run_cli`: create PingScanner with parsed config, run scan, compute diff (for ping modes) or collect diagnostics (for advanced modes), output JSON to stdout
    - Handle invalid arguments: print error to stderr, exit non-zero
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 12.11, 12.12_

  - [ ]* 16.2 Write unit tests for CLI
    - Test valid argument parsing for each mode
    - Test invalid arguments produce stderr error and non-zero exit
    - Test JSON output structure for ping modes (asymmetric IPs + metrics)
    - Test JSON output structure for diagnostic modes (per-host metrics)
    - Test --mode packet-loss with --ping-count
    - Test --mode jitter with --ping-count
    - Test --mode load with --burst-count and --burst-interval
    - Mock subprocess for scan execution
    - _Requirements: 7.4, 10.6_

- [x] 17. Implement PyInstaller packaging
  - [x] 17.1 Create `ip_range_ping_diff.spec` PyInstaller spec file
    - Configure single-file bundling (onefile mode)
    - Declare hidden imports for PySide6 modules
    - Include all application modules
    - Ensure spec file is reproducible (no absolute paths)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 18. Checkpoint - CLI and packaging complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Implement performance benchmarking harness
  - [x] 19.1 Implement `benchmark/harness.py`
    - Implement orchestration: run each implementation strategy against both subnets
    - Measure wall-clock time for each strategy
    - Produce comparison summary with relative performance differences
    - _Requirements: 11.1, 11.6, 11.7_

  - [x] 19.2 Create Bash ping implementation (`benchmark/ping_bash.sh`)
    - Shell script that pings all hosts in two /24 subnets sequentially or with limited parallelism
    - Output timing results to stdout
    - _Requirements: 11.3_

  - [x] 19.3 Create C ping implementation (`benchmark/ping_c/`)
    - Implement `ping_scan.c` using raw sockets or system ping
    - Create `Makefile` for building
    - _Requirements: 11.4_

  - [x] 19.4 Create Rust ping implementation (`benchmark/ping_rust/`)
    - Set up `Cargo.toml` with dependencies
    - Implement `src/main.rs` with concurrent ping scanning
    - _Requirements: 11.5_

  - [x] 19.5 Integrate Python subprocess benchmark into harness
    - Wrap the existing Python PingScanner as one benchmark strategy
    - _Requirements: 11.2_

- [x] 20. Final checkpoint - All implementation complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation between major phases
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All tests mock `subprocess.run` — no live network required
- The implementation language is Python 3.11 as specified in the design
