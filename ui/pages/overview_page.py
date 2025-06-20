from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QHBoxLayout, QTextEdit, QTabWidget, QFileDialog
)
from PyQt5.QtCore import pyqtSignal
import os
import re
import subprocess
import shutil
# Importe as novas classes do novo arquivo
from app.utils.qemu_helper import QemuHelper, QemuInfoCache
from app.context.app_context import AppContext

class OverviewPage(QWidget):
    overview_config_changed = pyqtSignal()
    qemu_binary_changed = pyqtSignal(str)

    def __init__(self, app_context):
        super().__init__()
        self.app_context = AppContext()
        # Use a nova classe de cache
        self.qemu_info_cache = QemuInfoCache()

        self.setup_ui()
        self.populate_qemu_binaries()
        self.bind_signals()
        self.load_config_to_ui()

    def setup_ui(self):
        # ... seu código de setup_ui permanece o mesmo ...
        # (código omitido por brevidade, é igual ao seu original)
        main_layout = QVBoxLayout(self)
        self.title_label = QLabel("Virtual Machine Overview")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(self.title_label)
        qemu_group = QGroupBox("QEMU Executable")
        qemu_layout = QFormLayout()
        self.qemu_combo = QComboBox()
        qemu_layout.addRow("Available QEMU:", self.qemu_combo)
        qemu_group.setLayout(qemu_layout)
        main_layout.addWidget(qemu_group)
        custom_group = QGroupBox("Custom Executable")
        custom_layout = QHBoxLayout()
        self.custom_path = QLineEdit()
        self.btn_browse = QPushButton("Browse")
        self.btn_clear = QPushButton("Clear")
        custom_layout.addWidget(self.custom_path)
        custom_layout.addWidget(self.btn_browse)
        custom_layout.addWidget(self.btn_clear)
        custom_group.setLayout(custom_layout)
        main_layout.addWidget(custom_group)
        self.arch_label = QLabel("Architecture:")
        main_layout.addWidget(self.arch_label)
        self.btn_launch = QPushButton("Launch QEMU")
        main_layout.addWidget(self.btn_launch)
        self.output_tabs = QTabWidget()
        self.qemuargs_output = QTextEdit()
        self.qemuargs_output.setReadOnly(False)
        self.qemuextraargs_output = QTextEdit()
        self.qemuextraargs_output.setReadOnly(False)
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.mesa_output = QTextEdit()
        self.mesa_output.setReadOnly(True)
        self.output_tabs.addTab(self.qemuargs_output, "Qemu Args")
        self.output_tabs.addTab(self.qemuextraargs_output, "Extra Args")
        self.output_tabs.addTab(self.console_output, "Console Output")
        self.output_tabs.addTab(self.mesa_output, "mesaPT / glidePT Logs")
        main_layout.addWidget(self.output_tabs)
        self.fps_label = QLabel("FPS: --")
        self.qemuargs_output.textChanged.connect(self._on_args_changed)


    def bind_signals(self):
        # A lógica agora é mais simples. Cada sinal apenas chama o handler apropriado.
        self.qemu_combo.currentIndexChanged.connect(self.on_qemu_combo_changed)
        self.btn_browse.clicked.connect(self.on_browse_clicked)
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        self.custom_path.textChanged.connect(self.on_custom_path_changed)
        self.btn_launch.clicked.connect(self.on_launch_clicked)
        self.app_context.qemu_args_pasted.connect(self.update_qemu_args)


    def populate_qemu_binaries(self):
        found = []
        # ... seu código aqui é bom, sem alterações necessárias ...
        for path in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.startswith("qemu-system-"):
                        full_path = shutil.which(f)
                        if full_path and full_path not in found:
                            found.append(full_path)
        found = sorted(found)
        self.app_context.qemu_binaries = found
        
        self.qemu_combo.blockSignals(True)
        self.qemu_combo.clear()
        self.qemu_combo.addItems([os.path.basename(p) for p in found])
        self.qemu_combo.blockSignals(False)

    def load_config_to_ui(self):
        """ Carrega a configuração inicial do app_context para a UI. """
        cfg = self.app_context.config
        if not cfg:
            return

        # Bloqueia sinais para evitar disparos em cascata durante o carregamento
        self.qemu_combo.blockSignals(True)
        self.custom_path.blockSignals(True)
        self.qemuargs_output.blockSignals(True)
        self.qemuextraargs_output.blockSignals(True)

        try:
            custom_exec = cfg.get("custom_executable", "")
            self.custom_path.setText(custom_exec)

            # Se houver um executável customizado, ele tem prioridade
            if custom_exec:
                # Desativa o combo para indicar que o caminho customizado está em uso
                self.qemu_combo.setEnabled(False)
                self._update_active_binary(custom_exec)
            else:
                self.qemu_combo.setEnabled(True)
                qemu_exec_basename = cfg.get("qemu_executable", "")
                
                # Encontra o índice correspondente no ComboBox
                items = [self.qemu_combo.itemText(i) for i in range(self.qemu_combo.count())]
                if qemu_exec_basename and qemu_exec_basename in items:
                    self.qemu_combo.setCurrentText(qemu_exec_basename)
                elif self.qemu_combo.count() > 0:
                    self.qemu_combo.setCurrentIndex(0)

                # Atualiza com base na seleção do combo
                if self.qemu_combo.currentIndex() >= 0:
                    binary_path = self.app_context.qemu_binaries[self.qemu_combo.currentIndex()]
                    self._update_active_binary(binary_path)
                else:
                    self._update_active_binary(None) # Nenhum binário selecionado

            # Atualiza os campos de texto com os argumentos do config
            qemu_args = cfg.get("qemu_args", "")
            extra_args = cfg.get("extra_args", "")

            self.qemuargs_output.setPlainText(qemu_args)
            self.qemuextraargs_output.setPlainText(extra_args)

        finally:
            self.qemu_combo.blockSignals(False)
            self.custom_path.blockSignals(False)
            self.qemuargs_output.blockSignals(False)
            self.qemuextraargs_output.blockSignals(False)


    def _update_active_binary(self, binary_path):
        """
        Função CENTRALIZADA. Toda mudança de binário QEMU passa por aqui.
        Isso evita chamadas em cascata e recursão.
        """
        if not binary_path:
            self.arch_label.setText("Architecture: No QEMU binary selected")
            self.app_context.update_config({"architecture": self.arch_label.text()})
            self.qemu_binary_changed.emit("")
            self.overview_config_changed.emit()
            return
            
        # Usa nosso novo cache para obter a arquitetura
        arch_text = self.qemu_info_cache.get_arch_for_binary(binary_path)
        self.arch_label.setText(f"Architecture: {arch_text}")

        # Atualiza o contexto da aplicação
        self.app_context.update_config({
            "architecture": self.arch_label.text(),
            "qemu_executable": os.path.basename(binary_path),
            "custom_executable": self.custom_path.text().strip()
        })
        
        # Emite os sinais para outras partes da aplicação saberem da mudança
        self.qemu_binary_changed.emit(binary_path)
        self.overview_config_changed.emit()

    # --- Handlers de Sinais (agora muito mais simples) ---

    def on_qemu_combo_changed(self, index):
        if 0 <= index < len(self.app_context.qemu_binaries):
            bin_path = self.app_context.qemu_binaries[index]
            self._update_active_binary(bin_path)

    def on_custom_path_changed(self, text):
        text = text.strip()
        if text:
            # Se um caminho customizado é digitado, ele se torna o ativo.
            # Bloqueia o combo para deixar claro qual está em uso.
            self.qemu_combo.setEnabled(False)
            self._update_active_binary(text)
        else:
            # Se o caminho customizado é limpo, o combo volta a ser a fonte.
            self.qemu_combo.setEnabled(True)
            self.on_qemu_combo_changed(self.qemu_combo.currentIndex())

    def on_browse_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select QEMU Executable")
        if path:
            # Apenas define o texto. O `on_custom_path_changed` fará o resto.
            self.custom_path.setText(path)

    def on_clear_clicked(self):
        # Apenas limpa o texto. O `on_custom_path_changed` será acionado com texto vazio.
        self.custom_path.clear()

    # ... on_launch_clicked, update_qemu_args, etc. permanecem os mesmos ...
    def on_launch_clicked(self):
        # ... (código igual ao seu original)
        bin_path = self.custom_path.text().strip()
        if not bin_path and self.qemu_combo.currentIndex() >= 0:
            bin_path = self.app_context.qemu_binaries[self.qemu_combo.currentIndex()]
        if not bin_path:
            self.console_output.append("No QEMU binary selected.")
            return
        self.console_output.append(f"Launching: {bin_path}")
        try:
            proc = subprocess.Popen([bin_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = proc.communicate(timeout=10)
            self.console_output.append(stdout)
            self.console_output.append(stderr)
        except Exception as e:
            self.console_output.append(f"Failed to launch QEMU: {e}")

    def update_qemu_args(self, args_list):
        if not args_list:
            args_list = []

        # Formata os argumentos principais (qemu_args)
        formatted_command = " ".join(args_list)
        pretty_command = re.sub(r' -', ' \\\n-', formatted_command)

        self.qemuargs_output.blockSignals(True)
        self.qemuargs_output.setPlainText(pretty_command)
        self.qemuargs_output.blockSignals(False)

        # Trata os extra_args salvos no config
        extra_args = self.app_context.config.get("extra_args", [])
        if extra_args:
            extra_str = " \\\n".join(extra_args)
        else:
            extra_str = ""

        self.qemuextraargs_output.blockSignals(True)
        self.qemuextraargs_output.setPlainText(extra_str)
        self.qemuextraargs_output.blockSignals(False)

    def _on_args_changed(self):
        # ... (código igual ao seu original)
        raw = self.qemuargs_output.toPlainText()
        if not any(kw in raw for kw in ("-drive", "-device", "-cpu", "-m", "-smp")):
            return
        try:
            import shlex
            cmd_clean = raw.replace("\\\n", " ").replace("\n", " ")
            args = shlex.split(cmd_clean)
        except Exception as e:
            print(f"Erro ao fazer parse da linha de comando: {e}")
            return
        self.app_context.qemu_args_pasted.emit(args)
