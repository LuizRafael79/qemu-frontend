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
        self.overview_page = OverviewPage(self.app_context)

        self.app_context.config_changed.connect(self._config_changed)
        self.app_context.config_loaded.connect(self._config_loaded)
        self.app_context.config_saved.connect(self._config_saved)
        self.qemu_helper = None

        self.config_file = "config.json"
        self._vm_state = {'theme': 'dark'}
        self.qemu_process = None
        self.recursion_prevent = False

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
            ("Overview", "fa5s.home"),
            ("Hardware", "fa5s.microchip"),
            ("Storage", "fa5s.hdd"),
            ("Network", "fa5s.network-wired"),
            ("Display", "fa5s.desktop"),
            ("Sound", "fa5s.volume-up"),
            ("Advanced", "fa5s.cogs"),
            ("Logs", "fa5s.terminal")
        ]

        for idx, (text, icon) in enumerate(self.items):
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

            if text == "Overview":
                page = OverviewPage(self.app_context)
                self.overview_page = page
                self.overview_page.overview_config_changed.connect(self.app_context.config_changed)
            elif text == "Hardware":
                page = HardwarePage(self.app_context)
                self.hardware_page = page
                self.hardware_page.hardware_config_changed.connect(self.app_context.config_changed)
                self.hardware_page.hardware_config_changed.connect(self.qemu_reverse_parse)
            elif text == "Storage":
                page = StoragePage(self.app_context)
                self.storage_page = page
                self.storage_page.storage_config_changed.connect(self.app_context.config_changed)
                self.storage_page.storage_config_changed.connect(self.qemu_reverse_parse)
            else:
                placeholder = QLabel(f"Page: {text}")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                page = placeholder

            self.pages.addWidget(page)

        self.app_context.qemu_args_pasted.connect(self.qemu_direct_parse)

        self.sidebar_layout.addStretch()

        self.save_config_button = SidebarButton(
            "Salvar Config",
            "fa5s.save",
            text_color="#f8f8f2",
            icon_color="#50fa7b",
            selected_bg="rgba(80, 92, 144, 0.3)",
            hover_bg="#505c90"
        )
        self.save_config_button.clicked.connect(self.save_vm_config_to_file)
        self.sidebar_layout.addWidget(self.save_config_button)

        self.load_config_button = SidebarButton(
            "Carregar Config",
            "fa5s.folder-open",
            text_color="#f8f8f2",
            icon_color="#ffb86c",
            selected_bg="rgba(80, 92, 144, 0.3)",
            hover_bg="#505c90"
        )
        self.load_config_button.clicked.connect(self.load_vm_config_from_file)
        self.sidebar_layout.addWidget(self.load_config_button)

        self.theme_button = SidebarButton(
            "Alternar Tema",
            "fa5s.adjust",
            text_color="#f8f8f2",
            icon_color="#8be9fd",
            selected_bg="rgba(80, 92, 144, 0.3)",
            hover_bg="#505c90"
        )
        self.theme_button.clicked.connect(self.toggle_theme)
        self.sidebar_layout.addWidget(self.theme_button)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)

        if self.buttons:
            self.buttons[0].setChecked(True)
            self.pages.setCurrentIndex(0)

        self.pages.currentChanged.connect(self.on_page_changed)

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
        for btn in self.buttons + [self.theme_button]:
            btn.text_color = "#f8f8f2"
            btn.icon_color = "#8be9fd"
            btn.selected_bg = "rgba(80, 92, 144, 0.3)"
            btn.hover_bg = "#505c90"
            btn.update_icon_color(btn.icon_color)
            btn.setStyleSheet(btn.build_style())

    def set_light_theme(self):
        self.setStyleSheet(get_light_stylesheet())
        self.sidebar.setStyleSheet("background-color: #ffffff;")
        for btn in self.buttons + [self.theme_button]:
            btn.text_color = "#1a1a1a"
            btn.icon_color = "#003366"
            btn.selected_bg = "rgba(0, 51, 102, 0.15)"
            btn.hover_bg = "#003366"
            btn.update_icon_color(btn.icon_color)
            btn.setStyleSheet(btn.build_style())

    def toggle_theme(self):
        current_theme = self._vm_state.get('theme', 'dark')
        new_theme = 'light' if current_theme == 'dark' else 'dark'
        self._vm_state['theme'] = new_theme
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
            self.update_window_title()
            return

        try:
            self.app_context.start_loading()
            with open(self.config_file, "r") as f:
                config = json.load(f)

            self.app_context.set_config(config)
            self.overview_page.load_config_to_ui()
            self.hardware_page.load_cpu_list()
            self.hardware_page.load_config_to_ui()
            self.storage_page.load_config_to_ui()

            qemu_args_str = self.app_context.config.get("qemu_args", "")
            tokens = self.app_context.split_shell_command(qemu_args_str)
            self.app_context.qemu_args_pasted.emit(tokens)
            print("Configuração carregada com sucesso!")

        except Exception as e:
            print(f"Erro ao carregar configuração: {e}")
        finally:
            self.app_context.finish_loading()
            self.update_window_title()

    def update_window_title(self):
        if not self.recursion_prevent:
            self.recursion_prevent = True
            base_title = "Frontend QEMU 3DFX"
            title = "\u25CF " + base_title if self.app_context.is_modified() else base_title
            if self.app_context.config and "name" in self.app_context.config:
                title += f" - {self.app_context.config['name']}"
            else:
                self.setWindowTitle(title)
                self.recursion_prevent = False

    def qemu_direct_parse(self, cmdline: list[str]):
        remaining = self.hardware_page.qemu_direct_parse(cmdline)
        if remaining:
            remaining = self.storage_page.qemu_direct_parse(remaining)
        self.overview_page.update_qemu_args(remaining)

    def qemu_reverse_parse(self):
        args = []
        #args += self.hardware_page.qemu_reverse_parse_args()
        args += self.storage_page.qemu_reverse_parse_args()
        args += self.hardware_page.qemu_reverse_parse_args()   
        self.overview_page.update_qemu_args(args)