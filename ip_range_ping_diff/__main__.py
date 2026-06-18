"""Entry point for the ip-range-ping-diff tool.

Usage:
    python -m ip_range_ping_diff          # Launch GUI mode
    python -m ip_range_ping_diff --cli    # Run in CLI mode with JSON output
"""

import sys


def main() -> None:
    """Main entry point dispatching to CLI or GUI mode."""
    if "--cli" in sys.argv:
        from ip_range_ping_diff.cli import parse_cli_args, run_cli

        config = parse_cli_args(sys.argv[1:])
        run_cli(config)
    else:
        from ip_range_ping_diff.gui.main_window import MainWindow

        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
