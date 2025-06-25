# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

# necessary imports
from ui.main_window import MainWindow, ConsoleStream  

import sys
import os

from PyQt5.QtWidgets import QApplication

# Add the project directory to sys.path to avoid import issues
# This is necessary for the application to find the project's modules
# in the project's directory.
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":

    app = QApplication(sys.argv)

    console_stream = ConsoleStream()
    sys.stdout = console_stream
    sys.stderr = console_stream

    window = MainWindow(console_stream)
    window.show()
    sys.exit(app.exec_())