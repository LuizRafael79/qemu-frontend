import sys
import os
from PyQt5.QtWidgets import QApplication

from app.utils import qemu_helper

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    from ui.main_window import MainWindow 

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())