import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow


def ensure_directories():
    base_dir = Path(__file__).resolve().parent.parent
    (base_dir / "output").mkdir(parents=True, exist_ok=True)
    (base_dir / "app" / "config").mkdir(parents=True, exist_ok=True)


def main():
    ensure_directories()

    app = QApplication(sys.argv)
    app.setApplicationName("Local Translation GUI")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()