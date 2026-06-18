"""16x16 dot grid visualization of host reachability.

This module provides the DotGridWidget, a QWidget that renders a 16x16 grid
of colored circles representing the scan status of 256 host octets (0–255).
Each dot maps to a specific octet via: row = octet // 16, col = octet % 16.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from ip_range_ping_diff.models import DotStatus

# Grid layout constants
GRID_SIZE = 16  # 16 rows x 16 columns = 256 dots
DOT_DIAMETER = 20  # Each dot is 20px diameter
DOT_SPACING = 5  # 5px spacing between dots
CELL_SIZE = DOT_DIAMETER + DOT_SPACING  # Total cell size per dot

# Color mapping for each DotStatus value
_STATUS_COLORS: dict[DotStatus, QColor] = {
    DotStatus.NOT_SCANNED: QColor(180, 180, 180),  # grey
    DotStatus.REACHABLE_BOTH: QColor(0, 200, 0),  # green
    DotStatus.ASYMMETRIC: QColor(220, 0, 0),  # red
    DotStatus.UNREACHABLE_BOTH: QColor(255, 255, 255),  # white
    DotStatus.PENDING_REACHABLE: QColor(70, 130, 220),  # blue
    DotStatus.PENDING_UNREACHABLE: QColor(120, 120, 120),  # dark grey
    DotStatus.LOSS_NONE: QColor(0, 200, 0),  # green (0% loss)
    DotStatus.LOSS_LOW: QColor(255, 200, 0),  # yellow (1–49% loss)
    DotStatus.LOSS_HIGH: QColor(220, 0, 0),  # red (50–99% loss)
    DotStatus.LOSS_TOTAL: QColor(255, 255, 255),  # white (100% loss)
}


def status_to_color(status: DotStatus) -> QColor:
    """Map a DotStatus enum value to its corresponding QColor.

    Args:
        status: The DotStatus value to look up.

    Returns:
        The QColor associated with the given status.
    """
    return _STATUS_COLORS.get(status, QColor(180, 180, 180))


class DotGridWidget(QWidget):
    """16x16 dot grid visualization of host reachability.

    Displays 256 dots arranged in a 16-row by 16-column grid. Each dot
    represents a host octet (0–255) and is colored according to its
    current DotStatus. The widget uses a fixed size calculated from the
    grid dimensions, dot diameter, and spacing.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize grid with all dots in NOT_SCANNED state (grey)."""
        super().__init__(parent)
        # Store status for each of the 256 octets
        self._dot_statuses: list[DotStatus] = [
            DotStatus.NOT_SCANNED for _ in range(GRID_SIZE * GRID_SIZE)
        ]
        # Calculate and set fixed widget size based on grid layout
        # Total width/height = 16 cells + one spacing as padding on the right/bottom
        total_size = GRID_SIZE * CELL_SIZE + DOT_SPACING
        self.setFixedSize(total_size, total_size)

    def update_dot(self, octet: int, status: DotStatus) -> None:
        """Update the color of a single dot by octet number.

        Args:
            octet: Host octet (0–255), mapped to grid position
                   (row = octet // 16, col = octet % 16).
            status: The new DotStatus determining color.

        Raises:
            ValueError: If octet is outside 0–255.
        """
        if not 0 <= octet <= 255:
            raise ValueError(f"Octet must be 0–255, got {octet}")
        self._dot_statuses[octet] = status
        self.update()  # Schedule a repaint

    def reset(self) -> None:
        """Reset all dots to NOT_SCANNED (grey)."""
        self._dot_statuses = [
            DotStatus.NOT_SCANNED for _ in range(GRID_SIZE * GRID_SIZE)
        ]
        self.update()  # Schedule a repaint

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the 16x16 grid of colored dots.

        Each dot is drawn as a filled circle at its grid position.
        Position is computed as:
            x = col * CELL_SIZE + DOT_SPACING
            y = row * CELL_SIZE + DOT_SPACING
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for octet in range(GRID_SIZE * GRID_SIZE):
            row = octet // GRID_SIZE
            col = octet % GRID_SIZE

            # Compute top-left position of this dot
            x = col * CELL_SIZE + DOT_SPACING
            y = row * CELL_SIZE + DOT_SPACING

            # Get color for current status
            color = status_to_color(self._dot_statuses[octet])

            # Draw filled circle with no border
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(x, y, DOT_DIAMETER, DOT_DIAMETER)

        painter.end()
