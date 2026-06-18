"""Control panel for scan configuration and mode selection.

This module provides the ControlPanel widget containing all user-configurable
input fields (subnets, exclusions, thread count, timeout, retry settings,
diagnostic mode parameters) and five scan mode buttons. Inline validation
displays red error labels next to fields with invalid values.

Referenced requirements: 8.3, 8.5, 8.9, 8.10, 8.14, 8.16, 8.17, 8.18
"""

from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ip_range_ping_diff.config import (
    DEFAULT_BURST_COUNT,
    DEFAULT_BURST_INTERVAL,
    DEFAULT_PING_COUNT,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_DELAY_MS,
    DEFAULT_SUBNET_A,
    DEFAULT_SUBNET_B,
    DEFAULT_THREAD_COUNT,
    DEFAULT_TIMEOUT,
)

# Regex for validating /24 CIDR notation subnet format
_SUBNET_PATTERN = re.compile(
    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/24$"
)


class ControlPanel(QWidget):
    """Control panel with scan configuration fields and mode buttons.

    Provides input fields for all scan parameters, five scan mode buttons,
    and inline validation that shows red error labels next to invalid fields.

    Signals:
        ping_once_clicked: Emitted when "Ping Once" button is pressed.
        ping_retry_clicked: Emitted when "Ping Retry" button is pressed.
        packet_loss_clicked: Emitted when "Packet Loss" button is pressed.
        jitter_clicked: Emitted when "Jitter" button is pressed.
        response_under_load_clicked: Emitted when "Response Under Load"
            button is pressed.
    """

    # Signals emitted when scan mode buttons are clicked
    ping_once_clicked = Signal()
    ping_retry_clicked = Signal()
    sequential_clicked = Signal()
    packet_loss_clicked = Signal()
    jitter_clicked = Signal()
    response_under_load_clicked = Signal()

    # Signals emitted when benchmark buttons are clicked
    bench_python_clicked = Signal()
    bench_bash_clicked = Signal()
    bench_c_clicked = Signal()
    bench_rust_clicked = Signal()
    bench_all_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the control panel with default field values."""
        super().__init__(parent)

        self._error_labels: dict[str, QLabel] = {}
        self._setup_ui()
        self._connect_buttons()

    def _setup_ui(self) -> None:
        """Build the complete control panel layout."""
        main_layout = QVBoxLayout(self)

        # --- Common Configuration Group ---
        common_group = QGroupBox("Common Configuration")
        common_layout = QGridLayout()

        # Row 0: Subnet A
        common_layout.addWidget(QLabel("Subnet A:"), 0, 0)
        self.subnet_a_input = QLineEdit(DEFAULT_SUBNET_A)
        self.subnet_a_input.setPlaceholderText("e.g. 192.168.1.0/24")
        common_layout.addWidget(self.subnet_a_input, 0, 1)
        self._error_labels["subnet_a"] = self._create_error_label()
        common_layout.addWidget(self._error_labels["subnet_a"], 0, 2)

        # Row 1: Subnet B
        common_layout.addWidget(QLabel("Subnet B:"), 1, 0)
        self.subnet_b_input = QLineEdit(DEFAULT_SUBNET_B)
        self.subnet_b_input.setPlaceholderText("e.g. 192.168.2.0/24")
        common_layout.addWidget(self.subnet_b_input, 1, 1)
        self._error_labels["subnet_b"] = self._create_error_label()
        common_layout.addWidget(self._error_labels["subnet_b"], 1, 2)

        # Row 2: Excluded Octets
        common_layout.addWidget(QLabel("Excluded Octets:"), 2, 0)
        self.excluded_octets_input = QLineEdit()
        self.excluded_octets_input.setPlaceholderText(
            "Comma-separated integers, e.g. 0,255"
        )
        common_layout.addWidget(self.excluded_octets_input, 2, 1)
        self._error_labels["excluded_octets"] = self._create_error_label()
        common_layout.addWidget(self._error_labels["excluded_octets"], 2, 2)

        # Row 3: Thread Count
        common_layout.addWidget(QLabel("Thread Count:"), 3, 0)
        self.thread_count_input = QSpinBox()
        self.thread_count_input.setRange(1, 512)
        self.thread_count_input.setValue(DEFAULT_THREAD_COUNT)
        common_layout.addWidget(self.thread_count_input, 3, 1)
        self._error_labels["thread_count"] = self._create_error_label()
        common_layout.addWidget(self._error_labels["thread_count"], 3, 2)

        # Row 4: Timeout
        common_layout.addWidget(QLabel("Timeout (s):"), 4, 0)
        self.timeout_input = QDoubleSpinBox()
        self.timeout_input.setRange(0.1, 30.0)
        self.timeout_input.setDecimals(1)
        self.timeout_input.setSingleStep(0.5)
        self.timeout_input.setValue(DEFAULT_TIMEOUT)
        common_layout.addWidget(self.timeout_input, 4, 1)
        self._error_labels["timeout"] = self._create_error_label()
        common_layout.addWidget(self._error_labels["timeout"], 4, 2)

        common_group.setLayout(common_layout)
        main_layout.addWidget(common_group)

        # --- Retry Configuration Group ---
        retry_group = QGroupBox("Retry Configuration")
        retry_layout = QGridLayout()

        # Retry Count
        retry_layout.addWidget(QLabel("Retry Count:"), 0, 0)
        self.retry_count_input = QSpinBox()
        self.retry_count_input.setRange(0, 100)
        self.retry_count_input.setValue(DEFAULT_RETRIES)
        retry_layout.addWidget(self.retry_count_input, 0, 1)
        self._error_labels["retry_count"] = self._create_error_label()
        retry_layout.addWidget(self._error_labels["retry_count"], 0, 2)

        # Retry Delay
        retry_layout.addWidget(QLabel("Retry Delay (ms):"), 1, 0)
        self.retry_delay_input = QDoubleSpinBox()
        self.retry_delay_input.setRange(0.0, 10000.0)
        self.retry_delay_input.setDecimals(1)
        self.retry_delay_input.setSingleStep(50.0)
        self.retry_delay_input.setValue(DEFAULT_RETRY_DELAY_MS)
        retry_layout.addWidget(self.retry_delay_input, 1, 1)
        self._error_labels["retry_delay"] = self._create_error_label()
        retry_layout.addWidget(self._error_labels["retry_delay"], 1, 2)

        retry_group.setLayout(retry_layout)
        main_layout.addWidget(retry_group)

        # --- Diagnostic Mode Configuration Group ---
        diag_group = QGroupBox("Diagnostic Mode Configuration")
        diag_layout = QGridLayout()

        # Ping Count (for Packet Loss and Jitter modes)
        diag_layout.addWidget(QLabel("Ping Count:"), 0, 0)
        self.ping_count_input = QSpinBox()
        self.ping_count_input.setRange(1, 1000)
        self.ping_count_input.setValue(DEFAULT_PING_COUNT)
        diag_layout.addWidget(self.ping_count_input, 0, 1)
        self._error_labels["ping_count"] = self._create_error_label()
        diag_layout.addWidget(self._error_labels["ping_count"], 0, 2)

        # Burst Count (for Response Under Load mode)
        diag_layout.addWidget(QLabel("Burst Count:"), 1, 0)
        self.burst_count_input = QSpinBox()
        self.burst_count_input.setRange(1, 1000)
        self.burst_count_input.setValue(DEFAULT_BURST_COUNT)
        diag_layout.addWidget(self.burst_count_input, 1, 1)
        self._error_labels["burst_count"] = self._create_error_label()
        diag_layout.addWidget(self._error_labels["burst_count"], 1, 2)

        # Burst Interval (for Response Under Load mode)
        diag_layout.addWidget(QLabel("Burst Interval (s):"), 2, 0)
        self.burst_interval_input = QDoubleSpinBox()
        self.burst_interval_input.setRange(0.01, 10.0)
        self.burst_interval_input.setDecimals(2)
        self.burst_interval_input.setSingleStep(0.05)
        self.burst_interval_input.setValue(DEFAULT_BURST_INTERVAL)
        diag_layout.addWidget(self.burst_interval_input, 2, 1)
        self._error_labels["burst_interval"] = self._create_error_label()
        diag_layout.addWidget(self._error_labels["burst_interval"], 2, 2)

        diag_group.setLayout(diag_layout)
        main_layout.addWidget(diag_group)

        # --- Scan Mode Buttons ---
        buttons_group = QGroupBox("Scan Modes")
        buttons_layout = QHBoxLayout()

        self.ping_once_button = QPushButton("Ping Once")
        self.ping_retry_button = QPushButton("Ping Retry")
        self.sequential_button = QPushButton("Sequential")
        self.packet_loss_button = QPushButton("Packet Loss")
        self.jitter_button = QPushButton("Jitter")
        self.response_under_load_button = QPushButton("Response Under Load")

        # Style sequential button to indicate it's the low-resource option
        self.sequential_button.setToolTip(
            "Single-thread, one host at a time. Minimal CPU/memory usage."
        )

        buttons_layout.addWidget(self.ping_once_button)
        buttons_layout.addWidget(self.ping_retry_button)
        buttons_layout.addWidget(self.sequential_button)
        buttons_layout.addWidget(self.packet_loss_button)
        buttons_layout.addWidget(self.jitter_button)
        buttons_layout.addWidget(self.response_under_load_button)

        buttons_group.setLayout(buttons_layout)
        main_layout.addWidget(buttons_group)

        # --- Benchmark Buttons ---
        bench_group = QGroupBox("Benchmark (by language)")
        bench_layout = QHBoxLayout()

        self.bench_python_button = QPushButton("Python")
        self.bench_bash_button = QPushButton("Bash")
        self.bench_c_button = QPushButton("C")
        self.bench_rust_button = QPushButton("Rust")
        self.bench_all_button = QPushButton("Run All")

        # Style the Run All button to stand out
        self.bench_all_button.setStyleSheet("font-weight: bold;")

        bench_layout.addWidget(self.bench_python_button)
        bench_layout.addWidget(self.bench_bash_button)
        bench_layout.addWidget(self.bench_c_button)
        bench_layout.addWidget(self.bench_rust_button)
        bench_layout.addWidget(self.bench_all_button)

        bench_group.setLayout(bench_layout)
        main_layout.addWidget(bench_group)

        main_layout.addStretch()

    def _connect_buttons(self) -> None:
        """Connect button click signals to validation-and-emit logic."""
        self.ping_once_button.clicked.connect(self._on_ping_once)
        self.ping_retry_button.clicked.connect(self._on_ping_retry)
        self.sequential_button.clicked.connect(self._on_sequential)
        self.packet_loss_button.clicked.connect(self._on_packet_loss)
        self.jitter_button.clicked.connect(self._on_jitter)
        self.response_under_load_button.clicked.connect(
            self._on_response_under_load
        )

        # Benchmark buttons emit directly (no validation needed)
        self.bench_python_button.clicked.connect(self.bench_python_clicked.emit)
        self.bench_bash_button.clicked.connect(self.bench_bash_clicked.emit)
        self.bench_c_button.clicked.connect(self.bench_c_clicked.emit)
        self.bench_rust_button.clicked.connect(self.bench_rust_clicked.emit)
        self.bench_all_button.clicked.connect(self.bench_all_clicked.emit)

    def _on_ping_once(self) -> None:
        """Validate common fields and emit ping_once_clicked if valid."""
        if self._validate_common():
            self.ping_once_clicked.emit()

    def _on_ping_retry(self) -> None:
        """Validate common + retry fields and emit ping_retry_clicked."""
        if self._validate_common() and self._validate_retry():
            self.ping_retry_clicked.emit()

    def _on_sequential(self) -> None:
        """Validate common fields and emit sequential_clicked."""
        if self._validate_common():
            self.sequential_clicked.emit()

    def _on_packet_loss(self) -> None:
        """Validate common + diagnostic fields and emit packet_loss_clicked."""
        if self._validate_common() and self._validate_diagnostic():
            self.packet_loss_clicked.emit()

    def _on_jitter(self) -> None:
        """Validate common + diagnostic fields and emit jitter_clicked."""
        if self._validate_common() and self._validate_diagnostic():
            self.jitter_clicked.emit()

    def _on_response_under_load(self) -> None:
        """Validate common + diagnostic fields and emit signal."""
        if self._validate_common() and self._validate_diagnostic():
            self.response_under_load_clicked.emit()

    # --- Validation Methods ---

    def _validate_common(self) -> bool:
        """Validate common configuration fields.

        Checks subnet format and excluded octets parsing. Returns True
        if all common fields are valid.
        """
        valid = True

        # Validate Subnet A
        if not self._validate_subnet(
            self.subnet_a_input.text(), "subnet_a"
        ):
            valid = False

        # Validate Subnet B
        if not self._validate_subnet(
            self.subnet_b_input.text(), "subnet_b"
        ):
            valid = False

        # Validate Excluded Octets
        if not self._validate_excluded_octets():
            valid = False

        return valid

    def _validate_subnet(self, value: str, field_key: str) -> bool:
        """Validate a subnet string against /24 CIDR format.

        Args:
            value: The subnet string to validate.
            field_key: The key in _error_labels for this field.

        Returns:
            True if the subnet format is valid.
        """
        value = value.strip()
        if not value:
            self._show_error(field_key, "Subnet cannot be empty")
            return False

        if not _SUBNET_PATTERN.match(value):
            self._show_error(field_key, "Invalid format. Use X.X.X.X/24")
            return False

        # Validate each octet is 0-255
        ip_part = value.split("/")[0]
        octets = ip_part.split(".")
        for octet_str in octets:
            try:
                octet_val = int(octet_str)
                if not 0 <= octet_val <= 255:
                    self._show_error(
                        field_key, f"Octet {octet_val} out of range 0-255"
                    )
                    return False
            except ValueError:
                self._show_error(field_key, "Invalid IP address octets")
                return False

        self._clear_error(field_key)
        return True

    def _validate_excluded_octets(self) -> bool:
        """Validate the excluded octets field.

        Checks that the comma-separated values are all integers in 0-255.

        Returns:
            True if valid or empty (empty means no exclusions).
        """
        text = self.excluded_octets_input.text().strip()
        if not text:
            self._clear_error("excluded_octets")
            return True

        parts = text.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                val = int(part)
            except ValueError:
                self._show_error(
                    "excluded_octets",
                    f"Non-integer value: '{part}'",
                )
                return False
            if not 0 <= val <= 255:
                self._show_error(
                    "excluded_octets",
                    f"Octet {val} out of range 0-255",
                )
                return False

        self._clear_error("excluded_octets")
        return True

    def _validate_retry(self) -> bool:
        """Validate retry-specific fields. Always valid via QSpinBox constraints."""
        self._clear_error("retry_count")
        self._clear_error("retry_delay")
        return True

    def _validate_diagnostic(self) -> bool:
        """Validate diagnostic-specific fields. Always valid via QSpinBox constraints."""
        self._clear_error("ping_count")
        self._clear_error("burst_count")
        self._clear_error("burst_interval")
        return True

    # --- Error Display Helpers ---

    def _create_error_label(self) -> QLabel:
        """Create a red-colored QLabel for displaying validation errors.

        Returns:
            A QLabel styled with red text, initially hidden (empty text).
        """
        label = QLabel("")
        label.setStyleSheet("color: red; font-size: 11px;")
        label.setWordWrap(True)
        return label

    def _show_error(self, field_key: str, message: str) -> None:
        """Display a validation error message next to the specified field.

        Args:
            field_key: Key identifying which error label to update.
            message: The error message to display.
        """
        if field_key in self._error_labels:
            self._error_labels[field_key].setText(message)

    def _clear_error(self, field_key: str) -> None:
        """Clear the validation error message for the specified field.

        Args:
            field_key: Key identifying which error label to clear.
        """
        if field_key in self._error_labels:
            self._error_labels[field_key].setText("")

    def clear_all_errors(self) -> None:
        """Clear all validation error messages."""
        for label in self._error_labels.values():
            label.setText("")

    # --- Value Accessor Methods ---

    def get_subnet_a(self) -> str:
        """Return the current Subnet A value."""
        return self.subnet_a_input.text().strip()

    def get_subnet_b(self) -> str:
        """Return the current Subnet B value."""
        return self.subnet_b_input.text().strip()

    def get_excluded_octets(self) -> set[int]:
        """Parse and return the set of excluded octets.

        Returns:
            A set of integers representing excluded octets, or an empty
            set if the field is empty.
        """
        text = self.excluded_octets_input.text().strip()
        if not text:
            return set()
        result = set()
        for part in text.split(","):
            part = part.strip()
            if part:
                result.add(int(part))
        return result

    def get_thread_count(self) -> int:
        """Return the current thread count value."""
        return self.thread_count_input.value()

    def get_timeout(self) -> float:
        """Return the current timeout value in seconds."""
        return self.timeout_input.value()

    def get_retry_count(self) -> int:
        """Return the current retry count value."""
        return self.retry_count_input.value()

    def get_retry_delay_ms(self) -> float:
        """Return the current retry delay value in milliseconds."""
        return self.retry_delay_input.value()

    def get_ping_count(self) -> int:
        """Return the current ping count value."""
        return self.ping_count_input.value()

    def get_burst_count(self) -> int:
        """Return the current burst count value."""
        return self.burst_count_input.value()

    def get_burst_interval(self) -> float:
        """Return the current burst interval value in seconds."""
        return self.burst_interval_input.value()

    def set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all scan mode and benchmark buttons.

        Args:
            enabled: True to enable buttons, False to disable.
        """
        self.ping_once_button.setEnabled(enabled)
        self.ping_retry_button.setEnabled(enabled)
        self.sequential_button.setEnabled(enabled)
        self.packet_loss_button.setEnabled(enabled)
        self.jitter_button.setEnabled(enabled)
        self.response_under_load_button.setEnabled(enabled)
        self.bench_python_button.setEnabled(enabled)
        self.bench_bash_button.setEnabled(enabled)
        self.bench_c_button.setEnabled(enabled)
        self.bench_rust_button.setEnabled(enabled)
        self.bench_all_button.setEnabled(enabled)
