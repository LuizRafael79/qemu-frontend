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

from typing import Any, Dict, List, Optional, Tuple

class QemuHelper:
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
            except (json.JSONDecodeError, IOError) as e:
                print(f"Erro ao ler cache QEMU para {self.qemu_path}. Gerando novamente. Erro: {e}")
        
        return self._generate_cache()

    def _run_qemu_command(self, args):
        try:
            result = subprocess.run(
                [self.qemu_path] + args,
                capture_output=True, text=True, timeout=5, check=False
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"Timeout ao executar QEMU para o comando: {' '.join(args)}")
            return ""
        except Exception as e:
            print(f"Erro ao executar QEMU para o comando {' '.join(args)}: {e}")
            return ""

    def _generate_cache(self):
        print(f"Gerando cache de informações para {os.path.basename(self.qemu_path)}...")
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
            print(f"Erro ao salvar cache QEMU em {self.cache_file}: {e}")
        return cache


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

    def get_info(self, key):
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
    def __init__(self):
        self.qemu_config = QemuConfig() 

    def _parse_sub_options(self, value_string):
        """
        Função auxiliar genérica para parsear valores com sub-opções (chave=valor, separadas por vírgula).
        Não faz suposições sobre 'type' ou 'boot_order' aqui, apenas divide.
        """
        sub_options = {}
        parts = value_string.split(',')
        
        for part in parts:
            if '=' in part:
                key, val = part.split('=', 1)
                sub_options[key] = val
            else:
                pass

        return sub_options
    
    def _parse_qemu_key_value_string(self, s: str) -> Dict[str, Any]:
        """
        Helper para parsear strings no formato 'key=value,key2=value2'.
        Trata chaves sem valor como True (flags).
        """
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
    
    def parse_qemu_command_line_to_config(self, cmd_line_str: str = "", arg_name_full: str = "", arg_value_raw: str = ""):
        """
        Analisa uma string de linha de comando QEMU e a converte para o formato
        self.qemu_config.all_args e self.qemu_config.extra_args_list.
        Esta é a lógica do parser que popula a QemuConfig.
        """
        current_all_args = self.qemu_config.all_args.copy()
        if current_all_args is None:
            current_all_args = {}
        print(f"AppContext: Parsing QEMU input string: {cmd_line_str[:100]}...")
        self.qemu_config.reset() 
        cleaned_string = cmd_line_str.replace('\\\n', ' ').strip()

        arg_pattern = re.compile(r'(-[a-zA-Z0-9_]+)(?:\s*((?:[^-\s]|-(?!\w)|"[^"]*")*?))?(?=\s+-[a-zA-Z0-9_]|\s*$)')
        matches = arg_pattern.findall(cleaned_string)

        current_all_args = {}
        current_extra_args_list: List[Tuple[str, Optional[str]]] = []

        for arg_name_full, arg_value_raw in matches:
            arg_name = arg_name_full.lstrip('-')

            if arg_value_raw and arg_value_raw.startswith('"') and arg_value_raw.endswith('"'):
                arg_value_raw = arg_value_raw[1:-1]

            if ',' in arg_value_raw or '=' in arg_value_raw:
                parsed_value = self._parse_qemu_key_value_string(arg_value_raw)
                if parsed_value:
                    if arg_name in ['device', 'drive', 'audiodev', 'netdev', 'chardev', 'monitor', 'qmp', 'serial', 'parallel']:
                        if arg_name not in current_all_args or not isinstance(current_all_args[arg_name], list):
                            current_all_args[arg_name] = []
                        current_all_args[arg_name].append(parsed_value)

                    elif arg_name in ['machine', 'M', 'smp', 'rtc', 'boot']:
                        if arg_name == 'M':
                            current_all_args['machine'] = parsed_value
                        else:
                            if arg_name in current_all_args:
                                if isinstance(current_all_args[arg_name], list):
                                    current_all_args[arg_name].append(parsed_value)
                                else:
                                    current_all_args[arg_name] = [current_all_args[arg_name], parsed_value]
                            else:
                                current_all_args[arg_name] = parsed_value

                        if arg_name == 'smp':
                            if len(parsed_value) == 1 and list(parsed_value.keys())[0] == list(parsed_value.values())[0]:
                                try:
                                    current_all_args['smp'] = int(list(parsed_value.keys())[0])
                                except ValueError:
                                    current_all_args['smp'] = parsed_value
                            else:
                                current_all_args['smp'] = parsed_value
                        elif arg_name == 'boot':
                            if len(parsed_value) == 1 and 'order' in parsed_value:
                                current_all_args['boot'] = parsed_value
                            else:
                                current_all_args['boot'] = parsed_value
                        else:
                            current_all_args[arg_name] = parsed_value

                    else:
                        current_extra_args_list.append((arg_name_full, arg_value_raw))
                else:
                    current_all_args[arg_name] = arg_value_raw

            elif arg_value_raw:
                if arg_name == 'm':
                    try:
                        current_all_args['m'] = int(arg_value_raw)
                    except ValueError:
                        current_all_args['m'] = arg_value_raw
                else:
                    current_all_args[arg_name] = arg_value_raw

            else:
                if arg_name in ['enable-kvm', 'usb', 'nodefaults', 'nographic', 'daemonize', 'no-reboot']:
                    current_all_args[arg_name] = True
                else:
                    current_extra_args_list.append((arg_name_full, None))

        # Após o parse, atualiza a QemuConfig
        self.qemu_config.all_args.update(current_all_args)
        self.extra_args_list = current_extra_args_list

        print("QemuConfig: QemuConfig updated from input string, qemu_config_updated emitted.")


    def parse_qemu_command_line(self, qemu_cmd_line_raw: str):
        cleaned_string = qemu_cmd_line_raw.replace('\\\n', ' ').strip()
        arg_pattern = re.compile(r'(-[a-zA-Z0-9_]+)(?:\s*((?:[^-\s]|-(?!\w)|"[^"]*")*?))?(?=\s+-[a-zA-Z0-9_]|\s*$)')
        matches = arg_pattern.findall(cleaned_string)

        for arg_name_full, arg_value_raw in matches:
            arg_name = arg_name_full.lstrip('-')
            
            if arg_value_raw and arg_value_raw.startswith('"') and arg_value_raw.endswith('"'):
                arg_value_raw = arg_value_raw[1:-1]

            if ',' in arg_value_raw or '=' in arg_value_raw:
                parsed_value = self._parse_sub_options(arg_value_raw)

                if parsed_value:

                    if arg_name in ['device', 'drive', 'audiodev', 'netdev']: 

                        if arg_name not in self.qemu_config.all_args:
                            self.qemu_config.all_args[arg_name] = []
                        self.qemu_config.all_args[arg_name].append(parsed_value)

                    else: 
                        self.qemu_config.all_args[arg_name] = parsed_value

                else: 
                    self.qemu_config.all_args[arg_name] = arg_value_raw

            elif arg_value_raw: 
                self.qemu_config.all_args[arg_name] = arg_value_raw

            else: 
                self.qemu_config.all_args[arg_name] = True

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
            'rtc': {'base': 'localtime', 'clock': 'host'},
            'nodefaults': False,
            'bios': '',
            'boot': {},
            'vga': 'std',
            'display': 'sdl',
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
        print("[DEBUG] get_qemu_helper() chamado com:", current_qemu_executable)
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
        """
        Converte o dicionário all_args e extra_args_list em duas strings:
        1. A linha de comando QEMU completa (incluindo o executável e extra args).
        2. Uma string separada contendo apenas os 'extra args'.

        Returns:
            Tuple[str, str]: (full_qemu_command_string, extra_args_only_string)
        """
        full_args_list: List[str] = []
        gui_managed_args_list: List[str] = [] # Argumentos que são gerenciados pela GUI
        extra_args_only_list: List[str] = [] # Apenas os argumentos extras

        # 1. Executável QEMU (sempre o primeiro)
        qemu_executable = self.all_args.get("qemu_executable")
        if qemu_executable:
            full_args_list.append(qemu_executable)

        # 2. Argumentos gerenciados pela GUI (de self.all_args)
        # É crucial que esta lógica reflita fielmente como sua GUI gerencia os args.
        # Defina 'known_gui_args' para ser a lista de chaves que sua GUI realmente configura.
        # Isso evita que argumentos que a GUI não entende, mas estão em all_args,
        # sejam considerados "gerenciados".
        # Vamos usar uma abordagem mais robusta: iterar sobre all_args e categorizar.
        
        # Ordem de processamento para args gerenciados pela GUI
        # Isso garante que -M, -m, -cpu, -smp etc. venham antes de -device, -drive
        # para uma linha de comando QEMU mais legível.
        ordered_keys = [
            "qemu_executable", "M", "m", "cpu", "smp", "enable-kvm", "cpu-mitigations",
            "usb", "rtc", "nodefaults", "bios", "boot"
            # Adicione outras chaves de configuração principal aqui
        ]
        
        # Processar argumentos em ordem conhecida
        for key in ordered_keys:
            if key not in self.all_args:
                continue
            value = self.all_args[key]

            # Lógica para converter chave-valor para string QEMU
            arg_str: Optional[str] = None
            if key == "M": # Machine type
                if isinstance(value, str):
                    arg_str = f"-M {value}"
                elif isinstance(value, dict) and 'type' in value:
                    machine_type = value['type']
                    options = [f"{k}={v}" if not isinstance(v, bool) else f"{k}={'on' if v else 'off'}" for k, v in value.items() if k != 'type']
                    arg_str = f"-M {machine_type},{','.join(options)}" if options else f"-M {machine_type}"
            elif key == "m": # Memory
                if isinstance(value, int) and value > 0:
                    arg_str = f"-m {value}"
            elif key == "cpu":
                if isinstance(value, str) and value:
                    arg_str = f"-cpu {value}"
            elif key == "smp":
                if isinstance(value, int) and value > 0:
                    arg_str = f"-smp {value}"
                elif isinstance(value, dict):
                    sockets = value.get("sockets", 0)
                    cores = value.get("cores", 0)
                    threads = value.get("threads", 0)
                    smp_parts = []
                    if sockets > 0: smp_parts.append(f"sockets={sockets}")
                    if cores > 0: smp_parts.append(f"cores={cores}")
                    if threads > 0: smp_parts.append(f"threads={threads}")
                    if smp_parts:
                        arg_str = f"-smp {','.join(smp_parts)}"
            elif key == "enable-kvm" and value is True:
                arg_str = "-enable-kvm"
            elif key == "cpu-mitigations":
                if value is True or str(value).lower() == 'on': arg_str = "-cpu-mitigations on"
                elif value is False or str(value).lower() == 'off': arg_str = "-cpu-mitigations off"
            elif key == "usb" and value is True:
                arg_str = "-usb"
            elif key == "rtc":
                if value is True:
                    arg_str = "-rtc base=localtime,clock=host"
                elif isinstance(value, dict):
                    rtc_parts = [f"{k}={v}" for k,v in value.items()]
                    arg_str = f"-rtc {','.join(rtc_parts)}"
            elif key == "nodefaults" and value is True:
                arg_str = "-nodefaults"
            elif key == "bios" and value:
                arg_str = f"-bios {value}"
            elif key == "boot":
                if isinstance(value, str) and value:
                    arg_str = f"-boot {value}"
                elif isinstance(value, dict):
                    boot_str_parts = []
                    if 'order' in value: boot_str_parts.append(value['order'])
                    if 'menu' in value: boot_str_parts.append(f"menu={value['menu']}")
                    if boot_str_parts:
                        arg_str = f"-boot {','.join(boot_str_parts)}"
            
            # Adicione outros argumentos gerenciados pela GUI aqui

            if arg_str:
                gui_managed_args_list.append(arg_str)
                # Remove do all_args temporariamente para não reprocessar como "extra"
                # Isso é mais seguro para a lógica do loop posterior
                # Mas para esta abordagem, não remova, apenas processe explicitamente
        
        # Processar argumentos de lista (device, drive, etc.)
        # Esses geralmente não têm uma ordem fixa em relação aos outros,
        # mas QEMU os trata como múltiplos argumentos do mesmo tipo.
        list_keys = ["device", "drive", "netdev", "chardev", "monitor", "serial"]
        for key in list_keys:
            if key in self.all_args and isinstance(self.all_args[key], list):
                for item_value in self.all_args[key]:
                    # Adapte a formatação do item conforme sua estrutura.
                    # Ex: para drive_data = {'file': 'path', 'if': 'ide'}
                    item_str = ""
                    if isinstance(item_value, dict):
                        # Lógica para formatar dicionários de drives/devices
                        parts = []
                        if 'id' in item_value: parts.append(f"id={item_value['id']}")
                        if 'file' in item_value: parts.append(f"file={item_value['file']}")
                        if 'if' in item_value: parts.append(f"if={item_value['if']}")
                        # Adicione outras propriedades comuns para devices/drives
                        # Ex: 'media', 'format', 'bus', 'unit'
                        for k, v in item_value.items():
                            if k not in ['id', 'file', 'if', 'media', 'format', 'bus', 'unit']:
                                parts.append(f"{k}={v}")
                        item_str = ','.join(parts)
                        # Se for um device simples como "VGA"
                        if not parts and isinstance(item_value, str):
                             item_str = item_value
                    elif isinstance(item_value, str):
                        item_str = item_value
                    
                    if item_str:
                        gui_managed_args_list.append(f"-{key} {item_str}")
            # Se for uma string única (não lista), isso seria um caso de edge ou legacy.
            elif key in self.all_args and isinstance(self.all_args[key], str):
                 gui_managed_args_list.append(f"-{key} {self.all_args[key]}")


        # 3. Adicionar argumentos "extras" (extra_args_list)
        # Estes são os argumentos que o AppContext não conseguiu mapear para campos da GUI
        # e foram armazenados separadamente.
        for arg_name, arg_value in self.extra_args_list:
            formatted_value = ''
            if arg_value is not None: # Pode ser uma flag sem valor
                formatted_value = f'"{arg_value}"' if ' ' in str(arg_value) else str(arg_value)
            
            extra_arg_str = f"-{arg_name} {formatted_value}".strip() # strip para flags sem valor
            
            extra_args_only_list.append(extra_arg_str) # Para a string separada de extras
            full_args_list.append(extra_arg_str) # Adiciona à lista completa também

        # Concatenar todos os argumentos para a linha de comando completa
        full_qemu_command_string = ' \\\n'.join(filter(None, full_args_list + gui_managed_args_list))
        extra_args_only_string = ' \\\n'.join(filter(None, extra_args_only_list))

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
        print("[DEBUG] update_qemu_config_from_page() chamado")
        print("[DEBUG] qemu_executable =", data_dict.get("qemu_executable"))
        self._is_modified = True

        for arg_name, arg_value in data_dict.items():
            self.all_args[arg_name] = arg_value

        # Atualiza QemuHelper (se aplicável)
        if "qemu_executable" in data_dict:
            self.current_qemu_executable = data_dict["qemu_executable"]
      