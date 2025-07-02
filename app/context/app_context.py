# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
from __future__ import annotations

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional

import shlex
import re
import json

from contextlib import contextmanager
from app.utils.qemu_config import QemuConfig
from app.utils.qemu_parser import QemuParser
from app.utils.qemu_helper import QemuHelper
class AppContext(QObject):
    qemu_config_updated = pyqtSignal(object)
    qemu_config_modified = pyqtSignal(bool)
    storage_media_changed = pyqtSignal()

    def __init__(self, qemu_path=None):
        self._qemu_helper_cache: dict[str, QemuHelper] = {}
        super().__init__()

        self.qemu_config = QemuConfig()
        self.qemu_config.set_app_context(self)
        
        self.qemu_argument_parser = QemuParser(config_provider=self.get_qemu_config_object)
        self.qemu_argument_parser.set_app_context(self)

        self._qemu_helper_cache = {}  # armazena múltiplos helpers
        self.qemu_helper = None

        if qemu_path:
            self.qemu_helper = self.get_helper(qemu_path)

        self._is_loading = False     
        self._blocking_signals = False
        self._last_saved_config_hash = None
        self._is_modified = False
        self._is_hash_modified = False 
        self.pages = {}
        self.helpers = {}

        self.qemu_config = QemuConfig()
        self.qemu_config.set_app_context(self)

    def get_helper(self, qemu_path: str) -> QemuHelper:
        if qemu_path in self._qemu_helper_cache:
            return self._qemu_helper_cache[qemu_path]

        if not QemuHelper._is_valid_qemu_binary(qemu_path):
            raise FileNotFoundError(f"Binário QEMU inválido: {qemu_path}")

        helper = QemuHelper(qemu_path)
        helper.set_app_context(self)

        self._qemu_helper_cache[qemu_path] = helper
        return helper

    def _register_page(self, name: str, page: QObject):
        self.pages[name] = page

    def _register_helper(self, name: str, helper: QObject):
        self.helpers[name] = helper

    def _get_page(self, name: str):
        return self.pages.get(name)
    
    def _get_helper(self, name: str):
        return self.helpers.get(name)

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
        try:
            return shlex.split(cleaned.strip())
        except Exception:
            return []

    def format_shell_command(self, args: list[str]) -> list[str]:
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
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            with self.signal_blocker():
                self.qemu_config.update_all_args(config_data)
            self.mark_saved()
            self.qemu_config_updated.emit(self.qemu_config)
        except Exception:
            pass

    def get_qemu_config_object(self) -> QemuConfig:
        return self.qemu_config

    def save_qemu_config(self, file_path: str):
        is_safe_to_save = True
        try:
            for value in self.qemu_config.all_args.values():
                if not isinstance(value, (dict, list, str, int, float, bool, type(None))):
                    is_safe_to_save = False
                    break
        except Exception:
            is_safe_to_save = False

        if not is_safe_to_save:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText("Erro de Salvamento")
            msg_box.setInformativeText("A configuração contém dados inválidos e não pode ser salva. Verifique o console do terminal para detalhes técnicos.")
            msg_box.setWindowTitle("Erro")
            msg_box.exec_()
            return

        try:
            with open(file_path, 'w') as f:
                json.dump(self.qemu_config.all_args, f, indent=4)
            self.mark_saved()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

    def parse_cli_and_notify(self, cmd_line_str: str):
        self.qemu_argument_parser.parse_qemu_command_line_to_config(cmd_line_str)
        self.qemu_config_updated.emit(self.qemu_config)
        self.mark_saved()
