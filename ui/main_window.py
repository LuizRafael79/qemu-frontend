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
import sys
from typing import Optional # Para tipagem do file_path

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

        # AppContext é o coração da lógica de dados
        self.app_context = AppContext()
        self.qemu_config = self.app_context.qemu_config

        # O arquivo de configuração padrão
        self.config_file = "qemu_config.json" # Renomeei para evitar conflito com 'config.json' genérico
        self.qemu_process = None # Para controlar o processo QEMU quando for implementado
        self._vm_state = {"theme": "dark"} # Estado da UI, não da VM QEMU

        # Flag para prevenir recursão no título da janela
        self.recursion_prevent = False

        # Instanciação das páginas, passando o AppContext
        self.overview_page = OverviewPage(self.app_context)
        self.app_context.register_page("overview", self.overview_page)
        self.hardware_page = HardwarePage(self.app_context)
        self.app_context.register_page("hardware", self.hardware_page)
        self.storage_page = StoragePage(self.app_context)
        self.app_context.register_page("storage", self.storage_page)               

        self.overview_page.resolve_dependencies()

        # Conectar ao sinal de atualização de configuração do AppContext
        # Isso garante que a MainWindow reaja a QUALQUER mudança na QemuConfig.
        self.app_context.qemu_config_updated.connect(self.update_window_title)
        self.app_context.qemu_config_modified.connect(self.update_window_title)

        # Setup da interface
        self.setup_ui()
        self.apply_theme()
        
        # Carrega a configuração inicial da VM se o arquivo existir.
        # Isso vai disparar qemu_config_updated, que por sua vez atualizará as páginas.
        self.load_vm_config_from_file(self.config_file) 
        
        # Opcional: Se nenhuma config for carregada, forçar uma atualização inicial do título
        # para refletir o estado padrão.
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
            ("Network", "fa5s.network-wired", None), # Páginas Placeholder
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
            # Conecta o botão para mudar a página no QStackedWidget
            btn.clicked.connect(lambda checked=False, i=idx: self.pages.setCurrentIndex(i))
            self.sidebar_layout.addWidget(btn)
            self.buttons.append(btn)

            # Adiciona a página ao QStackedWidget
            if page is not None:
                self.pages.addWidget(page)
            else:
                placeholder = QLabel(f"Página: {text} (Em Desenvolvimento)")
                placeholder.setAlignment(Qt.AlignCenter) # type: ignore
                self.pages.addWidget(placeholder)

        self.sidebar_layout.addStretch()

        # Botões de ação na barra lateral
        self.sidebar_layout.addWidget(self._make_button("Salvar Config", "fa5s.save", self.save_vm_config_to_file_dialog, "#50fa7b"))
        self.sidebar_layout.addWidget(self._make_button("Carregar Config", "fa5s.folder-open", self.load_vm_config_from_file_dialog, "#ffb86c"))
        self.sidebar_layout.addWidget(self._make_button("Alternar Tema", "fa5s.adjust", self.toggle_theme, "#8be9fd"))

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)

        # Seleciona o primeiro botão e a primeira página por padrão
        if self.buttons:
            self.buttons[0].setChecked(True)
            self.pages.setCurrentIndex(0)

        # Conecta o sinal de mudança de página para atualizar o estado dos botões da sidebar
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

    # Os métodos _config_changed, _config_saved, _config_loaded foram removidos,
    # pois a lógica de atualização agora é centralizada via qemu_config_updated.

    def closeEvent(self, event):
        # Verifica se a configuração foi modificada antes de fechar
        if self.app_context.is_modified():
            msg = QMessageBox(self)
            msg.setWindowTitle("Salvar Configuração?")
            msg.setText("Você tem alterações não salvas. Deseja salvar antes de sair?")
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            ret = msg.exec_()
            if ret == QMessageBox.Save:
                self.save_vm_config_to_file(self.config_file) # Chama a função de salvar com o arquivo padrão
                event.accept()
            elif ret == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def on_page_changed(self, index):
        # Atualiza o estado "checked" dos botões da sidebar
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        
        # Notifica a página atual (se tiver o método) que ela foi ativada
        page = self.pages.currentWidget()
        if page and hasattr(page, "on_page_changed"):
            page.on_page_changed()

    def apply_theme(self):
        theme = self._vm_state.get('theme', 'dark')
        if theme == 'dark':
            self.set_dark_theme()
        else:
            self.set_light_theme()

    # Métodos para aplicar temas (mantidos como estavam)
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
        """Abre um diálogo para o usuário escolher onde salvar a configuração."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Configuração da VM", self.config_file, "QEMU Config Files (*.json);;All Files (*)"
        )
        if file_path:
            self.config_file = file_path # Atualiza o arquivo padrão se o usuário salvou em outro lugar
            self.save_vm_config_to_file(file_path)

    def save_vm_config_to_file(self, file_path: str):
        """Salva a configuração da VM no arquivo especificado."""
        try:
            # Delega o salvamento para o AppContext
            self.app_context.save_qemu_config(file_path)
            QMessageBox.information(self, "Configuração Salva", f"Configuração da VM salva em: {file_path}")
            print(f"Configuração salva com sucesso em: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Falha ao salvar configuração: {e}")
            print(f"Erro ao salvar configuração: {e}")
       
    def load_vm_config_from_file_dialog(self):
        """Abre um diálogo para o usuário escolher qual arquivo carregar."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Carregar Configuração da VM", self.config_file, "QEMU Config Files (*.json);;All Files (*)"
        )
        if file_path:
            self.config_file = file_path # Atualiza o arquivo padrão
            self.load_vm_config_from_file(file_path)

    def load_vm_config_from_file(self, file_path: Optional[str] = None):
        """
        Carrega a configuração da VM de um arquivo.
        Se nenhum caminho for fornecido, tenta carregar do arquivo padrão.
        """
        if file_path is None:
            file_path = self.config_file # Tenta carregar do arquivo padrão
            
        if not os.path.exists(file_path):
            print(f"Nenhum arquivo de configuração encontrado em: {file_path}. Iniciando com configuração padrão.")
            # Se não há arquivo, o AppContext permanece com a config padrão.
            # O sinal qemu_config_updated já será emitido na inicialização do AppContext
            # ou você pode forçar uma emissão se realmente quiser.
            return

        try:
            # Delega o carregamento para o AppContext.
            # O AppContext carregará os dados e EMITIRÁ qemu_config_updated.
            self.app_context.load_qemu_config(file_path)
            
            # As páginas (OverviewPage, HardwarePage, StoragePage) 
            # já estão conectadas a qemu_config_updated e irão se atualizar.
            
            #QMessageBox.information(self, "Configuração Carregada", f"Configuração da VM carregada de: {file_path}")
            print(f"Configuração carregada com sucesso de: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Erro ao Carregar Configuração", f"Falha ao carregar configuração: {e}")
            print(f"Erro ao carregar configuração: {e}")

        # O update_window_title será chamado via conexão ao sinal qemu_config_updated

    def update_window_title(self, modified=None):
        if not self.recursion_prevent:
            self.recursion_prevent = True
            base_title = "Frontend QEMU 3DFX"
            current_qemu_config = self.app_context.get_qemu_config_object()
            # Use o parâmetro modified vindo do sinal, se tiver, senão calcula
            if modified is None:
                modified = self.app_context.is_modified()
            modified_indicator = "\u25CF " if modified else ""
            vm_name = current_qemu_config.all_args.get("name", "Nova VM")
            title = f"{modified_indicator} {base_title} - {vm_name}"
            self.setWindowTitle(title)
            self.recursion_prevent = False