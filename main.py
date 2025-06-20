import sys
import os

# Adiciona o diretório raiz do projeto ao sys.path
# Isso garante que os módulos como 'app' e 'ui' possam ser importados de qualquer lugar.
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from PyQt5.QtWidgets import QApplication
# Import MainWindow inside the main block to avoid circular import issues
MainWindow = None
if __name__ == "__main__":
    from ui.main_window import MainWindow  # Import here to avoid circular import
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    sys.exit(app.exec_())
