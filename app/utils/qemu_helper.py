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
        cache = {
            "version": self._run_qemu_command(["--version"]),
            "architecture": self._extract_architecture(),
            "cpu_help": self._run_qemu_command(["-cpu", "help"]),
            "machine_help": self._run_qemu_command(["-machine", "help"])
        }
        try:
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except IOError as e:
            print(f"Erro ao salvar cache QEMU em {self.cache_file}: {e}")
        return cache

    def _extract_architecture(self):
        """ Extrai a arquitetura do nome do arquivo ou da saída de --version. """
        # 1. Tenta extrair do nome do arquivo (mais confiável)
        match = re.search(r'qemu-system-([a-zA-Z0-9_]+)', os.path.basename(self.qemu_path))
        if match:
            return match.group(1)
            
        # 2. Se falhar, tenta extrair da saída da versão
        version_string = self.get_version()
        match = re.search(r'\(qemu-([a-zA-Z0-9_-]+)', version_string)
        if match:
            return match.group(1).replace('_', '-') # ex: qemu-x86_64 -> x86_64
            
        return "Unknown"

    def get_info(self, key):
        return self.data.get(key, "")

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
