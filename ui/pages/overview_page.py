# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from __future__ import annotations

from app.utils.debug_log import debug_log

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QHBoxLayout, QTextEdit, 
    QTabWidget, QFileDialog, QPlainTextEdit, QMessageBox
)
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor

from PyQt5.QtCore import pyqtSignal, QTimer
import os
import shutil
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.context.app_context import AppContext
class OverviewPage(QWidget):
    overview_config_changed = pyqtSignal()
    qemu_binary_changed = pyqtSignal(str)

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.qemu_config = self.app_context.qemu_config
        self.qemu_argument_parser = self.app_context.qemu_argument_parser
        self.hardware_page = self.app_context._get_page("hardware")
        self.storage_page = self.app_context._get_page("storage")

        self.tab_widget = QTabWidget()

        self._internal_text_change = False
        self.app_context.qemu_config_updated.connect(self.refresh_display_from_qemu_config)
        self._parse_timer = QTimer(self) 
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(500)
        self.setup_ui()
        self.populate_qemu_binaries()
        self.load_config_to_ui()
        self.bind_signals()
        self.refresh_display_from_qemu_config()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.title_label = QLabel("Virtual Machine Overview")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(self.title_label)

        # QEMU Binary group
        qemu_group = QGroupBox("QEMU Executable")
        qemu_layout = QFormLayout()
        self.qemu_combo = QComboBox()
        qemu_layout.addRow("Available QEMU:", self.qemu_combo)
        qemu_group.setLayout(qemu_layout)
        main_layout.addWidget(qemu_group)

        # Custom binary group
        custom_group = QGroupBox("Custom Executable")
        custom_layout = QHBoxLayout()
        self.custom_path = QLineEdit()
        self.btn_browse = QPushButton("Browse")
        self.btn_clear = QPushButton("Clear")
        custom_layout.addWidget(self.custom_path)
        custom_layout.addWidget(self.btn_browse)
        custom_layout.addWidget(self.btn_clear)
        custom_group.setLayout(custom_layout)
        main_layout.addWidget(custom_group)

        # Architecture info
        self.arch_label = QLabel("Architecture:")
        main_layout.addWidget(self.arch_label)

        # Launch
        self.btn_launch = QPushButton("Launch QEMU")
        main_layout.addWidget(self.btn_launch)

        # Output tabs
        self.output_tabs = QTabWidget()
        self.qemuargs_output = QTextEdit()
        self.qemuargs_output.setReadOnly(False)
        self.qemuextraargs_output = QTextEdit()
        self.qemuextraargs_output.setReadOnly(True)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.mesa_output = QTextEdit()
        self.mesa_output.setReadOnly(True)
        
        self.output_tabs.addTab(self.qemuargs_output, "Qemu Args")
        self.output_tabs.addTab(self.qemuextraargs_output, "Extra Args")
        self.output_tabs.addTab(self.console_output, "Console Output")
        self.output_tabs.addTab(self.mesa_output, "mesaPT / glidePT Logs")
        main_layout.addWidget(self.output_tabs)

        self.fps_label = QLabel("FPS: --")
        main_layout.addWidget(self.fps_label)

    def bind_signals(self):
        self.qemu_combo.currentIndexChanged.connect(self.on_qemu_combo_changed)
        self.btn_browse.clicked.connect(self.on_browse_clicked)
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        self.custom_path.textChanged.connect(self.on_custom_path_changed)
        self.btn_launch.clicked.connect(self.on_launch_clicked)
        self.qemuargs_output.textChanged.connect(self._on_qemuargs_output_text_changed)
        # 1. Connect the signal of the timer (500ms) to the slot that will parse the qemu command
        self._parse_timer.timeout.connect(self._do_parse_qemu_command)

        # 2. Connect the change of the text of the QemuArgsOutput to the slot that will parse the qemu command
        self.qemuargs_output.textChanged.connect(self._on_qemuargs_output_text_changed)

        # 3. Connect the signal change of QemuConfig (Via AppContext)
        #    That guarantees that the OverviewPage will be refreshed
        self.app_context.qemu_config_updated.connect(self.refresh_display_from_qemu_config)

    def populate_qemu_binaries(self):

        debug_log("Iniciando populate_qemu_binaries")
        self.qemu_config._cache.clear()
        debug_log("Cache interno limpo")

        found = 0
        for path in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.startswith("qemu-system-"):
                        full_path = shutil.which(f)
                        if full_path:
                            debug_log(f"Encontrado candidato: {full_path}")
                            try:
                                self.qemu_config._get_helper(full_path, self.app_context)
                                found += 1
                            except Exception as e:
                                debug_log(f"Erro ao processar {full_path}: {e}")

        debug_log(f"{found} binários QEMU adicionados ao cache")
        
        all_binaries = list(self.qemu_config._cache.keys())
        self.qemu_combo.blockSignals(True)
        self.qemu_combo.clear()
        self.qemu_combo.addItems([os.path.basename(p) for p in all_binaries])
        self.qemu_combo.blockSignals(False)

        debug_log(f"{len(all_binaries)} itens adicionados ao combo")

    def load_config_to_ui(self):        
        cfg = self.app_context.qemu_config
        if not cfg:
            return

        self._internal_text_change = True
        self.qemu_combo.blockSignals(True)
        self.custom_path.blockSignals(True)

        try:
            custom_exec = cfg.get("custom_executable", "").strip()
            self.custom_path.setText(custom_exec)

            if custom_exec:
                self.qemu_combo.setEnabled(False)
                self._update_active_binary(custom_exec)
            else:
                self.qemu_combo.setEnabled(True)
                
                # --- INÍCIO DO BLOCO DE INSPEÇÃO ---
                debug_log("\n==========================================================")
                debug_log("--- INICIANDO INSPEÇÃO MICROSCÓPICA ---")
                
                # 1. Inspeciona o valor vindo do JSON
                json_full_path = cfg.get("qemu_executable", "").strip()
                json_basename = os.path.basename(json_full_path)
                debug_log(f"JSON_VAL: '{json_basename}' | TIPO: {type(json_basename)} | LEN: {len(json_basename)}")

                # 2. Inspeciona cada item do ComboBox e compara
                combo_items = [self.qemu_combo.itemText(i) for i in range(self.qemu_combo.count())]
                found_index = -1

                debug_log("--- COMPARANDO ITEM A ITEM ---")
                for i, item_from_combo in enumerate(combo_items):
                    # Normaliza ambos os lados
                    json_val_norm = json_basename.lower().strip()
                    combo_val_norm = item_from_combo.lower().strip()
                    
                    match = "SIM" if json_val_norm == combo_val_norm else "NAO"
                    
                    debug_log(f"  Índice {i}: Comparando JSON '{json_val_norm}' (LEN:{len(json_val_norm)}) com COMBO '{combo_val_norm}' (LEN:{len(combo_val_norm)}) -> BATE? {match}")
                    
                    if match == "SIM":
                        found_index = i
                
                debug_log(f"--- FIM DA INSPEÇÃO. Índice encontrado: {found_index} ---")
                debug_log("==========================================================\n")
                # --- FIM DO BLOCO DE INSPEÇÃO ---


                # A lógica original continua, usando o índice encontrado
                if found_index != -1:
                    self.qemu_combo.setCurrentIndex(found_index)
                elif self.qemu_combo.count() > 0:
                    self.qemu_combo.setCurrentIndex(0)
                
                # O get a seguir pode falhar se o índice for -1 após uma falha de busca, mas o setCurrentIndex(0) deve prevenir isso
                current_idx = self.qemu_combo.currentIndex()
                if current_idx != -1:
                    self.on_qemu_combo_changed(current_idx)

            self.refresh_display_from_qemu_config()

        finally:
            self._internal_text_change = False
            self.qemu_combo.blockSignals(False)
            self.custom_path.blockSignals(False)

    def _update_active_binary(self, binary_path: Optional[str]):
            from PyQt5.QtWidgets import QMessageBox

            # Bloqueia sinais para evitar loops, como você já faz
            with self.app_context.signal_blocker():
                custom_path_text = self.custom_path.text().strip()
                
                # Prepara o dicionário de dados a serem salvos
                data_to_update = {
                    "qemu_executable": binary_path or "",
                    "custom_executable": custom_path_text
                }

                if not binary_path or not os.path.exists(binary_path):
                    self.arch_label.setText("Architecture: No QEMU binary selected")
                    # Salva um valor padrão ou vazio para a arquitetura
                    data_to_update["architecture"] = ""
                else:
                    try:
                        helper = self.app_context.get_helper(binary_path)
                        if not helper:
                            raise FileNotFoundError(f"QEMU helper não pôde ser instanciado para: {binary_path}")

                        # Pega o dado bruto (ex: "hppa")
                        arch_text = helper.get_info("architecture") or "Unknown"
                        
                        # Atualiza a UI (Visão)
                        self.arch_label.setText(f"Architecture: {arch_text}")
                        
                        # --- A CORREÇÃO ---
                        # Salva apenas o dado bruto (Modelo)
                        data_to_update["architecture"] = arch_text

                    except Exception as e:
                        # Trata os erros como antes
                        # ...
                        return

                # Atualiza o QemuConfig com os dados puros e notifica o restante da app
                self.qemu_config.update_qemu_config_from_page(data_to_update)
                self.qemu_binary_changed.emit(binary_path or "")
                self.overview_config_changed.emit()

                if hasattr(self, "hardware_page") and self.hardware_page:
                    self.hardware_page.update_qemu_helper()

    def on_qemu_combo_changed(self, index):
        # Block signals of qemu_combo to avoid recurion or more than one signal emission
        self.qemu_combo.blockSignals(True) 
        
        selected_basename = self.qemu_combo.itemText(index)
        full_binary_path = None
        
        # Find the full path of Qemu Binary in cache (~/.cache/qemu_binaries/)
        for path_key in self.qemu_config._cache.keys():
            if os.path.basename(path_key) == selected_basename:
                full_binary_path = path_key
                break

        if full_binary_path:
            # call _update_active_binary with the full path
            self._update_active_binary(full_binary_path)
        else:
            # reload state of qemu_executable as none to clean the state
            self.qemu_config.update_qemu_config_from_page({"qemu_executable": ""})
            self._update_active_binary(None) # Pass none to clean the state
        self.app_context.mark_modified()

        self.qemu_combo.blockSignals(False) # Unlock the signals

    def on_custom_path_changed(self, text):
        from PyQt5.QtWidgets import QMessageBox

        text = text.strip()
        if text:
            self.qemu_combo.setEnabled(False)
            try:
                self._update_active_binary(text)
            except FileNotFoundError as e:
                QMessageBox.critical(self, "Erro", str(e))
                self.arch_label.setText("Architecture: Invalid QEMU binary")
                self.qemu_combo.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self, "Unexpected error", f"Unknown error processing binary: {e}")
                self.arch_label.setText("Architecture: Unexpected error")
                self.qemu_combo.setEnabled(True)
        else:
            self.qemu_combo.setEnabled(True)
            self.on_qemu_combo_changed(self.qemu_combo.currentIndex())

    def on_browse_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select QEMU Executable")
        if path:
            self.custom_path.setText(path)

    def on_clear_clicked(self):
        self.custom_path.clear()

    def on_launch_clicked(self):
        # Imports necessários no início do arquivo
        import shlex
        import subprocess
        import traceback

        try:
            # 1. Gera a lista de comando completa a partir da sua lógica
            qemu_config_object = self.app_context.get_qemu_config_object()
            full_qemu_cmd_tuple = qemu_config_object.to_qemu_args_string()
            final_command_list = self.app_context.split_shell_command(full_qemu_cmd_tuple[0])

            if not final_command_list:
                self.console_output.appendPlainText("ERRO: Falha ao gerar a lista de comando final.")
                return

            # Log para a UI usando o método correto
            self.console_output.appendPlainText(f"Iniciando: {' '.join(shlex.quote(arg) for arg in final_command_list)}")

            # 2. Executa o QEMU em um novo processo, permitindo que a janela apareça
            subprocess.Popen(final_command_list)
            
            self.console_output.appendPlainText("QEMU foi iniciado em uma nova janela (se não houve erros).")

        except Exception as e:
            # Se qualquer erro ocorrer durante a GERAÇÃO do comando, ele será pego aqui
            self.console_output.appendPlainText("--- ERRO INESPERADO AO PREPARAR O COMANDO ---")
            self.console_output.appendPlainText(traceback.format_exc())

    def refresh_display_from_qemu_config(self):
        """
        UPDATES THE VISUAL INTERFACE of the OverviewPage.
        Receives the current state of QemuConfig (generated by the GUI or via direct parsing)
        and displays the full command line and extra arguments.
        This is the "RENDER" method of the OverviewPage.
        """
        # Active blocking to avoid infinite recursion
        self._internal_text_change = True 

        try:
            # Call the process to generate "Reverse Parse" (GUI -> CLI)
            qemu_config = self.app_context.get_qemu_config_object()
            full_cmd_str, extra_args_str = qemu_config.to_qemu_args_string()
            # Refresh the "Qemu Args" Window Tab
            self.qemuargs_output.blockSignals(True)
            self.qemuargs_output.setPlainText(full_cmd_str)
            self.qemuargs_output.blockSignals(False)
            
            # Refresh the "Extra Args" Window Tab
            self.qemuargs_output.blockSignals(True)
            self.qemuextraargs_output.setPlainText(extra_args_str)
            self.qemuargs_output.blockSignals(False)

        except Exception as e:
            self.qemuargs_output.setPlainText("[ERROR] Fail to generate QemuArgs.")
            self.qemuextraargs_output.setPlainText("[ERROR] Fail to generate QemuExtraArgs.")
        finally:
            # Deactivate the protection against recursion
            self._internal_text_change = False

    def _on_qemuargs_output_text_changed(self):
        """
        Called when the text in `qemuargs_output` has CHANGED (by user or paste).
        Starts or resets the timer to parse the command after a short delay.
        """
        if self._internal_text_change: 
            return

        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        if raw_cmd_line:            
            self._parse_timer.start()
            self.app_context.parse_cli_and_notify(raw_cmd_line) 
        else:            
            self._parse_timer.stop() 
            self.app_context.get_qemu_config_object().reset()
            # Emit a signal to RESET all GUI's to default or last saved state.
            self.app_context.qemu_config_updated.emit(self.app_context.get_qemu_config_object())

    def _do_parse_qemu_command(self):
        """
        Este método é chamado pelo QTimer após o delay.
        Ele aciona o parse da linha de comando e NOTIFICA as outras páginas.
        """
        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        if raw_cmd_line:
            try:
                print(f"[INFO] OverviewPage: Timer Started. Starting reverse parse from inputed args: '{raw_cmd_line}'")
                self.qemu_argument_parser.parse_qemu_command_line_to_config(raw_cmd_line)
                self.app_context.parse_cli_and_notify(raw_cmd_line)
                self.app_context.mark_modified()
            except Exception as e:
                print(f"[ERROR] Exception during parse_qemu_command_line_to_config: {e}")
                import traceback
                traceback.print_exc()
        else:
            self.app_context.get_qemu_config_object().reset()
            self.app_context.qemu_config_updated.emit(self.app_context.get_qemu_config_object())

    def resolve_dependencies(self):
        self.hardware_page = self.app_context._get_page("hardware")
        self.storage_page = self.app_context._get_page("storage")

    def append_colored_text(self, text, color):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self.console_output.textCursor() 
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + '\n', fmt)
        self.console_output.setTextCursor(cursor) 
        self.console_output.ensureCursorVisible()

        # The use of type: ignore is only for the purpose of the IDE plugin, like Pylance in Vscode
        # is not able to detect the types of functions arguments (false positive)






 