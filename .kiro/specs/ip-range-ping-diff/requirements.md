# Requirements Document

## Introduction

This feature implements a Python 3.11 tool that pings two /24 IP address ranges (192.168.1.0/24 and 192.168.2.0/24) concurrently and reports asymmetric reachability — IP addresses (by last octet) that are pingable on one subnet but not on the other. The tool supports two scanning modes: a simple single-pass ping ("Ping Once") and a retry-based ping ("Ping Retry") with a user-specified retry count. It presents results through a PySide6 graphical user interface featuring a 16x16 dot grid visualization. The scan logic is also independently runnable from the command line, producing JSON output. The application is packaged as a standalone executable using PyInstaller for easy distribution.

## Glossary

- **Ping_Scanner**: The main system component responsible for orchestrating concurrent ping operations across IP ranges and collecting results.
- **Ping_Executor**: The component responsible for executing individual ping operations against a single IP address, including optional retry logic.
- **Diff_Reporter**: The component responsible for comparing ping results between two subnets and producing the asymmetric reachability report.
- **Exclusion_Filter**: The component responsible for filtering out specific host addresses (by last octet) from the scan.
- **Subnet**: A /24 IP address range containing 256 addresses (host octets 0–255, though typically 1–254 are scanned).
- **Asymmetric_Reachability**: A condition where a host octet is pingable on one subnet but not on the corresponding address in the other subnet.
- **Last_Octet**: The fourth and final segment of an IPv4 address, identifying the host within a /24 subnet.
- **Retry_Count**: The number of additional ping attempts made after an initial ping failure, specified by the user for the "Ping Retry" mode.
- **Dot_Grid**: A 16x16 grid of 256 dots in the GUI, where each dot represents a host octet (0–255) and is color-coded by reachability status.
- **GUI_Application**: The PySide6-based graphical user interface that provides a dot grid visualization, operation buttons, and result displays.
- **Main_Window**: The primary application window containing the dot grid, operation buttons, asymmetric IP list, and metrics section.
- **Scan_Controller**: The GUI component that manages the lifecycle of a scan (start, completion) and bridges the GUI thread with the scanning logic.
- **CLI_Mode**: The command-line interface mode allowing the Python scan script to be run independently of the GUI, producing JSON output.
- **Metrics_Section**: The GUI component displaying scan performance statistics including total runtime and ping response delay statistics.
- **PyInstaller_Bundle**: The standalone executable produced by PyInstaller that packages the Python runtime, PySide6 libraries, and application code into a single distributable file.

## Requirements

### Requirement 1: Concurrent Ping Scanning

**User Story:** As a network administrator, I want to ping all addresses in two /24 subnets concurrently, so that the scan completes quickly even with 500+ addresses to check.

#### Acceptance Criteria

1. WHEN a scan is initiated, THE Ping_Scanner SHALL ping all host addresses (octets 1–254) in both 192.168.1.0/24 and 192.168.2.0/24 concurrently using Python asyncio or concurrent.futures.
2. THE Ping_Scanner SHALL execute concurrent pings using a user-specified thread count to control parallelism.
3. WHEN a scan is initiated, THE Ping_Scanner SHALL return a result set containing the reachability status (reachable or unreachable) of each scanned IP address.
4. THE Ping_Scanner SHALL use a user-specified timeout value for each individual ping operation.

### Requirement 2: Ping Retry Strategy

**User Story:** As a network administrator, I want to optionally retry failed pings a specified number of times, so that transient failures do not produce false negatives when I choose the retry mode.

#### Acceptance Criteria

1. WHEN operating in "Ping Once" mode, THE Ping_Executor SHALL attempt each ping exactly once with no retries.
2. WHEN operating in "Ping Retry" mode, THE Ping_Executor SHALL retry failed pings up to a user-specified retry count before classifying the host as unreachable.
3. THE Ping_Executor SHALL classify an IP address as reachable if any single ping attempt (initial or retry) succeeds.
4. WHEN a ping attempt succeeds, THE Ping_Executor SHALL not perform additional retry attempts for that address.
5. THE Ping_Executor SHALL classify an IP address as unreachable only after the initial attempt plus all retry attempts have been exhausted without a successful response.
6. THE Ping_Executor SHALL use the same user-specified timeout for each individual ping attempt (initial and retries).

### Requirement 3: Asymmetric Reachability Reporting

**User Story:** As a network administrator, I want to see which host addresses are reachable on one subnet but not the other, so that I can identify and troubleshoot asymmetric network issues.

