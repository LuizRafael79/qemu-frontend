from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QHBoxLayout, QTextEdit, 
    QTabWidget, QFileDialog, QRadioButton
)
from PyQt5.QtCore import pyqtSignal
import os
import re
import subprocess
import shutil
import shlex

import app
from app.context import app_context
from app.utils.qemu_helper import QemuInfoCache
from app.context.app_context import AppContext

class OverviewPage(QWidget):
    overview_config_changed = pyqtSignal()
    qemu_binary_changed = pyqtSignal(str)

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.qemu_info_cache = QemuInfoCache()

        self._internal_text_change = False
        self.app_context.qemu_args_pasted.connect(self.update_qemu_args)

        self.setup_ui()
        self.populate_qemu_binaries()
        self.bind_signals()

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
        self.console_output = QTextEdit()
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
        self.qemuargs_output.textChanged.connect(self._on_args_changed)
        self.qemuextraargs_output.textChanged.connect(self._on_args_changed)

    def populate_qemu_binaries(self):
        self.qemu_info_cache._cache.clear()  # Limpa o cache anterior se quiser forçar reload
        for path in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.startswith("qemu-system-"):
                        full_path = shutil.which(f)
                        if full_path:
                            self.qemu_info_cache._get_helper(full_path)  # Instancia e armazena no cache

        all_binaries = list(self.qemu_info_cache._cache.keys())
        self.qemu_combo.blockSignals(True)
        self.qemu_combo.clear()
        self.qemu_combo.addItems([os.path.basename(p) for p in all_binaries])
        self.qemu_combo.blockSignals(False)

    def load_config_to_ui(self):
        cfg = self.app_context.config
        if not cfg:
            return

        self._internal_text_change = True
        self.qemu_combo.blockSignals(True)
        self.custom_path.blockSignals(True)
        self.qemuargs_output.blockSignals(True)
        self.qemuextraargs_output.blockSignals(True)

        try:
            custom_exec = cfg.get("custom_executable", "")
            self.custom_path.setText(custom_exec)

            if custom_exec:
                self.qemu_combo.setEnabled(False)
                self._update_active_binary(custom_exec)
            else:
                self.qemu_combo.setEnabled(True)
                qemu_exec_basename = cfg.get("qemu_executable", "")
                items = [self.qemu_combo.itemText(i) for i in range(self.qemu_combo.count())]
                if qemu_exec_basename and qemu_exec_basename in items:
                    self.qemu_combo.setCurrentText(qemu_exec_basename)
                elif self.qemu_combo.count() > 0:
                    self.qemu_combo.setCurrentIndex(0)

                if self.qemu_combo.currentIndex() >= 0:
                    binary_path = list(self.qemu_info_cache._cache.keys())[self.qemu_combo.currentIndex()]
                    self._update_active_binary(binary_path)
                else:
                    self._update_active_binary(None)

            qemu_args = cfg.get("qemu_args", "")
            extra_args = cfg.get("extra_args", "")

            self.qemuargs_output.setPlainText(" ".join(qemu_args) if isinstance(qemu_args, list) else qemu_args)
            self.qemuextraargs_output.setPlainText(" \\\n".join(extra_args) if isinstance(extra_args, list) else extra_args)

        finally:
            self._internal_text_change = False
            self.qemu_combo.blockSignals(False)
            self.custom_path.blockSignals(False)
            self.qemuargs_output.blockSignals(False)
            self.qemuextraargs_output.blockSignals(False)

    def _update_active_binary(self, binary_path):
        with self.app_context.signal_blocker():
            if not binary_path:
                self.arch_label.setText("Architecture: No QEMU binary selected")
                self.app_context.update_config({"architecture": self.arch_label.text()})
                self.qemu_binary_changed.emit("")
                self.overview_config_changed.emit()
                return

            arch_text = self.qemu_info_cache.get_arch_for_binary(binary_path)
            self.arch_label.setText(f"Architecture: {arch_text}")

            self.app_context.update_config({
                "architecture": self.arch_label.text(),
                "qemu_executable": os.path.basename(binary_path),
                "custom_executable": self.custom_path.text().strip()
            })
            self.app_context.config_changed.emit()

            self.qemu_binary_changed.emit(binary_path)
            self.overview_config_changed.emit()

    def on_qemu_combo_changed(self, index):
        if 0 <= index < len(self.qemu_info_cache._cache.keys()):
            bin_path = list(self.qemu_info_cache._cache.keys())[index]
            self._update_active_binary(bin_path)
            hardware_page = self.app_context.get_page("hardware")
            if hardware_page:
                hardware_page.update_qemu_helper()

    def on_custom_path_changed(self, text):
        text = text.strip()
        if text:
            self.qemu_combo.setEnabled(False)
            self._update_active_binary(text)
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
        binary_list = list(self.qemu_info_cache._cache.keys())
        index = self.qemu_combo.currentIndex()
        bin_path = binary_list[index] if 0 <= index < len(binary_list) else ""
        if not bin_path and self.qemu_combo.currentIndex() >= 0:
            bin_path = list(self.qemu_info_cache._cache.keys())[self.qemu_combo.currentIndex()]
        if not bin_path:
            self.console_output.append("No QEMU binary selected.")
            return
        self.console_output.append(f"Launching: {bin_path}")
        try:
            proc = subprocess.Popen([bin_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = proc.communicate(timeout=10)
            self.console_output.append(stdout)
            self.console_output.append(stderr)
        except Exception as e:
            self.console_output.append(f"Failed to launch QEMU: {e}")

    def update_qemu_args(self, args_list):
        self._internal_text_change = True
        try:
            with self.app_context.signal_blocker():
                if not args_list:
                    args_list = []

                recognized_flags = {
                    "-cpu", "-m", "-smp", "-machine", "-accel", "-k", "-M",
                    "-usb", "-rtc", "-audiodev", "-display", "-nodefaults", "-boot"
                }
                parsed_main = []
                parsed_extra = []

                i = 0
                while i < len(args_list):
                    arg = args_list[i]
                    if arg in recognized_flags:
                        parsed_main.append(arg)
                        if i + 1 < len(args_list) and not args_list[i + 1].startswith("-"):
                            parsed_main.append(args_list[i + 1])
                            i += 1
                    else:
                        parsed_extra.append(arg)
                    i += 1

                self.app_context.update_config({
                    "qemu_args": parsed_main,
                    "extra_args": parsed_extra
                })

                self.qemuargs_output.blockSignals(True)
                self.qemuargs_output.setPlainText(" \\\n".join(parsed_main))
                self.qemuargs_output.blockSignals(False)

                self.qemuextraargs_output.blockSignals(True)
                self.qemuextraargs_output.setPlainText(" \\\n".join(parsed_extra))
                self.qemuextraargs_output.blockSignals(False)

        finally:
            self._internal_text_change = False

    def _on_args_changed(self):
        if self._internal_text_change:
            return

        raw = self.qemuargs_output.toPlainText().strip()
        extra_raw = self.qemuextraargs_output.toPlainText().strip()

        args = []

        try:
            # 1. Se houver texto em qemuargs, processa
            if raw:
                cmd_clean = raw.replace("\\\n", " ").replace("\n", " ")
                args += shlex.split(cmd_clean)

            # 2. Se houver texto em extra_args, processa também
            if extra_raw:
                args += shlex.split(extra_raw)

            self.app_context.qemu_args_pasted.emit(args)

            # 3. Se nada foi passado (tudo vazio), limpa o config
            if not args:
                self.app_context.update_config({
                    "qemu_args": [],
                    "extra_args": [],
                    "drives": [],
                    "floppies": [],
                    "architecture": "",
                    "qemu_executable": "",
                    "custom_executable": ""
                })
            self.app_context.config_changed.emit()

        except Exception as e:
            print(f"Erro ao fazer parse da linha de comando: {e}")

# Dentro do OverviewPage, substitua:

    def qemu_direct_parse(self, args_list: list[str]):
        remaining = args_list
        hardware_page = self.app_context.get_page("hardware")
        if hardware_page:
            remaining = hardware_page.qemu_direct_parse(remaining)
        storage_page = self.app_context.get_page("storage")
        if storage_page:
            remaining = storage_page.qemu_direct_parse(remaining)
        self.update_qemu_args(remaining)

    def qemu_reverse_parse(self) -> list[str]:
        args = []
        hardware_page = self.app_context.get_page("hardware")
        if hardware_page:
            args += hardware_page.qemu_reverse_parse_args()

        storage_page = self.app_context.get_page("storage")
        if storage_page:
            args += storage_page.qemu_reverse_parse_args()

        extra_raw = self.qemuextraargs_output.toPlainText().strip()
        if extra_raw:
            try:
                args += shlex.split(extra_raw)
            except Exception as e:
                print(f"Erro ao fazer parse dos argumentos extras: {e}")

        self.qemuargs_output.blockSignals(True)
        self.qemuargs_output.setPlainText(" \\\n".join(args))
        self.qemuargs_output.blockSignals(False)

        return args
 