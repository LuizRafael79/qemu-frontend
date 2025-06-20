# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtCore import QObject, pyqtSignal
import shlex
from contextlib import contextmanager
from app.utils.qemu_helper import QemuHelper, QemuInfoCache

class AppContext(QObject):
    config_saved = pyqtSignal()
    config_loaded = pyqtSignal()
    config_changed = pyqtSignal()
    qemu_args_pasted = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.config = {}
        self.qemu_info_cache = QemuInfoCache()
        self.config_modified = False
        self._is_loading = False
        self._blocking_signals = False

        self.pages = {}  # Novo: armazena as páginas

    # ---------- Registro de Páginas ----------

    def register_page(self, name: str, page: QObject):
        """Registra uma página acessível por nome."""
        self.pages[name] = page

    def get_page(self, name: str):
        """Retorna a página registrada com o nome informado."""
        return self.pages.get(name)

    # ---------- Configuração ----------

    def set_config(self, new_config):
        self.config = new_config
        self.config_loaded.emit()
        self.config_modified = False

    def update_config(self, partial_config):
        modified = False
        for key, value in partial_config.items():
            if self.config.get(key) != value:
                self.config[key] = value
                modified = True

        if modified:
            print("[update_config] Emite config_changed")
            self.config_changed.emit()
            self.config_modified = True

    def mark_saved(self):
        self.config_saved.emit()
        self.config_modified = False

    def is_modified(self):
        return self.config_modified

    # ---------- Sinais e bloqueios ----------

    def block_all_signals(self, state: bool = True):
        self._blocking_signals = state

    def start_loading(self):
        self._is_loading = True

    def finish_loading(self):
        self._is_loading = False
        self.config_modified = False

    @contextmanager
    def loading(self):
        self.start_loading()
        try:
            yield
        finally:
            self.finish_loading()

    @contextmanager
    def signal_blocker(self):
        self.block_all_signals(True)
        try:
            yield
        finally:
            self.block_all_signals(False)

    # ---------- Utilitário ----------

    def split_shell_command(self, cmdline_str):
        if isinstance(cmdline_str, list):
            cmdline_str = ' '.join(cmdline_str)
        cleaned = cmdline_str.replace("\\\n", " ").replace("\\\r\n", " ").strip()
        return shlex.split(cleaned)
