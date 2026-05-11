# run_gui.py

import sys
from PySide6.QtWidgets import QApplication
from bidking_gui import BidKingOverlay


def main():
    app = QApplication(sys.argv)

    w = BidKingOverlay()
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
