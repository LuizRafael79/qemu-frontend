# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
from __future__ import annotations

import os
import json
import hashlib
import subprocess
import re
from typing import Any, Dict

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
        self._context = None  # Será setado por set_app_context()

    def set_app_context(self, context):
        self._context = context

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
                return self._generate_cache()
        else:
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
        except Exception:
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
            "network_help": self._run_qemu_command(["-netdev", "help"]),
            "device_help": self._run_qemu_command(["-device", "help"]),
            "qemu_path": qemu_path
        }
        try:
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except IOError:
            pass
        return cache

    def _extract_architecture(self, version_string):
        match = re.search(r'featuring qemu-([a-zA-Z0-9]+)@([^-\s]+)', version_string)
        if match:
            feature, git_hash = match.groups()
            return f"Official Qemu {feature} - GIT HEAD -> @{git_hash}-"

        match = re.search(r'qemu-system-([a-zA-Z0-9_]+)', os.path.basename(self.qemu_path))
        if match:
            return match.group(1)

        match = re.search(r'\(qemu-([a-zA-Z0-9_-]+)', version_string)
        if match:
            return match.group(1).replace('_', '-')

        return "Unknown"

    def get_info(self, key: str) -> Any:
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

    def get_network_netdev(self):
        network_output = self.get_info("network_help")
        netdevs = []
        for line in network_output.splitlines():
            line = line.strip()
            if line and not line.startswith("Available netdev backend types:"):
                parts = line.split()
                if parts and parts[0] not in netdevs:
                    netdevs.append(parts[0])
        return netdevs if netdevs else ["user", "tap", "bridge", "virtio-net-pci"]

    def get_network_devices(self):
        device_output = self.get_info("device_help")
        net_devices = []

        for line in device_output.splitlines():
            line = line.strip()
            if not line or line.startswith("Name") or line.startswith("---"):
                continue
            parts = line.split()
            if len(parts) >= 2 and ("Ethernet" in line or "network" in line.lower()):
                net_devices.append(parts[0])
            elif parts[0] in ["e1000", "e1000e", "virtio-net-pci", "rtl8139", "vmxnet3", "ne2k_pci"]:
                net_devices.append(parts[0])

        if not net_devices:
            net_devices = ["virtio-net-pci", "e1000", "rtl8139", "vmxnet3", "ne2k_pci"]

        return sorted(set(net_devices))

    # Exemplo de método para acessar qemu_config via contexto
    def get_current_config(self):
        if self._context is not None:
            return self._context.qemu_config
        else:
            raise RuntimeError("AppContext não configurado em QemuHelper")

    # Exemplo para acessar o parser pelo contexto
    def get_parser(self):
        if self._context is not None:
            return self._context.qemu_argument_parser
        else:
            raise RuntimeError("AppContext não configurado em QemuHelper")
