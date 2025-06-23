# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtCore import QObject, pyqtSignal
import shlex
import re
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

    # ---------- Utilitários ----------

    def split_shell_command(self, cmdline_str: str | list[str]) -> list[str]:
        """
        Divide uma linha de comando shell QEMU em lista de argumentos.
        Suporta string com quebras de linha usando '\\' e espaços.
        Usa shlex para respeitar aspas e escapes.
        """
        if isinstance(cmdline_str, list):
            cmdline_str = ' '.join(cmdline_str)

        cleaned = re.sub(r"\\\s*\n", " ", cmdline_str)
        cleaned = re.sub(r"[\r\n]+", " ", cleaned)

        try:
            return shlex.split(cleaned.strip())
        except Exception as e:
            print(f"[split_shell_command] erro ao fazer split: {e}")
            return []

    def format_shell_command(self, args: list[str]) -> list[str]:
        """
        Recebe lista de argumentos e retorna lista formatada para visualização
        tipo shell, juntando flags com seus valores na mesma linha para facilitar edição.
        Cada item na lista representa uma linha na visualização.
        Exemplo:
        ['-m 2048', '-cpu host', '-usb']
        """
        formatted = []
        it = iter(args)

        while True:
            try:
                arg = next(it)
            except StopIteration:
                break

            if arg.startswith("-"):
                try:
                    val = next(it)
                    if val.startswith("-"):
                        formatted.append(arg)
                        # devolve o val para o iterador
                        it = iter([val] + list(it))
                    else:
                        formatted.append(f"{arg} {val}")
                except StopIteration:
                    formatted.append(arg)
            else:
                formatted.append(arg)

        return formatted