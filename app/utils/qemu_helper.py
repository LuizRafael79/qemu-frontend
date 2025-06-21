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

class QemuHelper:
    """
    Classe auxiliar que executa comandos de um binário QEMU específico
    e armazena os resultados em um arquivo de cache individual.
    """
    def __init__(self, qemu_path):
        if not os.path.exists(qemu_path) or not os.access(qemu_path, os.X_OK):
            raise FileNotFoundError(f"Binário QEMU não encontrado ou não executável: {qemu_path}")
            
        self.qemu_path = qemu_path
        self.cache_dir = os.path.expanduser("~/.cache/qemu_frontend")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # O hash garante um cache único por binário
        qemu_hash = hashlib.sha256(self.qemu_path.encode()).hexdigest()
        self.cache_file = os.path.join(self.cache_dir, f"{qemu_hash}.json")
        
        self.data = self._load_or_generate_cache()

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
            # Usamos um timeout curto para evitar que a UI congele se o QEMU travar
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
        cache = {
            "version": version_output,
            "architecture": architecture,
            "cpu_help": self._run_qemu_command(["-cpu", "help"]),
            "machine_help": self._run_qemu_command(["-machine", "help"])
        }
        try:
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except IOError as e:
            print(f"Erro ao salvar cache QEMU em {self.cache_file}: {e}")
        return cache


    def _extract_architecture(self, version_string):
        # 1. tenta pela linha featuring qemu-...
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
        """ Analisa a saída de 'cpu_help' e retorna uma lista de nomes de CPU. """
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
        
        # Adiciona 'host' se a arquitetura for a mesma do sistema
        # Esta é uma simplificação; uma verificação real pode ser mais complexa
        if self.get_info("architecture") in ["x86_64", "i386"]:
             if "host" not in cpus:
                cpus.insert(0, "host")

        return cpus if cpus else ["default"]

    def get_machine_list(self):
        """ Analisa a saída de 'machine_help' e retorna uma lista de tipos de máquina. """
        machine_output = self.get_info("machine_help")
        machines = []
        for line in machine_output.splitlines():
            line = line.strip()
            if line and not line.startswith("Supported machines are:"):
                parts = line.split()
                if parts and parts[0] not in machines:
                    machines.append(parts[0])
        return machines if machines else ["pc", "q35", "isapc"]

class QemuInfoCache:
    """
    Gerenciador que mantém uma coleção de instâncias QemuHelper
    para evitar a recriação e reprocessamento de binários já vistos.
    """
    def __init__(self):
        self._cache = {}  # Mapeia: "caminho/do/binario" -> instância QemuHelper

    def _get_helper(self, binary_path):
        if binary_path not in self._cache:
            try:
                self._cache[binary_path] = QemuHelper(binary_path)
            except FileNotFoundError as e:
                print(e)
                return None
        return self._cache[binary_path]

    def get_arch_for_binary(self, binary_path):
        helper = self._get_helper(binary_path)
        if helper:
            return helper.get_info("architecture")
        return "Invalid or not found"    
