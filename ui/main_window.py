# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal

from app.context.app_context import AppContext
from ui.widgets.sidebar_button import SidebarButton
from ui.pages.overview_page import OverviewPage
from ui.pages.hardware_page import HardwarePage
from ui.pages.storage_page import StoragePage
from ui.styles.themes import get_dark_stylesheet, get_light_stylesheet

import os
from typing import Optional 

class ConsoleStream(QObject):
    new_text = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            self.new_text.emit(line)

    def flush(self):
        if self._buffer:
            self.new_text.emit(self._buffer)
            self._buffer = ""

class MainWindow(QWidget):
    def __init__(self, console_stream):
        super().__init__()
        self.console_stream = console_stream
        self.setWindowTitle("Frontend QEMU 3DFX")
        self.resize(900, 600)

        # AppContext is the heart of data logic, it is used to store
        # data and to control the state of the application.
        self.app_context = AppContext()
        self.qemu_config = self.app_context.qemu_config

        # default configuration file
        self.config_file = "qemu_config.json"
        self.qemu_process = None # for control QEMU Process
        self._vm_state = {"theme": "dark"} # UI status, not QEMU VM status

        self.recursion_prevent = False

        # AppContext pages instance
        self.overview_page = OverviewPage(self.app_context)
        self.app_context.register_page("overview", self.overview_page)
        self.hardware_page = HardwarePage(self.app_context)
        self.app_context.register_page("hardware", self.hardware_page)
        self.storage_page = StoragePage(self.app_context)
        self.app_context.register_page("storage", self.storage_page)               

        self.overview_page.resolve_dependencies()

        # Hook into the AppContext configuration update signal
        # This ensures that MainWindow reacts to ANY change in QemuConfig.
        self.app_context.qemu_config_updated.connect(self.update_window_title)
        self.app_context.qemu_config_modified.connect(self.update_window_title)

        # Setup interface
        self.setup_ui()
        self.apply_theme()
        
        # Load the initial VM configuration if the file exists.
        # This will trigger qemu_config_updated, which in turn will update the pages.
        self.load_vm_config_from_file(self.config_file) 
        
        # Optional: If no config is loaded, force an initial title refresh
        # to reflect the default state.
        self.update_window_title()      

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
            ("Network", "fa5s.network-wired", None), # Placeholders Pages
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
            # Connect the button to change the page in the QStackedWidget
            btn.clicked.connect(lambda checked=False, i=idx: self.pages.setCurrentIndex(i))
            self.sidebar_layout.addWidget(btn)
            self.buttons.append(btn)

            # Add page to QStackedWidget
            if page is not None:
                self.pages.addWidget(page)
            else:
                placeholder = QLabel(f"Página: {text} (Em Desenvolvimento)")
                placeholder.setAlignment(Qt.AlignCenter) # type: ignore
                self.pages.addWidget(placeholder)

        self.sidebar_layout.addStretch()

        # Action Buttons in Sidebar
        self.sidebar_layout.addWidget(self._make_button("Salvar Config", "fa5s.save", self.save_vm_config_to_file_dialog, "#50fa7b"))
        self.sidebar_layout.addWidget(self._make_button("Carregar Config", "fa5s.folder-open", self.load_vm_config_from_file_dialog, "#ffb86c"))
        self.sidebar_layout.addWidget(self._make_button("Alternar Tema", "fa5s.adjust", self.toggle_theme, "#8be9fd"))

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)

        # Select the first page and the first button as default
        if self.buttons:
            self.buttons[0].setChecked(True)
            self.pages.setCurrentIndex(0)

        # Connect signal changed to update the selected page
        self.pages.currentChanged.connect(self.on_page_changed)

        self.console_stream.new_text.connect(self.overview_page.console_output.appendPlainText)

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

    def closeEvent(self, event):
        # Check if app is modified before closing
        if self.app_context.is_modified():
            msg = QMessageBox(self)
            msg.setWindowTitle("Save configuration")
            msg.setText("You have unsaved changes. Do you want to save before exiting?")
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            ret = msg.exec_()
            if ret == QMessageBox.Save:
                # Call the default configuration file
                self.save_vm_config_to_file(self.config_file) 
                event.accept()
            elif ret == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def on_page_changed(self, index):
        # Refresh the "checked" state of the buttons when the page is changed
        self.buttons[index].setChecked(True)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        
        # Notify the current page
        page = self.pages.currentWidget()
        if page and hasattr(page, "on_page_changed"):
            page.on_page_changed()

    def apply_theme(self):
        theme = self._vm_state.get('theme', 'dark')
        if theme == 'dark':
            self.set_dark_theme()
        else:
            self.set_light_theme()

    # Themes methods
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

    def save_vm_config_to_file_dialog(self):
        """Open a dialog file to save configuration to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save configuration of Frontend", self.config_file, "QEMU Config Files (*.json);;All Files (*)"
        )
        if file_path:
            self.config_file = file_path # Atualiza o arquivo padrão se o usuário salvou em outro lugar
            self.save_vm_config_to_file(file_path)

    def save_vm_config_to_file(self, file_path: str):
        """Save the Frontend configuration to a file."""
        try:
            # Delega o salvamento para o AppContext
            self.app_context.save_qemu_config(file_path)
            QMessageBox.information(self, "Configuration Saved", f"Configuration saved to: {file_path}")
            print(f"[INFO] Configuration saved sucessfully to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "A error ocurred saving configuration", f"Error saving configuration: {e}")
            print(f"[WARN] Error ocurred saving configuration: {e}")
       
    def load_vm_config_from_file_dialog(self):
        """Open a dialog file to load configuration from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load configuration of Frontend", self.config_file, "QEMU Config Files (*.json);;All Files (*)"
        )
        if file_path:
            self.config_file = file_path # Atualiza o arquivo padrão
            self.load_vm_config_from_file(file_path)

    def load_vm_config_from_file(self, file_path: Optional[str] = None):
        """
        Load the Frontend configuration from a file.
        If file_path is None, it tries to load the default configuration.
        """
        if file_path is None:
            file_path = self.config_file # Tenta carregar do arquivo padrão
            
        if not os.path.exists(file_path):
            print(f"[WARN]Don't have a configuration file to load {file_path}. Starting with the default configuration.")
            return
        try:
            # Delegate the loading to the AppContext
            self.app_context.load_qemu_config(file_path)
            
            #QMessageBox.information(self, "Configuração Carregada", f"Configuração da VM carregada de: {file_path}")
            print(f"[INFO]Configuration loaded sucessfully from: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error loading configuration", f"Error loading configuration: {e}")
            print(f"[ERROR] Error ocurred loading configuration: {e}")

        # update_window_title is called by AppContext to refresh window title

    def update_window_title(self, modified=None):
        # Prevent signal recursion
        if not self.recursion_prevent:
            self.recursion_prevent = True
            base_title = "Frontend QEMU 3DFX"
            current_qemu_config = self.app_context.get_qemu_config_object()
            # Use's the parameters to generate the title
            if modified is None:
                modified = self.app_context.is_modified()
            modified_indicator = "\u25CF " if modified else ""
            vm_name = current_qemu_config.all_args.get("name", "Nova VM")
            title = f"{modified_indicator} {base_title} - {vm_name}"
            self.setWindowTitle(title)
            self.recursion_prevent = False