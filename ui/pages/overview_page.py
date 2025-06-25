# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QHBoxLayout, QTextEdit, 
    QTabWidget, QFileDialog, QPlainTextEdit, QMessageBox
)
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor

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
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(500)
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
        # 1. Connect the signal of the timer (500ms) to the slot that will parse the qemu command
        self._parse_timer.timeout.connect(self._do_parse_qemu_command)

        # 2. Connect the change of the text of the QemuArgsOutput to the slot that will parse the qemu command
        self.qemuargs_output.textChanged.connect(self._on_qemuargs_output_text_changed)

        # 3. Connect the signal change of QemuConfig (Via AppContext)
        #    That guarantees that the OverviewPage will be refreshed
        self.app_context.qemu_config_updated.connect(self.refresh_display_from_qemu_config)

    def populate_qemu_binaries(self):
        self.qemu_config._cache.clear()  # Clean last cache for reload
        for path in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.startswith("qemu-system-"):
                        full_path = shutil.which(f)
                        if full_path:
                            qemu_path = full_path
                            self.qemu_config._get_helper(qemu_path)  # Instances and cache the path
        
        all_binaries = list(self.qemu_config._cache.keys())
        self.qemu_combo.blockSignals(True)
        self.qemu_combo.clear()
        self.qemu_combo.addItems([os.path.basename(p) for p in all_binaries])
        self.qemu_combo.blockSignals(False)

        if not self.app_context.qemu_config.get_config_value("qemu_executable") and self.qemu_combo.count() > 0:
            self.qemu_combo.setCurrentIndex(0)
            self.on_qemu_combo_changed(0)
        
    def load_config_to_ui(self):        
        cfg = self.app_context.qemu_config
        if not cfg:
            return

        self._internal_text_change = True
        self.qemu_combo.blockSignals(True)
        self.custom_path.blockSignals(True)

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
                    # Call on_qemu_combo_changed and guarantee that the current index is valid
                    self.on_qemu_combo_changed(self.qemu_combo.currentIndex())
                elif self.qemu_combo.count() > 0:
                    self.qemu_combo.setCurrentIndex(0)
                    self.on_qemu_combo_changed(0) # Select the first item
                 
                if self.qemu_combo.currentIndex() >= 0:
                    selected_basename = self.qemu_combo.itemText(self.qemu_combo.currentIndex())
                    # Find complete path of Binary selected
                    binary_path = next((p for p in self.qemu_config._cache.keys() 
                                        if os.path.basename(p) == selected_basename), None)
                    self._update_active_binary(binary_path)
                else: # No have items in binary combo
                    self._update_active_binary(None)
                self.refresh_display_from_qemu_config()
        finally:
            self._internal_text_change = False
            self.qemu_combo.blockSignals(False)
            self.custom_path.blockSignals(False)

    def _update_active_binary(self, binary_path: Optional[str]):

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
                    QMessageBox.critical(self, "Error", str(e))
                    self.arch_label.setText("Architecture: Invalid QEMU binary")
                    data_to_update["architecture"] = self.arch_label.text()
                    return
                except Exception as e:
                    QMessageBox.critical(self, "Unexpected error", f"Unexpected error loading binary: {e}")
                    self.arch_label.setText("Architecture: Unexpected error")
                    data_to_update["architecture"] = self.arch_label.text()
                    return

            self.qemu_config.update_qemu_config_from_page(data_to_update)
            self.qemu_binary_changed.emit(binary_path if binary_path else "")
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
        bin_path = self.app_context.qemu_config.current_qemu_executable

        if not bin_path:
            self.console_output.append("No QEMU binary selected.")
            return

        # 1. Obtain the QemuConfig object from the AppContext
        qemu_config_object = self.app_context.get_qemu_config_object()
        
        # 2. Call QemuConfig to generate the Qemu Parse of arguments
        full_qemu_cmd_string = qemu_config_object.to_qemu_args_string()
        
        # 3. Use the AppContext to generate the Qemu Args list to execute VM
        qemu_args_list = self.app_context.split_shell_command(full_qemu_cmd_string[0])
        # 4. Launch the Qemu process, and redirect all output to the Console Window Tab
        self.console_output.append(f"Launching: {bin_path} {' '.join(shlex.quote(arg) for arg in qemu_args_list)}")
        
        try:
            result = subprocess.run(
                [bin_path] + qemu_args_list,  # Pass the formated arguments to Qemu
                capture_output=True, 
                text=True, 
                timeout=60, 
                check=False # Don't raise an exception if the process enter in a non-zero status
            )
            self.console_output.append(result.stdout.strip())
            self.console_output.append(result.stderr.strip())
            self.console_output.append(f"QEMU process exited with code: {result.returncode}")
        except subprocess.TimeoutExpired:
            self.console_output.append(f"Qemu execute, time-out. The process excedded the 60 seconds time limit.")
        except FileNotFoundError:
            self.console_output.append(f"Error: Qemu Binary not found in: '{bin_path}'.")
        except Exception as e:
            self.console_output.append(f"Fail to launch Qemu. Unexpected error: {e}")

    def _on_args_changed(self):
        """
        Called when the text in `qemuargs_output` (the main input field) changes.
        Starts the GUI parsing and updating process.
        """
        if self._internal_text_change: # Block recursion if the output has changed/edited
            return

        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        # Call AppContext to parse the text inputed in QemuArgs Window Tab
        if raw_cmd_line:
            self.qemu_argument_parser.parse_qemu_command_line(raw_cmd_line)
        else:
            self.qemu_config.reset()
            self.refresh_from_qemu_config() # not implemented yet

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
            self.qemuargs_output.setPlainText(full_cmd_str)
            
            # Refresh the "Extra Args" Window Tab
            self.qemuextraargs_output.setPlainText(extra_args_str)

            print("[INFO][DEBUG] OverviewPage: Page refresh by QemuConfig.")

        except Exception as e:
            print(f"[WARN][DEBUG] OverviewPage: Error refreshing page. Error: {e}")
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
            print("[INFO] OverviewPage: Text inputed by user. Start/Restarting parse timer (500ms).")
            self._parse_timer.start() 
        else:            
            print("[INFO] OverviewPage: QemuArgs Window is cleaned by user. Reseting configuration.")
            self._parse_timer.stop() 
            self.app_context.get_qemu_config_object().reset()
            # Emit a signal to RESET all GUI's to default or last saved state.
            self.app_context.qemu_config_updated.emit(self.app_context.get_qemu_config_object())

    def _do_parse_qemu_command(self):
        """
        This method is called by QTimer after the delay.
        It triggers the command line parsing in the AppContext.
        """
        raw_cmd_line = self.qemuargs_output.toPlainText().strip()
        
        if raw_cmd_line:
            print(f"[INFO] OverviewPage: Timer Started. Starting reverse parse from inputed args: '{raw_cmd_line}'")
            self.qemu_argument_parser.parse_qemu_command_line_to_config(raw_cmd_line)
        else:
            print("[WARN]OverviewPage: Timer Started, but the QemuArgs status is clean, report that in GitHub.")

    def resolve_dependencies(self):
        self.hardware_page = self.app_context.get_page("hardware")
        self.storage_page = self.app_context.get_page("storage")

    def append_colored_text(self, text, color):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self.console_output.textCursor() #type: ignore
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + '\n', fmt)
        self.console_output.setTextCursor(cursor) #type: ignore
        self.console_output.ensureCursorVisible() #type: ignore

        # The use of type: ignore is only for the purpose of the IDE plugin, like Pylance in Vscode
        # is not able to detect the types of functions arguments (false positive)




 