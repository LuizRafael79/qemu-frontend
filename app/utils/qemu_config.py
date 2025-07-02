# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

class QemuConfig:
    _cache = {}
    current_qemu_executable: str = ""

    def __init__(self):
        self._context = None
        self.all_args: Dict[str, Any] = {
            'm': 1024,
            'cpu': 'default',
            'machine': {'type': 'pc'},
            'smp': 2,
            'enable-kvm': False,
            'usb': False,
            'usb-tablet': False,
            'usb-mouse': False,
            'rtc': {'base': 'localtime', 'clock': 'host'},
            'nodefaults': False,
            'bios': '',
            'boot': {},
            'device': [],
            'netdev': [],
            'drive': [],
            'floppy': []
        }
        self.extra_args_list: List[Tuple[str, Optional[str]]] = []
        self._is_modified = False

    def set_app_context(self, context):
        self._context = context

    @classmethod
    def _get_helper(cls, qemu_path: str, context=None) -> 'QemuHelper': # type: ignore
        # Se já cacheado, retorna direto
        if qemu_path in cls._cache:
            return cls._cache[qemu_path]

        # Se recebeu contexto, tenta obter helper via ele
        if context is not None:
            helper = context.get_qemu_helper(qemu_path)  # método que AppContext implementa para retornar QemuHelper
            if helper:
                cls._cache[qemu_path] = helper
                return helper

        # Fallback: não importa diretamente, pode retornar None ou lançar
        return None

    def get_qemu_helper(self, current_qemu_executable: str):
        if current_qemu_executable:
            return self._get_helper(current_qemu_executable)
        return None

    def get_arch_for_binary(self, qemu_path):
        helper = self._get_helper(qemu_path)
        if helper:
            return helper.get_info("architecture")
        return "Invalid or not found"

    def reset(self):
        self.__init__()

    def get(self, key: str, default: Any = None) -> Any:
        return self.all_args.get(key, default)

    def get_config_value(self, key, default=None):
        return self.all_args.get(key, default)

    def set_config_value(self, key, value):
        self.all_args[key] = value

    def parse_dict_to_config(self, new_data: Dict[str, Any]):
        for key, value in new_data.items():
            if key in ['device', 'drive', 'netdev']:
                if key in self.all_args and not isinstance(self.all_args[key], list):
                    self.all_args[key] = [self.all_args[key]]
                if isinstance(value, list):
                    self.all_args[key] = value
                else:
                    if key not in self.all_args:
                        self.all_args[key] = []
                    self.all_args[key].append(value)
            else:
                self.all_args[key] = value

    def to_qemu_args_string(self) -> Tuple[str, str]:
        full_args_list: List[str] = []
        gui_managed_args_list: List[str] = []
        extra_args_only_list: List[str] = []

        qemu_executable = self.all_args.get("qemu_executable")
        if qemu_executable:
            full_args_list.append(qemu_executable)

        ordered_keys = [
            "M", "m", "cpu", "smp", "enable-kvm", "cpu-mitigations", "netdev",
            "usb", "usb-tablet", "usb-mouse", "rtc", "nodefaults", "bios", "boot"
        ]

        for key in ordered_keys:
            if key not in self.all_args:
                continue
            value = self.all_args.get(key)
            arg_str = ""

            if key == "M" and value:
                if isinstance(value, str):
                    arg_str = f"-M {value}"
                elif isinstance(value, dict) and "type" in value:
                    options = [f"{k}={v}" for k, v in value.items() if k != "type"]
                    arg_str = f"-M {value['type']}" + (f",{','.join(options)}" if options else "")
            elif key == "m" and isinstance(value, int) and value > 0:
                arg_str = f"-m {value}"
            elif key == "cpu" and value:
                arg_str = f"-cpu {value}"
            elif key == "smp" and value:
                if isinstance(value, int) and value > 0:
                    arg_str = f"-smp {value}"
                elif isinstance(value, dict):
                    arg_str = f"-smp {','.join([f'{k}={v}' for k, v in value.items()])}"
            elif key == "enable-kvm" and value is True:
                arg_str = "-enable-kvm"
            elif key == "cpu-mitigations":
                if str(value).lower() in ["on", "true"]:
                    arg_str = "-cpu-mitigations on"
                elif str(value).lower() in ["off", "false"]:
                    arg_str = "-cpu-mitigations off"
            elif key == "usb" and value is True:
                arg_str = "-usb"
            elif key == "usb-tablet" and value is True:
                arg_str = "-device usb-tablet"
            elif key == "usb-mouse" and value is True:
                arg_str = "-device usb-mouse"
            elif key == "rtc" and isinstance(value, dict):
                arg_str = f"-rtc {','.join([f'{k}={v}' for k, v in value.items()])}"
            elif key == "nodefaults" and value is True:
                arg_str = "-nodefaults"
            elif key == "bios" and value:
                arg_str = f"-bios {value}"
            elif key == "boot" and value:
                boot_parts = []

                if isinstance(value, dict):
                    if 'order' in value:
                        boot_parts.append(value['order'])
                    if str(value.get('menu')).lower() == 'on':
                        boot_parts.append("menu=on")
                elif isinstance(value, str):
                    boot_parts.append(value)

                if boot_parts:
                    arg_str = f"-boot {','.join(boot_parts)}"

            if arg_str:
                gui_managed_args_list.append(arg_str)

        device_entries = self.all_args.get("device", [])
        if isinstance(device_entries, dict):
            device_entries = [device_entries]
        for device in device_entries:
            if not isinstance(device, dict):
                continue
            device_copy = device.copy()
            interface_name = device_copy.pop('interface', None)
            if not interface_name:
                continue
            other_parts = [f"{k}={v}" for k, v in device_copy.items()]
            full_device_str = interface_name
            if other_parts:
                full_device_str += "," + ",".join(other_parts)
            gui_managed_args_list.append(f"-device {full_device_str}")

        drives = self.all_args.get("drive", [])
        if isinstance(drives, dict):
            drives = [drives]
        for drive in drives:
            if isinstance(drive, dict):
                gui_managed_args_list.append(f"-drive {','.join([f'{k}={v}' for k, v in drive.items()])}")

        floppies = self.all_args.get("floppy", [])
        if isinstance(floppies, dict):
            floppies = [floppies]
        for floppy in floppies:
            if isinstance(floppy, dict):
                unit, fpath = floppy.get("unit"), floppy.get("file")
                if fpath and unit is not None:
                    if unit == 0:
                        gui_managed_args_list.append(f"-fda {fpath}")
                    elif unit == 1:
                        gui_managed_args_list.append(f"-fdb {fpath}")

        for key in ["netdev", "chardev", "monitor", "serial"]:
            items = self.all_args.get(key, [])
            if isinstance(items, dict):
                items = [items]
            for item in items:
                if isinstance(item, dict):
                    gui_managed_args_list.append(f"-{key} {','.join([f'{k}={v}' for k, v in item.items()])}")
                elif isinstance(item, str):
                    gui_managed_args_list.append(f"-{key} {item}")

        for arg_name, arg_value in self.extra_args_list:
            if arg_value is None:
                arg_str = f"-{arg_name}"
            else:
                val = f'"{arg_value}"' if ' ' in str(arg_value) else str(arg_value)
                arg_str = f"-{arg_name} {val}"
            extra_args_only_list.append(arg_str)

        full_args_list.extend(gui_managed_args_list)
        full_args_list.extend(extra_args_only_list)
        full_qemu_command_string = ' \\\n'.join(list(filter(None, full_args_list)))
        extra_args_only_string = ' \\\n'.join(list(filter(None, extra_args_only_list)))
        return full_qemu_command_string, extra_args_only_string

    def update_all_args(self, new_args: Dict[str, Any]):
        for key, value in new_args.items():
            if key in ["drives", "network"] and isinstance(value, list):
                self.all_args[key] = value
            else:
                self.all_args[key] = value

    def update_qemu_config_from_page(self, data_dict: Dict[str, Any]):
        self._is_modified = True

        for arg_name, arg_value in data_dict.items():
            if isinstance(arg_value, list) and arg_name in self.all_args:
                self.all_args[arg_name] = arg_value
            else:
                self.all_args[arg_name] = arg_value

        if "qemu_executable" in data_dict:
            self.current_qemu_executable = data_dict["qemu_executable"]