#### Acceptance Criteria

1. WHEN scan results from both subnets are available, THE Diff_Reporter SHALL identify all last octets where the address is reachable in subnet 192.168.1.0/24 but unreachable in subnet 192.168.2.0/24.
2. WHEN scan results from both subnets are available, THE Diff_Reporter SHALL identify all last octets where the address is reachable in subnet 192.168.2.0/24 but unreachable in subnet 192.168.1.0/24.
3. THE Diff_Reporter SHALL present asymmetric results grouped by direction (reachable on first subnet only, reachable on second subnet only).
4. THE Diff_Reporter SHALL include the full IP address of both the reachable and unreachable host in each reported difference.

### Requirement 4: Host Address Exclusion

**User Story:** As a network administrator, I want to exclude specific host addresses by last octet from both subnets, so that I can skip known-irrelevant addresses (e.g., gateways, broadcast) and focus on meaningful results.

#### Acceptance Criteria

1. WHEN a list of excluded last octets is provided, THE Exclusion_Filter SHALL remove all IP addresses with those last octets from both subnets before scanning begins.
2. THE Exclusion_Filter SHALL accept a collection of integer values representing last octets to exclude.
3. WHEN an excluded last octet appears in scan results, THE Diff_Reporter SHALL not include that octet in the asymmetric reachability report.
4. IF an excluded octet value is outside the valid range 0–255, THEN THE Exclusion_Filter SHALL raise a ValueError with a descriptive message.

### Requirement 5: Configurable Subnet Inputs

**User Story:** As a network administrator, I want to specify which two subnets to compare, so that the tool can be reused across different network segments.

#### Acceptance Criteria

1. THE Ping_Scanner SHALL accept two subnet prefixes (in the form "192.168.X.0/24") as input parameters.
2. IF an invalid subnet format is provided, THEN THE Ping_Scanner SHALL raise a ValueError with a descriptive error message.
3. THE Ping_Scanner SHALL default to scanning 192.168.1.0/24 and 192.168.2.0/24 when no subnets are explicitly provided.

### Requirement 6: Python 3.11 Compatibility and Code Quality

**User Story:** As a developer, I want the code to run on Python 3.11 and comply with PEP 8, so that it integrates cleanly into existing tooling and passes linting checks.

#### Acceptance Criteria

1. THE Ping_Scanner SHALL be compatible with Python 3.11 and use only standard library modules or well-known third-party packages.
2. THE Ping_Scanner SHALL pass PEP 8 validation with no errors.
3. THE Ping_Scanner SHALL include docstrings on all public modules, classes, and functions.
4. THE Ping_Scanner SHALL include inline comments explaining non-obvious logic.

### Requirement 7: Test Coverage

**User Story:** As a developer, I want comprehensive tests including mocks and unit tests, so that I can verify correct behavior without requiring a live network.

#### Acceptance Criteria

1. THE Test_Suite SHALL include unit tests that verify the Ping_Executor retry logic using mocked subprocess calls.
2. THE Test_Suite SHALL include unit tests that verify the Diff_Reporter correctly identifies asymmetric reachability from known input data.
3. THE Test_Suite SHALL include unit tests that verify the Exclusion_Filter correctly removes specified octets.
4. THE Test_Suite SHALL include integration tests that verify the full scan-and-diff pipeline using mocked ping responses.
5. THE Test_Suite SHALL achieve test coverage of all public functions and branches in the core modules.
6. FOR ALL sets of ping results, diffing then formatting SHALL produce output consistent with the input reachability data (round-trip property).

### Requirement 8: PySide6 GUI Application with Dot Grid Visualization

**User Story:** As a network administrator, I want a graphical user interface with a 16x16 dot grid showing host reachability at a glance and operation buttons for running scans, so that I can visually assess network status and initiate scans with chosen parameters.

#### Acceptance Criteria

