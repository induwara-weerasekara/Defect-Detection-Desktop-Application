import sys
from PyQt5.QtWidgets import QApplication
from app_ui import MainWindow
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
