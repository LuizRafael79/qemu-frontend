# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QHBoxLayout, QTextEdit, 
    QTabWidget, QFileDialog, QPlainTextEdit
)
from PyQt5.QtCore import pyqtSignal, QTimer
import os
import subprocess
import shutil
import shlex
from typing import Optional

from app.context.app_context import AppContext

class OverviewPage(QWidget):
    overview_config_changed = pyqtSignal()
    qemu_binary_changed = pyqtSignal(str)

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.qemu_config = self.app_context.qemu_config
        self.qemu_argument_parser = self.app_context.qemu_argument_parser
        self.hardware_page = self.app_context.get_page("hardware")
        self.storage_page = self.app_context.get_page("storage")

        self.tab_widget = QTabWidget()

        self._internal_text_change = False
        self.app_context.qemu_config_updated.connect(self.refresh_display_from_qemu_config)
        self._parse_timer = QTimer(self) 
        self._parse_timer.setSingleShot(True) # Dispara apenas uma vez
        self._parse_timer.setInterval(500) # Atraso de 0.5 segundos (ajustável)
        self.setup_ui()
        self.populate_qemu_binaries()
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
        # 1. Conecta o sinal do timer ao método que faz o parse
        self._parse_timer.timeout.connect(self._do_parse_qemu_command)

        # 2. Conecta a mudança de texto no campo principal (entrada/saída) ao timer
        self.qemuargs_output.textChanged.connect(self._on_qemuargs_output_text_changed)

        # 3. Conecta o sinal de atualização da QemuConfig (do AppContext) à atualização da GUI
        #    Isso garante que, após um parse (direto ou de GUI), a OverviewPage seja redesenhada.
        self.app_context.qemu_config_updated.connect(self.refresh_display_from_qemu_config)

    def populate_qemu_binaries(self):
        self.qemu_config._cache.clear()  # Limpa o cache anterior se quiser forçar reload
        for path in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.startswith("qemu-system-"):
                        full_path = shutil.which(f)
                        if full_path:
                            qemu_path = full_path
                            self.qemu_config._get_helper(qemu_path)  # Instancia e armazena no cache

        all_binaries = list(self.qemu_config._cache.keys())
        self.qemu_combo.blockSignals(True)
        self.qemu_combo.clear()
        self.qemu_combo.addItems([os.path.basename(p) for p in all_binaries])
        self.qemu_combo.blockSignals(False)

        if not self.app_context.qemu_config.get_config_value("qemu_executable") and self.qemu_combo.count() > 0:
            self.qemu_combo.setCurrentIndex(0)
            self.on_qemu_combo_changed(0)
        
    def load_config_to_ui(self):        
        cfg = self.app_context.qemu_config # Mantém sua referência à config existente
        if not cfg:
            return

        self._internal_text_change = True
        self.qemu_combo.blockSignals(True)
        self.custom_path.blockSignals(True)
        # REMOVIDO: self.qemuargs_output.blockSignals(True) e self.qemuextraargs_output.blockSignals(True)
        # O _internal_text_change é suficiente e a atualização dos campos de args é feita por refresh_display_from_qemu_config

        try:
            custom_exec = cfg.get("custom_executable", "")
            self.custom_path.setText(custom_exec)

            if custom_exec:
                self.qemu_combo.setEnabled(False)
                self._update_active_binary(custom_exec)
            else:
                self.qemu_combo.setEnabled(True)
                qemu_exec_basename = cfg.get("qemu_executable", "").strip()
                items = [self.qemu_combo.itemText(i) for i in range(self.qemu_combo.count())]
                if qemu_exec_basename and qemu_exec_basename in items:
                    self.qemu_combo.setCurrentText(qemu_exec_basename)
                    # Chama on_qemu_combo_changed para garantir que _update_active_binary seja acionado
                    self.on_qemu_combo_changed(self.qemu_combo.currentIndex())
                elif self.qemu_combo.count() > 0:
                    self.qemu_combo.setCurrentIndex(0)
                    self.on_qemu_combo_changed(0) # Aciona para o primeiro item

                # Se um executável foi selecionado na combo ou não há nenhum padrão
                if self.qemu_combo.currentIndex() >= 0:
                    selected_basename = self.qemu_combo.itemText(self.qemu_combo.currentIndex())
                    # Encontrar o caminho completo do binário selecionado na combo
                    binary_path = next((p for p in self.qemu_config._cache.keys() 
                                        if os.path.basename(p) == selected_basename), None)
                    self._update_active_binary(binary_path)
                else: # Não há itens na combo
                    self._update_active_binary(None)
                self.refresh_display_from_qemu_config()
        finally:
            self._internal_text_change = False
            self.qemu_combo.blockSignals(False)
            self.custom_path.blockSignals(False)

    def _update_active_binary(self, binary_path: Optional[str]):
        from PyQt5.QtWidgets import QMessageBox

        with self.app_context.signal_blocker():
            custom_path_text = self.custom_path.text().strip()

            data_to_update = {
                "qemu_executable": binary_path if binary_path else "",
                "custom_executable": custom_path_text
            }

            if not binary_path:
                self.arch_label.setText("Architecture: No QEMU binary selected")
                data_to_update["architecture"] = self.arch_label.text()
            else:
                try:
                    arch_text = self.qemu_config.get_arch_for_binary(binary_path)
                    self.arch_label.setText(f"Architecture: {arch_text}")
                    data_to_update["architecture"] = self.arch_label.text()
                except FileNotFoundError as e:
                    QMessageBox.critical(self, "Erro", str(e))
                    self.arch_label.setText("Architecture: Invalid QEMU binary")
                    data_to_update["architecture"] = self.arch_label.text()
                    return
                except Exception as e:
                    QMessageBox.critical(self, "Erro inesperado", f"Erro ao carregar binário: {e}")
                    self.arch_label.setText("Architecture: Erro inesperado")
                    data_to_update["architecture"] = self.arch_label.text()
                    return

            self.qemu_config.update_qemu_config_from_page(data_to_update)
            self.qemu_binary_changed.emit(binary_path if binary_path else "")
            self.overview_config_changed.emit()
            if hasattr(self, "hardware_page") and self.hardware_page:
                self.hardware_page.update_qemu_helper()

    def on_qemu_combo_changed(self, index):
        # Bloqueia os sinais do combobox para evitar disparos múltiplos ou recursão
        self.qemu_combo.blockSignals(True) 
        
        selected_basename = self.qemu_combo.itemText(index)
        full_binary_path = None
        
        # Encontra o caminho completo do binário QEMU no cache
        for path_key in self.qemu_config._cache.keys():
            if os.path.basename(path_key) == selected_basename:
                full_binary_path = path_key
                break

        if full_binary_path:
            # Chama _update_active_binary com o CAMINHO COMPLETO
            self._update_active_binary(full_binary_path)
            # A chamada para update_qemu_config_from_page({"qemu_executable": full_binary_path})
            # já ocorre dentro de _update_active_binary.
            # Também não precisamos mais de self.hardware_page.update_qemu_helper() aqui,
            # pois o refresh_display_from_qemu_config (via qemu_config_updated) já o fará.
        else:
            # Se não encontrou o binário completo, limpa a seleção e atualiza o estado
            self.qemu_config.update_qemu_config_from_page({"qemu_executable": ""})
            self._update_active_binary(None) # Passa None para limpar o estado
        self.app_context.mark_modified()

        self.qemu_combo.blockSignals(False) # Desbloqueia os sinais

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
                QMessageBox.critical(self, "Erro inesperado", f"Erro ao processar binário: {e}")
                self.arch_label.setText("Architecture: Erro inesperado")
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
        # A lógica para determinar bin_path pode ser simplificada usando app_context.current_qemu_executable
        # Isso garante que você está usando o binário que o AppContext considera como ativo.
        bin_path = self.app_context.qemu_config.current_qemu_executable

        if not bin_path:
            self.console_output.append("No QEMU binary selected.")
            return

        # --- NOVA LÓGICA DE PARSER/CONFIG AQUI ---
        # 1. Obtenha a QemuConfig atual do AppContext
        qemu_config_object = self.app_context.get_qemu_config_object()
        
        # 2. Peça à QemuConfig para gerar a string completa de argumentos QEMU
        full_qemu_cmd_string = qemu_config_object.to_qemu_args_string()
        
        # 3. Use o utilitário do AppContext para dividir a string em uma lista de argumentos seguros
        qemu_args_list = self.app_context.split_shell_command(full_qemu_cmd_string[0])        # --- FIM DA NOVA LÓGICA ---

        self.console_output.append(f"Launching: {bin_path} {' '.join(shlex.quote(arg) for arg in qemu_args_list)}")
        
        try:
            # Use subprocess.run para simplicidade, se você não precisa de interação em tempo real
            # Ajustei o timeout para 60 segundos, que é mais razoável para iniciar uma VM.
            result = subprocess.run(
                [bin_path] + qemu_args_list,  # Passe a lista de argumentos formatada
                capture_output=True, 
                text=True, 
                timeout=60, 
                check=False # Não levanta exceção para códigos de saída diferentes de zero
            )
            self.console_output.append(result.stdout.strip())
            self.console_output.append(result.stderr.strip())
            self.console_output.append(f"QEMU process exited with code: {result.returncode}")
        except subprocess.TimeoutExpired:
            self.console_output.append(f"Timeout ao executar QEMU. O processo excedeu o tempo limite de 60 segundos.")
        except FileNotFoundError:
            self.console_output.append(f"Erro: Binário QEMU não encontrado em '{bin_path}'.")
        except Exception as e:
            self.console_output.append(f"Falha ao lançar QEMU: {e}")

    def _on_args_changed(self):
        """
        Chamado quando o texto em `qemuargs_output` (o campo de entrada principal) muda.
        Inicia o processo de parse e atualização da GUI.
        """
        if self._internal_text_change: # Impede loops infinitos se o próprio código muda o texto
            return

        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        # Chama o AppContext para parsear a string.
        # O AppContext, por sua vez, chamará refresh_from_qemu_config()
        # após o parse para atualizar a GUI.
        if raw_cmd_line:
            self.qemu_argument_parser.parse_qemu_command_line(raw_cmd_line)
        else:
            # Se a caixa de entrada está vazia, resetar toda a configuração
            self.qemu_config.reset()
            self.refresh_from_qemu_config() # Para limpar as GUIs e outputs

    def refresh_display_from_qemu_config(self):
        """
        ATUALIZA A INTERFACE VISUAL da OverviewPage.
        Recebe o estado atual da QemuConfig (gerado pela GUI ou via parse direto)
        e exibe a linha de comando completa e os argumentos extras.
        Este é o método de "RENDERIZAÇÃO" da OverviewPage.
        """
        # Ativa a flag para ignorar as mudanças programáticas no campo de texto
        self._internal_text_change = True 

        try:
            qemu_config = self.app_context.get_qemu_config_object()
            # Chama o método que faz o "parse reverso" (GUI para string)
            # e também separa os extras para exibição.
            full_cmd_str, extra_args_str = qemu_config.to_qemu_args_string()
            
            # Atualiza o campo principal (qemuargs_output) com a string completa gerada
            self.qemuargs_output.setPlainText(full_cmd_str)
            
            # Atualiza o campo de argumentos extras (qemuextraargs_output)
            self.qemuextraargs_output.setPlainText(extra_args_str)

            print("OverviewPage: Display atualizado a partir da QemuConfig.")

        except Exception as e:
            print(f"OverviewPage: ERRO ao atualizar display: {e}")
            self.qemuargs_output.setPlainText("ERRO: Falha ao gerar comando QEMU.")
            self.qemuextraargs_output.setPlainText("ERRO: Falha ao gerar extras.")
        finally:
            # Desativa a flag após a atualização programática
            self._internal_text_change = False

    def _on_qemuargs_output_text_changed(self):
        """
        Chamado quando o texto em `qemuargs_output` MUDOU (pelo usuário ou cola).
        Inicia ou reinicia o timer para parsear o comando após um curto atraso.
        """
        # Se a mudança foi programática (do refresh_display_from_qemu_config), ignore.
        if self._internal_text_change: 
            return

        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        if raw_cmd_line:
            # Há texto: inicia ou reinicia o timer. O parse real acontece em _do_parse_qemu_command.
            print("OverviewPage: Texto alterado pelo usuário. Iniciando/reiniciando timer de parse.")
            self._parse_timer.start() 
        else:
            # O texto foi limpo: reseta a configuração imediatamente e para o timer.
            print("OverviewPage: Campo de comando QEMU limpo. Resetando configuração.")
            self._parse_timer.stop() 
            self.app_context.get_qemu_config_object().reset()
            # Emite o sinal para atualizar TODA a GUI (incluindo outras páginas) para o estado resetado.
            self.app_context.qemu_config_updated.emit(self.app_context.get_qemu_config_object())

    def _do_parse_qemu_command(self):
        """
        Este método é chamado pelo QTimer após o atraso.
        Ele dispara o parse da linha de comando no AppContext.
        """
        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        if raw_cmd_line:
            print(f"OverviewPage: Timer disparado. Executando parse DIRETO de: '{raw_cmd_line}'")
            # Este é o ponto onde o "parse direto" acontece.
            # O AppContext fará o parse, atualizará a QemuConfig (all_args e extra_args_list),
            # e então emitirá qemu_config_updated.
            # O sinal qemu_config_updated, por sua vez, chamará refresh_display_from_qemu_config()
            # para redesenhar a OverviewPage (e outras páginas da GUI).
            self.qemu_argument_parser.parse_qemu_command_line_to_config(raw_cmd_line)
        else:
            print("OverviewPage: Timer disparado, mas campo de comando QEMU está vazio.")

    def resolve_dependencies(self):
        self.hardware_page = self.app_context.get_page("hardware")
        self.storage_page = self.app_context.get_page("storage")



 