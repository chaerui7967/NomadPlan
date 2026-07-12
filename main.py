import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.styles import APP_STYLE


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("TravelPlanner")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
