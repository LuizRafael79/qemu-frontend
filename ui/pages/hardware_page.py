# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QHBoxLayout,
    QPushButton, QSpinBox, QGroupBox, QMessageBox, QLineEdit, QFileDialog
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIntValidator 
import multiprocessing
from typing import Dict, Any
from app.context.app_context import AppContext

CPU_CONFIG = "cpu"
MACHINE_TYPE_CONFIG = "machine"
MEMORY_MB_CONFIG = "m"
KVM_ACCEL_CONFIG = "enable-kvm"
DEFAULT_KVM = False
CPU_MITIGATIONS_CONFIG = "cpu-mitigations"

DEFAULT_CPU = "default"
DEFAULT_MACHINE_QEMU_ARG = "pc" 
DEFAULT_MEMORY_QEMU_ARG = 1024 
HOST_CPU = "host"

ENABLE_USB = "usb"
ENABLE_RTC = "rtc"
DISABLE_NODEFAULTS = "nodefaults"
BIOS_PATH = "bios" 
BOOT_ORDER = "boot"

class HardwarePage(QWidget):
    hardware_config_changed = pyqtSignal() 
    def __init__(self, app_context: AppContext):
        print("[INIT] HardwarePage instanciada")
        super().__init__()
        self.app_context = app_context
        self.qemu_config = self.app_context.qemu_config
        self.qemu_argument_parser = self.app_context.qemu_argument_parser
        self._setup_ui

        self.host_cpu_count = multiprocessing.cpu_count()
        self._loading_config = False # Flag para quando a UI está sendo carregada pela config
        self._updating_cpu_ui = False # Flag para evitar loops na lógica de CPU/Topology

        self._setup_ui()
        self.bind_signals()

        # Conecta o sinal hardware_config_changed para o método de atualização do AppContext
        # Note que a conexão é para _on_hardware_config_changed (nesta página)
        # que por sua vez CHAMA o AppContext.update_qemu_config_from_page
        self.hardware_config_changed.connect(self._on_hardware_config_changed)

        # Conecta ao sinal do AppContext que avisa que a QemuConfig foi atualizada.
        # Este é o principal ponto de entrada para ATUALIZAR a UI da página.
        self.app_context.qemu_config_updated.connect(self.load_from_qemu_config)

    # === UI Setup ===

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel("Virtual Machine Hardware")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        self._setup_cpu_widgets(layout)
        self._setup_advanced_cpu_widgets(layout)
        self._setup_machine_and_memory_widgets(layout)
        self._setup_misc_widgets(layout)

        self.setLayout(layout)

    def _setup_cpu_widgets(self, parent_layout: QVBoxLayout):
        cpus_group = QGroupBox("CPUs")
        cpus_layout = QVBoxLayout()

        self.logical_host_label = QLabel(f"Logical Host CPUs: {self.host_cpu_count}")
        cpus_layout.addWidget(self.logical_host_label)

        hbox_vcpu = QHBoxLayout()
        hbox_vcpu.addWidget(QLabel("vCPU Allocation:"))
        self.smp_cpu_spinbox = QSpinBox()
        self.smp_cpu_spinbox.setRange(1, 256)
        self.smp_cpu_spinbox.setValue(4) # Valor inicial padrão
        hbox_vcpu.addWidget(self.smp_cpu_spinbox)
        cpus_layout.addLayout(hbox_vcpu)

        cpus_group.setLayout(cpus_layout)
        parent_layout.addWidget(cpus_group)

    def _setup_advanced_cpu_widgets(self, parent_layout: QVBoxLayout):
        adv_group = QGroupBox("Advanced CPU Config")
        adv_layout = QVBoxLayout()

        self.smp_passthrough_checkbox = QCheckBox("Copy host CPU configuration (host-passthrough)")
        adv_layout.addWidget(self.smp_passthrough_checkbox)

        hbox_cpu_model = QHBoxLayout()
        hbox_cpu_model.addWidget(QLabel("CPU Model:"))
        self.cpu_combo = QComboBox()
        hbox_cpu_model.addWidget(self.cpu_combo)
        adv_layout.addLayout(hbox_cpu_model)

        self.cpu_mitigations_checkbox = QCheckBox("Activate failsafe mitigations of CPU security, if available")
        adv_layout.addWidget(self.cpu_mitigations_checkbox)

        self.topology_checkbox = QCheckBox("Define CPU topology manually")
        adv_layout.addWidget(self.topology_checkbox)

        self._setup_topology_widgets(adv_layout)

        adv_group.setLayout(adv_layout)
        parent_layout.addWidget(adv_group)

    def _setup_topology_widgets(self, parent_layout: QVBoxLayout):
        self.topology_group = QGroupBox("Topology")
        topology_layout = QHBoxLayout()

        topology_layout.addWidget(QLabel("Sockets:"))
        self.smp_sockets_spinbox = QSpinBox()
        self.smp_sockets_spinbox.setRange(1, 16)
        self.smp_sockets_spinbox.setValue(1)
        topology_layout.addWidget(self.smp_sockets_spinbox)

        topology_layout.addWidget(QLabel("Cores:"))
        self.smp_cores_spinbox = QSpinBox()
        self.smp_cores_spinbox.setRange(1, 64)
        self.smp_cores_spinbox.setValue(1)
        topology_layout.addWidget(self.smp_cores_spinbox)

        topology_layout.addWidget(QLabel("Threads:"))
        self.smp_threads_spinbox = QSpinBox()
        self.smp_threads_spinbox.setRange(1, 16)
        self.smp_threads_spinbox.setValue(1)
        topology_layout.addWidget(self.smp_threads_spinbox)

        self.topology_group.setLayout(topology_layout)
        self.topology_group.setVisible(False)
        parent_layout.addWidget(self.topology_group)

    def _setup_machine_and_memory_widgets(self, parent_layout: QVBoxLayout):
        self.kvm_accel_checkbox = QCheckBox("Enable KVM Acceleration")
        parent_layout.addWidget(self.kvm_accel_checkbox)

        parent_layout.addWidget(QLabel("Machine Type:"))
        self.machine_combo = QComboBox()
        # Valores padrão para máquina. Serão populados por load_machine_list.
        self.machine_combo.addItems([DEFAULT_MACHINE_QEMU_ARG, "q35", "isapc"])
        parent_layout.addWidget(self.machine_combo)
        self.sata_checkbox = QCheckBox("Enable SATA")
        parent_layout.addWidget(self.sata_checkbox)

        parent_layout.addWidget(QLabel("Memory (MB):"))
        self.mem_combo = QComboBox()
        self.mem_combo.setEditable(True)
        mem_sizes = [str(2**i) for i in range(8, 16)]  # 256MB to 32768MB
        self.mem_combo.addItems(mem_sizes)
        # Define um valor inicial padrão para memória, se não estiver na lista, adiciona.
        if self.mem_combo.findText(str(DEFAULT_MEMORY_QEMU_ARG)) == -1:
            self.mem_combo.insertItem(0, str(DEFAULT_MEMORY_QEMU_ARG))
        self.mem_combo.setCurrentText(str(DEFAULT_MEMORY_QEMU_ARG))

        line_edit = self.mem_combo.lineEdit()
        if line_edit is not None:
            line_edit.setValidator(QIntValidator(128, 65536))
        parent_layout.addWidget(self.mem_combo)

    def _setup_misc_widgets(self, parent_layout: QVBoxLayout):
        group = QGroupBox("Extras")
        layout = QVBoxLayout()

        self.usb_checkbox = QCheckBox("Enable legacy USB support (-usb)")
        layout.addWidget(self.usb_checkbox)
        self.mouse_usb_checkbox = QCheckBox("Enable mouse USB support (-device usb-mouse)")
        layout.addWidget(self.mouse_usb_checkbox)
        self.tablet_usb_checkbox = QCheckBox("Enable tablet USB support (-device usb-tablet)")
        layout.addWidget(self.tablet_usb_checkbox)

        self.rtc_checkbox = QCheckBox("Enable RTC with localtime (-rtc base=localtime,clock=host)")
        layout.addWidget(self.rtc_checkbox)

        self.nodefaults_checkbox = QCheckBox("Disable default devices (-nodefaults)")
        layout.addWidget(self.nodefaults_checkbox)

        hbox_bios = QHBoxLayout()
        hbox_bios.addWidget(QLabel("BIOS file path:"))

        self.bios_lineedit = QLineEdit()
        hbox_bios.addWidget(self.bios_lineedit)

        self.bios_browse_btn = QPushButton("Browse")
        hbox_bios.addWidget(self.bios_browse_btn)

        layout.addLayout(hbox_bios)

        layout.addWidget(QLabel("Boot order:"))
        self.boot_combo = QComboBox()
        self.boot_combo.addItems([
            "",  # Empty/default
            "c",  # Disk
            "d",  # CD
            "menu=on",
            "c,menu=on",
            "d,menu=on"
        ])
        layout.addWidget(self.boot_combo)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    # === Signal Binding ===

    def bind_signals(self):
        # CPU and topology signals - TODOS conectados a _on_hardware_config_changed
        self.cpu_combo.currentTextChanged.connect(self.hardware_config_changed)
        self.smp_cpu_spinbox.valueChanged.connect(self.hardware_config_changed)
        self.smp_passthrough_checkbox.toggled.connect(self.hardware_config_changed)
        self.cpu_mitigations_checkbox.toggled.connect(self.hardware_config_changed)
        self.topology_checkbox.toggled.connect(self.hardware_config_changed)
        self.smp_sockets_spinbox.valueChanged.connect(self.hardware_config_changed)
        self.smp_cores_spinbox.valueChanged.connect(self.hardware_config_changed)
        self.smp_threads_spinbox.valueChanged.connect(self.hardware_config_changed)

        # Machine, Memory, KVM signals - TODOS conectados a _on_hardware_config_changed
        self.machine_combo.currentTextChanged.connect(self.hardware_config_changed)
        self.mem_combo.currentTextChanged.connect(self.hardware_config_changed)
        self.kvm_accel_checkbox.stateChanged.connect(self.hardware_config_changed)

        # Misc signals - TODOS conectados a _on_hardware_config_changed
        self.usb_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.mouse_usb_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.tablet_usb_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.rtc_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.nodefaults_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.bios_lineedit.textChanged.connect(self.hardware_config_changed)
        self.boot_combo.currentTextChanged.connect(self.hardware_config_changed)

        self.bios_browse_btn.clicked.connect(self.on_bios_browse_clicked)

        self.app_context.qemu_config_updated.connect(self.update_qemu_helper)

    # === Configuration Updates ===

    def _on_hardware_config_changed(self):
        """
        Este método é chamado quando alguma alteração na GUI da HardwarePage acontece
        e precisa ser refletida na QemuConfig do AppContext.
        Ele vai coletar TODOS os dados de hardware da GUI desta página
        e enviá-los em um dicionário para o AppContext atualizar a QemuConfig.
        """
        if self._loading_config or self._updating_cpu_ui or self.app_context._blocking_signals:
            return # Evita loops quando o próprio código ou o AppContext atualiza a UI

        # 1. Coleta os dados de hardware da GUI e os organiza em um dicionário.
        #    As chaves devem ser os nomes dos argumentos QEMU que a QemuConfig espera.
        hardware_data: Dict[str, Any] = {}

        # CPU Model (-cpu) e SMP (-smp)
        cpu_val = self.cpu_combo.currentText().strip()
        passthrough_enabled = self.smp_passthrough_checkbox.isChecked()
        topology_enabled = self.topology_checkbox.isChecked()

        if passthrough_enabled:
            hardware_data['cpu'] = HOST_CPU
            # Se cpu for host, smp é implícito, não adicionamos -smp explicitamente
            # a QemuConfig.to_qemu_args_string já sabe disso.
        elif cpu_val and cpu_val != DEFAULT_CPU:
            hardware_data['cpu'] = cpu_val
        # Se cpu_val é DEFAULT_CPU e não é passthrough, não adicionamos 'cpu' para usar o default

        if topology_enabled:
            sockets = self.smp_sockets_spinbox.value()
            cores = self.smp_cores_spinbox.value()
            threads = self.smp_threads_spinbox.value()
            hardware_data['smp'] = {'sockets': sockets, 'cores': cores, 'threads': threads}
        elif not passthrough_enabled:
            # Apenas se não for passthrough, o smp_cpu_spinbox controla o valor
            smp_val = self.smp_cpu_spinbox.value()
            if smp_val != DEFAULT_MEMORY_QEMU_ARG: # Comparar com o default de smp, que é 2
                hardware_data['smp'] = smp_val
        # Se passthrough_enabled, 'smp' é omitido ou o valor padrão (2) será usado,
        # dependendo de como a QemuConfig lida com defaults quando a chave está ausente.

        # CPU Mitigations (-cpu-mitigations)
        if self.cpu_mitigations_checkbox.isChecked():
            hardware_data['cpu-mitigations'] = 'on' # QEMU espera 'on' ou 'off'
        else:
            hardware_data['cpu-mitigations'] = 'off' # Explicitamente 'off' se desmarcado, ou remover se default é False

        # Machine Type (-machine)
        machine_val = self.machine_combo.currentText().strip()
        if machine_val and machine_val != DEFAULT_MACHINE_QEMU_ARG:
            hardware_data['machine'] = machine_val
        # else: se for DEFAULT_MACHINE_QEMU_ARG, a QemuConfig usará o seu próprio default.

        # Memory (-m)
        mem_val_str = self.mem_combo.currentText().strip()
        try:
            mem_val_int = int(mem_val_str)
            if mem_val_int != DEFAULT_MEMORY_QEMU_ARG: # Compara com o default de memória
                hardware_data['m'] = mem_val_int
        except ValueError:
            # Se não for um número válido, podemos ignorar ou definir um padrão seguro
            print(f"HardwarePage: Valor de memória inválido: {mem_val_str}")
            pass # Deixa QemuConfig lidar com o default se 'm' não for definido

        # KVM Acceleration (-enable-kvm)
        hardware_data['enable-kvm'] = self.kvm_accel_checkbox.isChecked()

        # USB (-usb)
        hardware_data['usb'] = self.usb_checkbox.isChecked()

        # RTC (-rtc)
        # O QemuConfig espera 'rtc': True para base=localtime,clock=host, ou um dict com mais opções.
        # Estamos assumindo que o checkbox significa o default.
        if self.rtc_checkbox.isChecked():
            hardware_data['rtc'] = {'base': 'localtime', 'clock': 'host'} # Padrão para checkbox RTC
        else:
            hardware_data['rtc'] = False # Define como False se desmarcado

        # No Defaults (-nodefaults)
        hardware_data['nodefaults'] = self.nodefaults_checkbox.isChecked()

        # BIOS Path (-bios)
        bios_path = self.bios_lineedit.text().strip()
        if bios_path:
            hardware_data['bios'] = bios_path

        # Boot order (-boot)
        boot_val = self.boot_combo.currentText().strip()
        if boot_val:
            # O AppContext.QemuConfig.parse_qemu_command_line_to_config
            # já lida com 'menu=on' e 'c,menu=on', então podemos passar a string.
            if '=' in boot_val: # ex: 'menu=on'
                hardware_data['boot'] = self.qemu_argument_parser._parse_qemu_key_value_string(boot_val)
            else: # ex: 'c' ou 'd'
                hardware_data['boot'] = {'order': boot_val}
        else:
            # Se vazio, garante que 'boot' não seja enviado ou seja resetado.
            # O AppContext deve ter lógica para remover args se o valor for "vazio".
            # Ou podemos omitir 'boot' do hardware_data. Por simplicidade, omisso se vazio.
            pass


        # 2. Envia o dicionário de dados para o AppContext.
        self.qemu_config.update_qemu_config_from_page(hardware_data)
        overview_page = self.app_context.get_page("overview")
        if overview_page:
            overview_page.refresh_display_from_qemu_config()
        self.app_context.mark_modified()        
        
        # Chamar _update_cpu_config_and_ui AQUI para garantir que a lógica de UI do CPU/SMP
        # (visibilidade e habilitação) seja aplicada APÓS os valores serem lidos da UI e enviados.
        # Isto é crucial porque as flags `_loading_config` e `_updating_cpu_ui`
        # precisam ser consideradas. O ideal é que `_update_cpu_config_and_ui` seja chamado
        # APENAS no `load_from_qemu_config`, quando a UI está sendo preenchida a partir da config.
        # Aqui, estamos REAGINDO a uma mudança da UI para a config, então o `_update_cpu_config_and_ui`
        # não deveria ser chamado diretamente por aqui, pois pode causar loops se mal orquestrado.
        # A responsabilidade de ajustar a UI deve ser do load_from_qemu_config,
        # que é acionado após a QemuConfig ser atualizada e o sinal emitido.

        print("HardwarePage: Configuração coletada da GUI e enviada para QemuConfig")


    # Métodos que agora APENAS disparam o sinal `hardware_config_changed`
    # Eles não precisam mais coletar dados individualmente, pois _on_hardware_config_changed faz isso.
    # on_machine_changed, on_mem_changed, on_kvm_changed são removidos pois o bind_signals
    # já os conecta diretamente ao hardware_config_changed.emit.
    # _update_misc_config também pode ser removido, pois tudo vai para _on_hardware_config_changed.

    def on_bios_browse_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select BIOS file")
        if path:
            self.bios_lineedit.setText(path)
            # A mudança de texto no lineEdit já aciona hardware_config_changed.emit,
            # que por sua vez, aciona _on_hardware_config_changed.

    def _update_cpu_config_and_ui(self):
        """
        Atualiza a lógica de habilitação/visibilidade dos widgets de CPU/Topology
        com base nos estados atuais dos checkboxes e comboboxes.
        Esta função é chamada para REAGIR a mudanças na UI ou quando a página é carregada.
        """
        if self._loading_config: # Se estamos carregando a config, não aplicamos lógica de UI ainda.
            return
        
        self._updating_cpu_ui = True # Ativa a flag para indicar que a UI está sendo atualizada por código
        self._set_cpu_signals_blocked(True) # Bloqueia sinais de CPU/SMP para evitar re-entrância

        try:
            current_cpu = self.cpu_combo.currentText()
            passthrough_enabled = self.smp_passthrough_checkbox.isChecked()
            # Desabilita combo de CPU se passthrough estiver ativo            
            topology_enabled = self.topology_checkbox.isChecked()

            is_host_cpu_model = (current_cpu == HOST_CPU or current_cpu == "max")

            # Apenas mostra checkbox de passthrough se cpu for "host" ou "max"
            self.smp_passthrough_checkbox.setVisible(is_host_cpu_model)

            # Se não for "host" ou "max", esconde o checkbox e garante que esteja desmarcado
            if not is_host_cpu_model:
                self.smp_passthrough_checkbox.setChecked(False)
                self.smp_passthrough_checkbox.setVisible(False)
                passthrough_enabled = False
            else:
                self.smp_passthrough_checkbox.setVisible(True)
                # Deixa o valor como está — usuário pode marcar ou desmarcar

            # Topology só pode estar habilitada se passthrough NÃO estiver ativo
            if passthrough_enabled:
                self.topology_checkbox.setChecked(False) # Desmarca topologia
                self.topology_checkbox.setEnabled(False) # Desabilita checkbox de topologia
                self.topology_group.setVisible(False) # Esconde grupo de topologia
                topology_enabled = False # Atualiza a variável local
            else:
                self.topology_checkbox.setEnabled(True) # Habilita checkbox de topologia
                self.topology_group.setVisible(topology_enabled) # Mostra/esconde grupo de topologia

            # vCPU spinbox só habilitado se topologia NÃO estiver ativada
            self.smp_cpu_spinbox.setEnabled(not topology_enabled)

            # Sincroniza o smp_cpu_spinbox para refletir a topologia ou passthrough
            smp_cpus_calculated = 0
            if topology_enabled:
                sockets = self.smp_sockets_spinbox.value()
                cores = self.smp_cores_spinbox.value()
                threads = self.smp_threads_spinbox.value()
                smp_cpus_calculated = sockets * cores * threads
            elif passthrough_enabled:
                smp_cpus_calculated = self.host_cpu_count
            else:
                smp_cpus_calculated = self.smp_cpu_spinbox.value()

            # Evita que o spinbox mude durante o carregamento de config
            if not self._loading_config and self.smp_cpu_spinbox.value() != smp_cpus_calculated:
                self.smp_cpu_spinbox.setValue(smp_cpus_calculated)

            # Alerta se vCPUs selecionadas ultrapassam CPUs do host (apenas um aviso)
            if smp_cpus_calculated > self.host_cpu_count and not self._loading_config: # Não alerta durante carregamento
                QMessageBox.warning(self, "vCPU Warning",
                                    f"vCPUs selecionadas ({smp_cpus_calculated}) excedem CPUs físicas do host ({self.host_cpu_count}).")

        finally:
            self._updating_cpu_ui = False # Desativa a flag
            self._set_cpu_signals_blocked(False) # Desbloqueia sinais

    def _set_cpu_signals_blocked(self, blocked: bool):
        widgets = [
            self.cpu_combo, self.smp_passthrough_checkbox,
            self.smp_cpu_spinbox, self.cpu_mitigations_checkbox,
            self.topology_checkbox, self.smp_sockets_spinbox,
            self.smp_cores_spinbox, self.smp_threads_spinbox
        ]
        for w in widgets:
            w.blockSignals(blocked)

    # === Loaders ===

    def load_cpu_list(self):
        self.cpu_combo.blockSignals(True)
        self.cpu_combo.clear()

        cpus = [DEFAULT_CPU]
        if self.qemu_helper:
            cpus.extend(c for c in self.qemu_helper.get_cpu_list() if c not in cpus)

        if HOST_CPU not in cpus:
            cpus.append(HOST_CPU)
        if "max" not in cpus:
            cpus.append("max")

        self.cpu_combo.addItems(sorted(cpus))
        self.cpu_combo.blockSignals(False)

    def load_machine_list(self):
        self.machine_combo.blockSignals(True)
        self.machine_combo.clear()

        machines = [DEFAULT_MACHINE_QEMU_ARG, "q35", "isapc"]
        if self.qemu_helper:
            machines.extend(m for m in self.qemu_helper.get_machine_list() if m not in machines)

        self.machine_combo.addItems(sorted(machines))
        self.machine_combo.blockSignals(False)


    def _set_all_signals_blocked(self, blocked: bool):
        """Bloqueia/desbloqueia todos os sinais de todos os widgets na página."""
        widgets = [
            self.cpu_combo, self.machine_combo, self.mem_combo,
            self.kvm_accel_checkbox, self.smp_passthrough_checkbox,
            self.smp_cpu_spinbox, self.cpu_mitigations_checkbox,
            self.topology_checkbox, self.smp_sockets_spinbox,
            self.smp_cores_spinbox, self.smp_threads_spinbox,
            self.usb_checkbox, self.rtc_checkbox, self.nodefaults_checkbox,
            self.bios_lineedit, self.boot_combo
        ]
        for w in widgets:
            if isinstance(w, QWidget):
                w.blockSignals(blocked)

    # === QEMU Helper Updates ===

    def update_qemu_helper(self):
        print(f"[DEBUG] Tipo de self.qemu_config: {type(self.qemu_config)}")
        print("[DEBUG] HardwarePage.update_qemu_helper()")
        bin_path = self.qemu_config.current_qemu_executable if self.qemu_config else None
        if not bin_path:
            self.qemu_helper = None
            self.load_cpu_list()     # Popula com defaults
            self.load_machine_list() # Popula com defaults
            return

        helper = self.qemu_config.get_qemu_helper(bin_path) if self.qemu_config else None
        if helper:
            self.qemu_helper = helper
        else:
            self.qemu_helper = None

        self.load_cpu_list()
        self.load_machine_list()

    # === Load from QemuConfig (Parse Reverso) ===

    def load_from_qemu_config(self, qemu_config_obj):
        if self._loading_config or self.app_context._blocking_signals:
            return
        
        self._loading_config = True
        self._set_all_signals_blocked(True)

        try:                                
            qemu_args_dict = qemu_config_obj.all_args
            print(f"HardwarePage: Carregando UI da QemuConfig: {qemu_args_dict}")

            # CPU Model (-cpu)
            cpu_model = qemu_args_dict.get("cpu", DEFAULT_CPU)
            if isinstance(cpu_model, dict):
                cpu_model = cpu_model.get("type", DEFAULT_CPU)
            passthrough_val = (cpu_model == HOST_CPU)

            self.smp_passthrough_checkbox.blockSignals(True)
            self.smp_passthrough_checkbox.setChecked(passthrough_val)
            self.smp_passthrough_checkbox.blockSignals(False)

            self.cpu_combo.blockSignals(True)
            self.cpu_combo.setCurrentText(cpu_model if self.cpu_combo.findText(cpu_model) != -1 else DEFAULT_CPU)
            self.cpu_combo.blockSignals(False)

            # SMP (-smp)
            smp_val = qemu_args_dict.get("smp")
            self.topology_checkbox.blockSignals(True)
            if isinstance(smp_val, dict):
                self.topology_checkbox.setChecked(True)

                self.smp_sockets_spinbox.blockSignals(True)
                self.smp_cores_spinbox.blockSignals(True)
                self.smp_threads_spinbox.blockSignals(True)

                self.smp_sockets_spinbox.setValue(smp_val.get('sockets', 1))
                self.smp_cores_spinbox.setValue(smp_val.get('cores', 1))
                self.smp_threads_spinbox.setValue(smp_val.get('threads', 1))

                self.smp_sockets_spinbox.blockSignals(False)
                self.smp_cores_spinbox.blockSignals(False)
                self.smp_threads_spinbox.blockSignals(False)
            elif isinstance(smp_val, int):
                self.topology_checkbox.setChecked(False)

                self.smp_cpu_spinbox.blockSignals(True)
                self.smp_cpu_spinbox.setValue(smp_val)
                self.smp_cpu_spinbox.blockSignals(False)
            else:
                self.topology_checkbox.setChecked(False)

                self.smp_cpu_spinbox.blockSignals(True)
                self.smp_cpu_spinbox.setValue(2)
                self.smp_cpu_spinbox.blockSignals(False)
            self.topology_checkbox.blockSignals(False)

            # CPU Mitigations
            cpu_mitigations_val = qemu_args_dict.get("cpu-mitigations", False)
            self.cpu_mitigations_checkbox.setChecked(
                cpu_mitigations_val is True or str(cpu_mitigations_val).lower() == 'true'
            )

            # Machine Type (-machine)
            machine = qemu_args_dict.get("machine", DEFAULT_MACHINE_QEMU_ARG)
            if isinstance(machine, dict):
                machine = machine.get('type', DEFAULT_MACHINE_QEMU_ARG)
            self.machine_combo.setCurrentText(machine if self.machine_combo.findText(machine) != -1 else DEFAULT_MACHINE_QEMU_ARG)

            # Memory (-m)
            mem = str(qemu_args_dict.get("m", DEFAULT_MEMORY_QEMU_ARG))
            self.mem_combo.setCurrentText(mem if self.mem_combo.findText(mem) != -1 else str(DEFAULT_MEMORY_QEMU_ARG))

            # KVM Acceleration
            self.kvm_accel_checkbox.setChecked(bool(qemu_args_dict.get("enable-kvm", False)))

            # USB
            self.usb_checkbox.setChecked(bool(qemu_args_dict.get("usb", False)))

            # RTC
            rtc_val = qemu_args_dict.get("rtc", False)
            if isinstance(rtc_val, dict):
                self.rtc_checkbox.setChecked(True)
            else:
                self.rtc_checkbox.setChecked(bool(rtc_val))

            # Nodefaults
            self.nodefaults_checkbox.setChecked(bool(qemu_args_dict.get("nodefaults", False)))

            # BIOS Path
            bios_path = qemu_args_dict.get("bios", "")
            self.bios_lineedit.setText(str(bios_path))

            # Boot Order (-boot)
            boot_config = qemu_args_dict.get("boot")
            boot_order_str = ""
            if isinstance(boot_config, dict):
                parts = []
                if 'order' in boot_config:
                    parts.append(boot_config['order'])
                if 'menu' in boot_config:
                    parts.append(f"menu={boot_config['menu']}")
                boot_order_str = ",".join(parts)
            elif isinstance(boot_config, str):
                boot_order_str = boot_config
            self.boot_combo.setEditText(boot_order_str)

            self._update_cpu_config_and_ui()

        finally:
            self._loading_config = False
            self._set_all_signals_blocked(False)