1. THE GUI_Application SHALL display a 16x16 Dot_Grid (256 dots total) where each dot represents a host octet from 0 to 255.
2. THE GUI_Application SHALL color each dot in the Dot_Grid based on scan status: grey for not yet scanned, green for reachable on both subnets, red for asymmetric reachability, and white for unreachable on both subnets.
3. THE GUI_Application SHALL provide a "Ping Once" button with user-configurable parameters for thread count and timeout.
4. WHEN the "Ping Once" button is pressed, THE Ping_Scanner SHALL ping each host in order using the specified thread count and timeout with no retries.
5. THE GUI_Application SHALL provide a "Ping Retry" button with user-configurable parameters for thread count, timeout, and retry count.
6. WHEN the "Ping Retry" button is pressed, THE Ping_Scanner SHALL ping each host using the specified thread count, timeout, and retry count, retrying failed pings the specified number of times before classifying a host as unreachable.
7. THE GUI_Application SHALL display a list of asymmetric IPs below the Dot_Grid, showing hosts that are pingable on one subnet but not the other.
8. THE GUI_Application SHALL display a metrics section below the asymmetric IP list, showing total scan runtime, and minimum, median, mode, and maximum ping response delay.
9. THE GUI_Application SHALL provide input fields for specifying the two /24 subnet prefixes to scan (defaulting to 192.168.1.0/24 and 192.168.2.0/24).
10. THE GUI_Application SHALL provide an input field for specifying exclusion octets as a comma-separated list of integers.
11. WHILE a scan is in progress, THE GUI_Application SHALL update dot colors in real time as results arrive.
12. WHILE a scan is in progress, THE GUI_Application SHALL disable both the "Ping Once" and "Ping Retry" buttons to prevent concurrent scans.
13. WHILE no scan is in progress, THE GUI_Application SHALL enable both the "Ping Once" and "Ping Retry" buttons.
14. IF invalid input is provided in any configuration field (e.g., non-integer exclusion octets, invalid subnet format), THEN THE GUI_Application SHALL display an inline validation error message next to the offending field and prevent the scan from starting.
15. THE GUI_Application SHALL use PySide6 (Qt for Python) as the GUI framework and remain responsive during scans by running scan logic on a background thread or via Qt's async integration.

### Requirement 9: PyInstaller Packaging

**User Story:** As a network administrator, I want the application packaged as a standalone executable, so that I can distribute and run it on machines without requiring a Python installation.

#### Acceptance Criteria

1. THE PyInstaller_Bundle SHALL produce a single-file executable that includes the Python runtime, PySide6 libraries, and all application code.
2. WHEN the standalone executable is launched, THE PyInstaller_Bundle SHALL display the GUI_Application main window without requiring any external dependencies or a Python installation on the target machine.
3. THE PyInstaller_Bundle SHALL be generated using a PyInstaller spec file (`.spec`) checked into the repository for reproducible builds.
4. IF the packaging process encounters missing hidden imports, THEN THE PyInstaller_Bundle spec file SHALL explicitly list all required hidden imports for PySide6 and application modules.

### Requirement 10: CLI Mode with JSON Output

**User Story:** As a network administrator, I want to run the scan logic from the command line independently of the GUI, so that I can integrate scan results into scripts and automation pipelines.

#### Acceptance Criteria

1. THE CLI_Mode SHALL allow the Python scan script to be invoked from the command line without launching the GUI_Application.
2. THE CLI_Mode SHALL accept command-line arguments for subnet prefixes, exclusion octets, thread count, timeout, and retry count.
3. WHEN the scan completes in CLI_Mode, THE CLI_Mode SHALL output the asymmetric IP list as a JSON array containing objects with the full IP addresses and direction of asymmetry.
4. WHEN the scan completes in CLI_Mode, THE CLI_Mode SHALL output metrics as a JSON object containing total runtime, minimum ping delay, median ping delay, mode ping delay, and maximum ping delay.
5. THE CLI_Mode SHALL output all results as a single valid JSON document to standard output.
6. IF invalid arguments are provided, THEN THE CLI_Mode SHALL print a descriptive error message to standard error and exit with a non-zero exit code.

### Requirement 11: Ping Implementation Performance Investigation

**User Story:** As a developer, I want to benchmark different ping implementation strategies, so that I can understand the performance ceiling and choose the optimal approach for production use.

#### Acceptance Criteria

1. THE Ping_Scanner project SHALL include a benchmarking harness that measures ping scan performance across multiple implementation strategies.
2. THE benchmarking harness SHALL measure performance of Python-driven ping (subprocess calling system ping).
3. THE benchmarking harness SHALL measure performance of Bash-driven ping (shell script executing ping commands).
4. THE benchmarking harness SHALL measure performance of a C implementation of the ping scan logic.
5. THE benchmarking harness SHALL measure performance of a Rust implementation of the ping scan logic.
6. THE benchmarking harness SHALL report wall-clock time for a complete scan of both subnets for each implementation strategy.
7. THE benchmarking harness SHALL produce a comparison summary showing relative performance differences between implementations.
