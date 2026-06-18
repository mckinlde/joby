"""Color legend widget for the dot grid.

Displays a visual key explaining what each dot color means in the
current scan mode. The legend updates depending on whether a standard
ping mode or a diagnostic (packet loss) mode is active.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from ip_range_ping_diff.gui.dot_grid import _STATUS_COLORS
from ip_range_ping_diff.models import DotStatus, ScanMode


# Legend entries for standard ping modes (Ping Once, Ping Retry)
_STANDARD_LEGEND: list[tuple[DotStatus, str]] = [
    (DotStatus.NOT_SCANNED, "Not scanned"),
    (DotStatus.REACHABLE_BOTH, "Reachable on both subnets"),
    (DotStatus.ASYMMETRIC, "Asymmetric (one subnet only)"),
    (DotStatus.UNREACHABLE_BOTH, "Unreachable on both subnets"),
]

# Legend entries for packet loss mode
_PACKET_LOSS_LEGEND: list[tuple[DotStatus, str]] = [
    (DotStatus.NOT_SCANNED, "Not scanned"),
    (DotStatus.LOSS_NONE, "0% packet loss"),
    (DotStatus.LOSS_LOW, "1–49% packet loss"),
    (DotStatus.LOSS_HIGH, "50–99% packet loss"),
    (DotStatus.LOSS_TOTAL, "100% packet loss (down)"),
]

# Legend entries for jitter / response under load modes
_DIAGNOSTIC_LEGEND: list[tuple[DotStatus, str]] = [
    (DotStatus.NOT_SCANNED, "Not scanned"),
    (DotStatus.REACHABLE_BOTH, "Responding"),
    (DotStatus.UNREACHABLE_BOTH, "No response"),
]

# Dot diameter for legend swatches
_SWATCH_SIZE = 14


class ColorLegend(QWidget):
    """Color key widget explaining dot grid colors.

    Shows colored circles paired with text labels indicating what each
    color means. The legend can be switched between standard ping mode
    and packet loss mode via set_mode().
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize with standard ping mode legend."""
        super().__init__(parent)
        self._entries: list[tuple[DotStatus, str]] = list(_STANDARD_LEGEND)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the legend layout with current entries."""
        # Clear existing layout if any
        if self.layout() is not None:
            # Remove all child widgets
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        layout = QVBoxLayout(self) if self.layout() is None else self.layout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        # Title label
        title = QLabel("<b>Color Key</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # Add each legend entry
        for status, label_text in self._entries:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Color swatch
            swatch = _ColorSwatch(status)
            row_layout.addWidget(swatch)

            # Text label
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 11px;")
            row_layout.addWidget(label)
            row_layout.addStretch()

            layout.addWidget(row_widget)

        layout.addStretch()

    def set_mode(self, mode: ScanMode) -> None:
        """Update the legend to reflect the given scan mode.

        Args:
            mode: The active ScanMode determining which color key to show.
        """
        if mode == ScanMode.PACKET_LOSS:
            new_entries = _PACKET_LOSS_LEGEND
        elif mode in (ScanMode.JITTER, ScanMode.RESPONSE_UNDER_LOAD):
            new_entries = _DIAGNOSTIC_LEGEND
        else:
            new_entries = _STANDARD_LEGEND

        # Only rebuild if entries changed
        if new_entries != self._entries:
            self._entries = list(new_entries)
            self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        """Tear down and rebuild the legend entries."""
        # Remove all widgets from layout
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Rebuild with new entries
        title = QLabel("<b>Color Key</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        for status, label_text in self._entries:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            swatch = _ColorSwatch(status)
            row_layout.addWidget(swatch)

            label = QLabel(label_text)
            label.setStyleSheet("font-size: 11px;")
            row_layout.addWidget(label)
            row_layout.addStretch()

            layout.addWidget(row_widget)

        layout.addStretch()


class _ColorSwatch(QWidget):
    """A small colored circle used as a legend swatch."""

    def __init__(self, status: DotStatus, parent: QWidget | None = None) -> None:
        """Initialize swatch with the given status color.

        Args:
            status: The DotStatus whose color to display.
        """
        super().__init__(parent)
        self._color: QColor = _STATUS_COLORS.get(
            status, QColor(180, 180, 180)
        )
        self.setFixedSize(_SWATCH_SIZE + 2, _SWATCH_SIZE + 2)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the colored circle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(1, 1, _SWATCH_SIZE, _SWATCH_SIZE)
        painter.end()
