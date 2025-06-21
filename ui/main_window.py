from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QMessageBox
)
from PyQt5.QtCore import Qt
from app.context.app_context import AppContext
from ui.widgets.sidebar_button import SidebarButton
from ui.pages.overview_page import OverviewPage
from ui.pages.hardware_page import HardwarePage
from ui.pages.storage_page import StoragePage
from ui.styles.themes import get_dark_stylesheet, get_light_stylesheet
import json
import os

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frontend QEMU 3DFX")
        self.resize(900, 600)

        self.app_context = AppContext()
        self.hardware_page = HardwarePage(self.app_context)
        self.config_file = "config.json"
        self.qemu_process = None
        self._vm_state = {"theme": "dark"}
        self.recursion_prevent = False

        # Instanciação explícita das páginas
        self.overview_page = OverviewPage(self.app_context)
        self.app_context.register_page("overview", self.overview_page)
        self.hardware_page = HardwarePage(self.app_context)
        self.app_context.register_page("hardware", self.hardware_page)
        self.storage_page = StoragePage(self.app_context)
        self.app_context.register_page("storage", self.storage_page)

        # Conecta sinais globais
        self.app_context.config_changed.connect(self._config_changed)
        self.app_context.config_loaded.connect(self._config_loaded)
        self.app_context.config_saved.connect(self._config_saved)
        self.app_context.qemu_args_pasted.connect(self.overview_page.qemu_direct_parse)

        # Setup da interface
        self.setup_ui()
        self.apply_theme()
        self.load_vm_config_from_file()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)

        self.buttons = []
        self.pages = QStackedWidget()

        self.items = [
            ("Overview", "fa5s.home", self.overview_page),
            ("Hardware", "fa5s.microchip", self.hardware_page),
            ("Storage", "fa5s.hdd", self.storage_page),
            ("Network", "fa5s.network-wired", None),
            ("Display", "fa5s.desktop", None),
            ("Sound", "fa5s.volume-up", None),
            ("Advanced", "fa5s.cogs", None),
            ("Logs", "fa5s.terminal", None)
        ]

        for idx, (text, icon, page) in enumerate(self.items):
            btn = SidebarButton(
                text,
                icon,
                text_color="#f8f8f2",
                icon_color="#8be9fd",
                selected_bg="rgba(80, 92, 144, 0.3)",
                hover_bg="#505c90"
            )
            btn.clicked.connect(lambda checked=False, i=idx: self.pages.setCurrentIndex(i))
            self.sidebar_layout.addWidget(btn)
            self.buttons.append(btn)

            if page is not None:
                self.pages.addWidget(page)
            else:
                placeholder = QLabel(f"Page: {text}")
                placeholder.setAlignment(Qt.AlignCenter)
                self.pages.addWidget(placeholder)

        self.sidebar_layout.addStretch()

        self.sidebar_layout.addWidget(self._make_button("Salvar Config", "fa5s.save", self.save_vm_config_to_file, "#50fa7b"))
        self.sidebar_layout.addWidget(self._make_button("Carregar Config", "fa5s.folder-open", self.load_vm_config_from_file, "#ffb86c"))
        self.sidebar_layout.addWidget(self._make_button("Alternar Tema", "fa5s.adjust", self.toggle_theme, "#8be9fd"))

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)

        if self.buttons:
            self.buttons[0].setChecked(True)
            self.pages.setCurrentIndex(0)

        self.pages.currentChanged.connect(self.on_page_changed)

    def _make_button(self, text, icon, callback, icon_color):
        btn = SidebarButton(
            text, icon,
            text_color="#f8f8f2",
            icon_color=icon_color,
            selected_bg="rgba(80, 92, 144, 0.3)",
            hover_bg="#505c90"
        )
        btn.clicked.connect(callback)
        return btn

    def _config_changed(self):
        self.update_window_title()

    def _config_saved(self):
        self.update_window_title()

    def _config_loaded(self):
        self.update_window_title()

    def closeEvent(self, event):
        if self.app_context.is_modified():
            msg = QMessageBox(self)
            msg.setWindowTitle("Salvar Configuração?")
            msg.setText("Você tem alterações não salvas. Deseja salvar antes de sair?")
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            ret = msg.exec_()
            if ret == QMessageBox.Save:
                self.save_vm_config_to_file()
                event.accept()
            elif ret == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def on_page_changed(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        page = self.pages.currentWidget()
        if page and hasattr(page, "on_page_changed"):
            page.on_page_changed()

    def apply_theme(self):
        theme = self._vm_state.get('theme', 'dark')
        if theme == 'dark':
            self.set_dark_theme()
        else:
            self.set_light_theme()

    def set_dark_theme(self):
        self.setStyleSheet(get_dark_stylesheet())
        self.sidebar.setStyleSheet("background-color: #282a36;")
        for btn in self.buttons:
            btn.text_color = "#f8f8f2"
            btn.icon_color = "#8be9fd"
            btn.selected_bg = "rgba(80, 92, 144, 0.3)"
            btn.hover_bg = "#505c90"
            btn.update_icon_color(btn.icon_color)
            btn.setStyleSheet(btn.build_style())

    def set_light_theme(self):
        self.setStyleSheet(get_light_stylesheet())
        self.sidebar.setStyleSheet("background-color: #ffffff;")
        for btn in self.buttons:
            btn.text_color = "#1a1a1a"
            btn.icon_color = "#003366"
            btn.selected_bg = "rgba(0, 51, 102, 0.15)"
            btn.hover_bg = "#003366"
            btn.update_icon_color(btn.icon_color)
            btn.setStyleSheet(btn.build_style())

    def toggle_theme(self):
        current = self._vm_state.get('theme', 'dark')
        self._vm_state['theme'] = 'light' if current == 'dark' else 'dark'
        self.apply_theme()

    def save_vm_config_to_file(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.app_context.config, f, indent=4)
            self.app_context.mark_saved()
            print("Configuração salva com sucesso!")
            self.update_window_title()
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")

    def load_vm_config_from_file(self):
        if not os.path.exists(self.config_file):
            self.app_context.start_loading()
            self.app_context.finish_loading()
            return

        try:
            self.app_context.start_loading()
            with open(self.config_file, "r") as f:
                config = json.load(f)

            self.app_context.set_config(config)

            self.overview_page.load_config_to_ui()

            print("Configuração carregada com sucesso!")

        except Exception as e:
            print(f"Erro ao carregar configuração: {e}")

        finally:
            self.app_context.finish_loading()
            self.app_context.config_loaded.emit()

    def update_window_title(self):
        if not self.recursion_prevent:
            self.recursion_prevent = True
            base_title = "Frontend QEMU 3DFX"
            title = "\u25CF " + base_title if self.app_context.is_modified() else base_title
            if self.app_context.config and "name" in self.app_context.config:
                title += f" - {self.app_context.config['name']}"
            self.setWindowTitle(title)
            self.recursion_prevent = False
