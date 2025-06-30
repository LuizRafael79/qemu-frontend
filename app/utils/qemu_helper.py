# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

import os
import json
import hashlib
import subprocess
import re
import shlex

from typing import Any, Dict, List, Optional, Tuple, Callable

class QemuHelper:
    data: Dict[str, Any]
    def __init__(self, qemu_path):

        if not self._is_valid_qemu_binary(qemu_path):
            raise FileNotFoundError(f"Arquivo selecionado não é um binário QEMU válido: {qemu_path}")
            
        self.qemu_path = qemu_path
        self.cache_dir = os.path.expanduser("~/.cache/qemu_frontend")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        qemu_hash = hashlib.sha256(self.qemu_path.encode()).hexdigest()
        self.cache_file = os.path.join(self.cache_dir, f"{qemu_hash}.json")
        
        self.data = self._load_or_generate_cache()

    @staticmethod
    def _is_valid_qemu_binary(path: str) -> bool:
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            return False
        try:
            result = subprocess.run(
                [path, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3,
                check=False,
                text=True
            )
            return "qemu" in result.stdout.lower()
        except Exception:
            return False

    def _load_or_generate_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):        
                # Se o arquivo existe mas é inválido, gera um novo.
                return self._generate_cache()
        else:
            # Se o arquivo não existe, gera um novo.
            return self._generate_cache()

    def _run_qemu_command(self, args):
        try:
            result = subprocess.run(
                [self.qemu_path] + args,
                capture_output=True, text=True, timeout=5, check=False
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            return ""

    def _generate_cache(self) -> Dict[str, Any]:
        version_output = self._run_qemu_command(["--version"])
        architecture = self._extract_architecture(version_output)
        qemu_path = os.path.abspath(self.qemu_path)
        cache = {
            "version": version_output,
            "architecture": architecture,
            "cpu_help": self._run_qemu_command(["-cpu", "help"]),
            "machine_help": self._run_qemu_command(["-machine", "help"]),
            "qemu_path": qemu_path
        }
        try:
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except IOError as e:
            return cache
        else:
            return {} 

    def _extract_architecture(self, version_string):
        match = re.search(r'featuring qemu-([a-zA-Z0-9]+)@([^-\s]+)', version_string)
        if match:
            feature, git_hash = match.groups()
            return f"Official Qemu {feature} - GIT HEAD -> @{git_hash}-"

        # 2. tenta extrair do nome do binário
        match = re.search(r'qemu-system-([a-zA-Z0-9_]+)', os.path.basename(self.qemu_path))
        if match:
            return match.group(1)

        # 3. fallback padrão
        match = re.search(r'\(qemu-([a-zA-Z0-9_-]+)', version_string)
        if match:
            return match.group(1).replace('_', '-')

        return "Unknown"

    def get_info(self, key) -> Any:
        return self.data.get(key, "") 

    def get_cpu_list(self):
        cpu_output = self.get_info("cpu_help")
        cpus = []
        parsing = False
        for line in cpu_output.splitlines():
            line = line.strip()
            if line.startswith("Available CPUs:"):
                parsing = True
                continue
            if parsing:
                if not line:
                    break
                parts = line.split()
                if parts:
                    cpus.append(parts[0])     
        if self.get_info("architecture") in ["x86_64", "i386"]:
             if "host" not in cpus:
                cpus.insert(0, "host")

        return cpus if cpus else ["default"]

    def get_machine_list(self):
        machine_output = self.get_info("machine_help")
        machines = []
        for line in machine_output.splitlines():
            line = line.strip()
            if line and not line.startswith("Supported machines are:"):
                parts = line.split()
                if parts and parts[0] not in machines:
                    machines.append(parts[0])
        return machines if machines else ["pc", "q35", "isapc"]    
class QemuArgumentParser:
    def __init__(self, config_provider: Callable[[], "QemuConfig"]):
        self.qemu_config: QemuConfig = config_provider()

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
            self.qemu_config.reset()
            cleaned_str = cmd_line_str.replace('\\\n', ' ').replace('\\\r\n', ' ')
            
            try:
                args = shlex.split(cleaned_str)
            except ValueError as e:
                print(f"[WARN] Erro ao fazer shlex.split: {e}")
                import traceback; traceback.print_exc()
                return

            if args and 'qemu-system-' in args[0]:
                self.qemu_config.all_args['qemu_executable'] = args.pop(0)

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

            self.qemu_config.all_args.update(current_all_args)
            self.qemu_config.extra_args_list = current_extra_args_list

        except Exception as e:
            print(f"[FATAL] Erro geral no parse_qemu_command_line_to_config: {e}")
            import traceback; traceback.print_exc()
class QemuConfig:
    _cache = {}
    current_qemu_executable: str = ""
    def __init__(self):
        # Dicionário para todos os argumentos QEMU
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
            'drive': [],
            'floppy': [],
        }
        # Argumentos que o GUI do app NÃO suporta
        self.extra_args_list: List[Tuple[str, Optional[str]]] = []

    @classmethod
    def _get_helper(cls, qemu_path: str) -> 'QemuHelper':
        if qemu_path not in cls._cache:
            cls._cache[qemu_path] = QemuHelper(qemu_path)
        return cls._cache[qemu_path]    
    
    def get_qemu_helper(self, current_qemu_executable: str):
        if current_qemu_executable:
            helper = self._get_helper(current_qemu_executable)
            return helper
        return None
    
    def get_arch_for_binary(self, qemu_path):
        helper = self._get_helper(qemu_path)
        if helper:
            return helper.get_info("architecture")
        return "Invalid or not found"

    def reset(self):
        """Redefine a configuração para seus valores padrão."""
        self.__init__()

    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor da configuração, com um valor padrão opcional."""
        return self.all_args.get(key, default)
        
    def get_config_value(self, key, default=None): # <--- ESTE MÉTODO PERTENCE A QemuConfig
        """
        Retorna o valor de uma chave específica da configuração.
        Por exemplo, config.get_config_value('qemu_executable')
        """
        return self.all_args.get(key, default)

    def set_config_value(self, key, value): # <--- ESTE MÉTODO PERTENCE A QemuConfig
        """
        Define o valor de uma chave específica na configuração.
        Isso é útil para atualizar valores diretamente na QemuConfig.
        """
        self.all_args[key] = value

    def parse_dict_to_config(self, new_data: Dict[str, Any]):
        """
        Mescla um novo dicionário de dados na configuração atual.
        Isso é usado quando as páginas da GUI enviam suas configurações.
        """
        for key, value in new_data.items():
            # Aqui você decide como lidar com a mesclagem.
            # Para argumentos de lista (device, drive), você pode querer concatenar ou substituir.
            # Por simplicidade, vamos substituir aqui. Se precisar mesclar, adicione lógica.
            if key in ['device', 'drive', 'netdev']:
                # Assegura que se o valor já existir e não for uma lista, ele se torna uma lista.
                if key in self.all_args and not isinstance(self.all_args[key], list):
                    self.all_args[key] = [self.all_args[key]]
                if isinstance(value, list):
                    # Se new_data tem uma lista, substitua ou adicione. Aqui, vamos substituir para UI.
                    self.all_args[key] = value
                else: # Se for um item único, adicione a uma lista existente ou nova
                    if key not in self.all_args: self.all_args[key] = []
                    self.all_args[key].append(value)
            else:
                self.all_args[key] = value
        
        # Note: Este método não limpa extra_args_list. Isso é feito no parse_qemu_command_line_to_config
        # ou quando você intencionalmente define a config a partir de uma fonte GUI.

    def to_qemu_args_string(self) -> Tuple[str, str]:
        full_args_list: List[str] = []
        gui_managed_args_list: List[str] = []
        extra_args_only_list: List[str] = []

        qemu_executable = self.all_args.get("qemu_executable")
        if qemu_executable:
            full_args_list.append(qemu_executable)

        ordered_keys = [
            "M", "m", "cpu", "smp", "enable-kvm", "cpu-mitigations",
            "usb", "tablet-usb", "mouse-usb", "rtc", "nodefaults", "bios", "boot"
        ]

        for key in ordered_keys:
            if key not in self.all_args: continue
            value = self.all_args.get(key)
            arg_str = ""
            
            if key == "M" and value:
                if isinstance(value, str): arg_str = f"-M {value}"
                elif isinstance(value, dict) and "type" in value:
                    options = [f"{k}={v}" for k, v in value.items() if k != "type"]
                    arg_str = f"-M {value['type']}" + (f",{','.join(options)}" if options else "")
            elif key == "m" and isinstance(value, int) and value > 0: arg_str = f"-m {value}"
            elif key == "cpu" and value: arg_str = f"-cpu {value}"
            elif key == "smp" and value:
                if isinstance(value, int) and value > 0: arg_str = f"-smp {value}"
                elif isinstance(value, dict): arg_str = f"-smp {','.join([f'{k}={v}' for k, v in value.items()])}"
            elif key == "enable-kvm" and value is True: arg_str = "-enable-kvm"
            elif key == "cpu-mitigations":
                if str(value).lower() in ["on", "true"]: arg_str = "-cpu-mitigations on"
                elif str(value).lower() in ["off", "false"]: arg_str = "-cpu-mitigations off"
            elif key == "usb" and value is True:
                arg_str = "-usb"
            elif key == "usb-tablet" and value is True:
                arg_str = "-device usb-tablet" # Gera o argumento -device correto
            elif key == "usb-mouse" and value is True:
                arg_str = "-device usb-mouse" # Gera o argumento -device correto
            elif key == "rtc" and isinstance(value, dict): arg_str = f"-rtc {','.join([f'{k}={v}' for k, v in value.items()])}"
            elif key == "nodefaults" and value is True: arg_str = "-nodefaults"
            elif key == "bios" and value: arg_str = f"-bios {value}"
            elif key == "boot" and value:
                boot_parts = []
                
                # Primeiro, lida com o dicionário que o parser cria
                if isinstance(value, dict):
                    # Adiciona a ordem de boot, se existir
                    if 'order' in value:
                        boot_parts.append(value['order'])
                    
                    # Adiciona menu=on APENAS se estiver explicitamente 'on'
                    if str(value.get('menu')).lower() == 'on':
                        boot_parts.append("menu=on")

                # Lida com o caso de ser uma string simples
                elif isinstance(value, str):
                    boot_parts.append(value)

                # Monta a string final apenas se houver partes a serem unidas
                if boot_parts:
                    arg_str = f"-boot {','.join(boot_parts)}"
            
            if arg_str: 
                gui_managed_args_list.append(arg_str)

        # A lógica para os outros devices, drives e floppies permanece a mesma que já corrigimos.
        device_entries = self.all_args.get("device", [])
        if isinstance(device_entries, dict): device_entries = [device_entries]
        for device in device_entries:
            if not isinstance(device, dict): continue
            device_copy = device.copy()
            interface_name = device_copy.pop('interface', None)
            if not interface_name: continue
            other_parts = [f"{k}={v}" for k, v in device_copy.items()]
            full_device_str = interface_name
            if other_parts:
                full_device_str += "," + ",".join(other_parts)
            gui_managed_args_list.append(f"-device {full_device_str}")

        drives = self.all_args.get("drive", [])
        if isinstance(drives, dict): drives = [drives]
        for drive in drives:
            if isinstance(drive, dict): gui_managed_args_list.append(f"-drive {','.join([f'{k}={v}' for k, v in drive.items()])}")

        floppies = self.all_args.get("floppy", [])
        if isinstance(floppies, dict): floppies = [floppies]
        for floppy in floppies:
            if isinstance(floppy, dict):
                unit, fpath = floppy.get("unit"), floppy.get("file")
                if fpath and unit is not None:
                    if unit == 0: gui_managed_args_list.append(f"-fda {fpath}")
                    elif unit == 1: gui_managed_args_list.append(f"-fdb {fpath}")

        for key in ["netdev", "chardev", "monitor", "serial"]:
            items = self.all_args.get(key, [])
            if isinstance(items, dict): items = [items]
            for item in items:
                if isinstance(item, dict): gui_managed_args_list.append(f"-{key} {','.join([f'{k}={v}' for k, v in item.items()])}")
                elif isinstance(item, str): gui_managed_args_list.append(f"-{key} {item}")
        
        for arg_name, arg_value in self.extra_args_list:
            if arg_value is None: arg_str = f"-{arg_name}"
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
        """
        Atualiza o dicionário de argumentos QEMU com novos valores.
        Se uma chave já existe, seu valor é sobrescrito.
        Se a chave 'drives' ou 'network' for atualizada, ela substitui a lista inteira.
        Para tipos complexos como 'drives', você pode querer uma lógica de mesclagem mais inteligente
        no futuro (ex: atualizar drives por ID em vez de substituir a lista toda).
        Por enquanto, uma simples substituição para listas e atualização para outros tipos é o suficiente.
        """
        for key, value in new_args.items():
            if key in ["drives", "network"] and isinstance(value, list):
                self.all_args[key] = value
            else:
                self.all_args[key] = value

    def update_qemu_config_from_page(self, data_dict: Dict[str, Any]):
        self._is_modified = True

        for arg_name, arg_value in data_dict.items():
            if isinstance(arg_value, list) and arg_name in self.all_args:
                # Mescla listas ao invés de sobrescrever para evitar perder dados
                # Pode ser ajustado conforme a lógica exata de merge desejada
                existing_list = self.all_args.get(arg_name, [])
                # Opcional: evitar duplicatas, etc
                self.all_args[arg_name] = arg_value
            else:
                self.all_args[arg_name] = arg_value

        if "qemu_executable" in data_dict:
            self.current_qemu_executable = data_dict["qemu_executable"]
      