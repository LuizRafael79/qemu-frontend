# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
import shlex
import re
import json
from contextlib import contextmanager
from app.utils.qemu_helper import QemuConfig, QemuArgumentParser

class AppContext(QObject):
    qemu_config_updated = pyqtSignal(object)
    qemu_config_modified = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.qemu_config = QemuConfig()
        self.qemu_argument_parser = QemuArgumentParser()
        self._is_loading = False     
        self._blocking_signals = False
        self._last_saved_config_hash = None
        self._is_modified = False
        self._is_hash_modified = False 
        self.pages = {}           

    def register_page(self, name: str, page: QObject):
        self.pages[name] = page
        print(f"[AppContext] Página registrada: {name}")

    def get_page(self, name: str):
        return self.pages.get(name)   

    def block_all_signals(self, state: bool = True):
        self._blocking_signals = state

    def start_loading(self):
        self._is_loading = True

    def finish_loading(self):
        self._is_loading = False

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
 
    def split_shell_command(self, cmdline_str: str | list[str]) -> list[str]:
        if isinstance(cmdline_str, list):
            cmdline_str = ' '.join(cmdline_str)
        cleaned = re.sub(r"\\\s*\n", " ", cmdline_str)
        cleaned = re.sub(r"[\r\n]+", " ", cleaned)
        try: return shlex.split(cleaned.strip())
        except Exception as e:
            print(f"[split_shell_command] erro ao fazer split: {e}")
            return []

    def format_shell_command(self, args: list[str]) -> list[str]:
        formatted = []
        it = iter(args)
        while True:
            try: arg = next(it)
            except StopIteration: break
            if arg.startswith("-"):
                try:
                    val = next(it)
                    if val.startswith("-"): 
                        formatted.append(arg)
                        it = iter([val] + list(it)) 
                    else: 
                        formatted.append(f"{arg} {val}")
                except StopIteration: 
                    formatted.append(arg)
            else: 
                formatted.append(arg)
        return formatted
    
    def _update_config_hash(self):
        config_str = json.dumps(self.qemu_config.all_args, sort_keys=True)
        self._last_saved_config_hash = hash(config_str)

    def is_modified(self) -> bool:
        current_config_str = json.dumps(self.qemu_config.all_args, sort_keys=True)
        is_hash_diff = (hash(current_config_str) != self._last_saved_config_hash)
        return self._is_modified or self._is_hash_modified or is_hash_diff

    def mark_saved(self):
        self._is_modified = False
        self._update_config_hash()
        self.qemu_config_updated.emit(self.qemu_config)
        self.qemu_config_modified.emit(False)
    
    def mark_modified(self):
        if not self._is_modified:
            self._is_modified = True
            self.qemu_config_modified.emit(True)

    def load_qemu_config(self, file_path: str):
        print(f"AppContext: Carregando configuração do arquivo: {file_path}")
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            
            with self.signal_blocker():
                self.qemu_config.update_all_args(config_data)

            self.mark_saved()
            self.qemu_config_updated.emit(self.qemu_config)
            print("AppContext: Configuração carregada do arquivo e qemu_config_updated emitida.")
        except Exception as e:
            print(f"AppContext: Erro ao carregar configuração: {e}")
            # Você pode querer emitir um sinal de erro aqui ou lidar com ele de outra forma.

    def get_qemu_config_object(self) -> 'QemuConfig':
        """Retorna a instância atual de QemuConfig."""
        return self.qemu_config
    
    def save_qemu_config(self, file_path: str):
        """Salva a configuração QEMU atual em um arquivo JSON."""
        print(f"AppContext: Salvando configuração para o arquivo: {file_path}")
        try:
            with open(file_path, 'w') as f:
                json.dump(self.qemu_config.all_args, f, indent=4)
            self.mark_saved() # <--- Adicione ou verifique esta linha
            print("AppContext: Configuração salva com sucesso.")
        except Exception as e:
            print(f"AppContext: Erro ao salvar configuração: {e}")
            raise # Re-lança a exceção para que a MainWindow possa lidar com ela (ex: QMessageBox)

    def append_colored_text(self, text, color):
        self.overview_page = self.get_page("Overview")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self.overview_page.console_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + '\n', fmt)
        self.overview_page.console_output.setTextCursor(cursor)
        self.overview_page.console_output.ensureCursorVisible()     
