# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
from __future__ import annotations

import shlex
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from app.context.app_context import AppContext

class QemuArgumentParser:
    def __init__(self, app_context: "AppContext"):
        self.app_context = app_context

    def _parse_key_value_string(self, s: str) -> Dict[str, Any]:
        """Helper genérico para parsear strings como 'key=value,key2=value2'."""
        sub_options = {}
        parts = s.split(',')
        for part in parts:
            part = part.strip()
            if not part: continue
            if '=' in part:
                key, val = part.split('=', 1)
                sub_options[key.strip()] = val.strip()
            else:
                sub_options[part] = True 
        return sub_options

    def _parse_device_string(self, value_string: str) -> Dict[str, Any]:
        """Parser especializado para argumentos como -device."""
        parts = value_string.split(',')
        if not parts: return {}
        parsed_dict = {'interface': parts[0].strip()}
        for part in parts[1:]:
            if '=' in part:
                key, val = part.split('=', 1)
                parsed_dict[key.strip()] = val.strip()
            elif part.strip():
                parsed_dict[part.strip()] = "true" 
        return parsed_dict

    def _parse_boot_string(self, value_string: str) -> Dict[str, Any]:
        """Parser especializado para o argumento -boot."""
        sub_options = {}
        parts = value_string.split(',')
        if parts and '=' not in parts[0]:
            sub_options['order'] = parts[0].strip()
            remaining_parts = parts[1:]
        else:
            remaining_parts = parts
        for part in remaining_parts:
            part = part.strip()
            if '=' in part:
                key, val = part.split('=', 1)
                sub_options[key.strip()] = val.strip()
        return sub_options
    
    def parse_qemu_command_line_to_config(self, cmd_line_str: str):
        """Analisa uma string de linha de comando QEMU usando shlex para robustez."""
        try:
            qemu_config = self.app_context.qemu_config
            if qemu_config:
                qemu_config.reset()
                cleaned_str = cmd_line_str.replace('\\\n', ' ').replace('\\\r\n', ' ')            
            try:
                args = shlex.split(cleaned_str)
            except ValueError as e:
                print(f"[WARN] Erro ao fazer shlex.split: {e}")
                import traceback; traceback.print_exc()
                return

            if args and 'qemu-system-' in args[0]:
                qemu_config = self.app_context.qemu_config
                if qemu_config:
                    qemu_config.all_args['qemu_executable'] = args.pop(0)

            current_all_args = {}
            current_extra_args_list: List[Tuple[str, Optional[str]]] = []
            
            i = 0
            while i < len(args):
                arg = args[i]
                if not arg.startswith('-'):
                    current_extra_args_list.append(('', arg))
                    i += 1
                    continue

                arg_name = arg.lstrip('-')
                is_flag_only = (i + 1 == len(args)) or (args[i+1].startswith('-'))

                if is_flag_only:
                    current_all_args[arg_name] = True
                    i += 1
                else:
                    value_str = args[i+1]
                    parsed_value = value_str  # default

                    if arg_name in ['device', 'drive', 'netdev', 'audiodev', 'machine', 'M', 'rtc', 'boot']:
                        try:
                            if arg_name == 'device':
                                parsed_value = self._parse_device_string(value_str)
                            elif arg_name == 'boot':
                                parsed_value = self._parse_boot_string(value_str)
                            else:
                                parsed_value = self._parse_key_value_string(value_str)
                        except Exception as e:
                            print(f"[ERROR] Falha ao parsear {arg_name} com valor '{value_str}': {e}")
                            import traceback; traceback.print_exc()

                    if arg_name in ['device', 'drive', 'netdev', 'audiodev']:
                        current_all_args.setdefault(arg_name, []).append(parsed_value)
                    else:
                        current_all_args[arg_name] = parsed_value
                    i += 2
            qemu_config = self.app_context.qemu_config
            if qemu_config:
                qemu_config.all_args.update(current_all_args)
                qemu_config.extra_args_list = current_extra_args_list

        except Exception as e:
            print(f"[FATAL] Erro geral no parse_qemu_command_line_to_config: {e}")
            import traceback; traceback.print_exc()
