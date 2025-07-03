# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QHBoxLayout,
    QPushButton, QSpinBox, QGroupBox, QLineEdit, QFileDialog,
    QListWidget, QListWidgetItem, QPushButton, QAbstractItemView
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIntValidator 
import multiprocessing
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
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
        super().__init__()
        self.app_context = app_context
        self.qemu_config = self.app_context.qemu_config
        self.qemu_argument_parser = self.app_context.qemu_argument_parser
        self._setup_ui

        self.host_cpu_count = multiprocessing.cpu_count()
        self._loading_config = False 
        self._updating_cpu_ui = False 

        self._setup_ui()
        self.bind_signals()

        # Connect the hardware_config_changed signal to the AppContext update method
        # Note that the connection is to _on_hardware_config_changed (on this page)
        # which in turn CALLS AppContext.update_qemu_config_from_page
        self.hardware_config_changed.connect(self._on_hardware_config_changed)

        # Hooks into the AppContext signal that tells you that QemuConfig has been updated.
        # This is the main entry point for UPDATING the page's UI.
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
        self.smp_cpu_spinbox.setValue(4)  # Initial default value
        hbox_vcpu.addWidget(self.smp_cpu_spinbox)
        cpus_layout.addLayout(hbox_vcpu)

        # Agora adiciona o aviso **DENTRO** do grupo CPUs, após o spinbox
        self.vcpu_warning_label = QLabel()
        self.vcpu_warning_label.setStyleSheet("color: yellow; font-weight: italic;")
        self.vcpu_warning_label.setVisible(False)
        self.vcpu_warning_label.setText("⚠️ Atenção: vCPUs excedem CPUs físicas do host!")
        cpus_layout.addWidget(self.vcpu_warning_label)

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
        # Default values, These values ​​will be populated by QemuConfig based on the chosen binary
        self.machine_combo.addItems([DEFAULT_MACHINE_QEMU_ARG, "q35", "isapc"])
        parent_layout.addWidget(self.machine_combo)
        self.sata_checkbox = QCheckBox("Enable SATA")
        parent_layout.addWidget(self.sata_checkbox)

        parent_layout.addWidget(QLabel("Memory (MB):"))
        self.mem_combo = QComboBox()
        self.mem_combo.setEditable(True)
        mem_sizes = [str(2**i) for i in range(8, 16)]  # 256MB to 64GB
        mem_sizes.sort(reverse=True)
        self.mem_combo.addItems(mem_sizes)
        # Define the default value for memory if not present in config file
        if self.mem_combo.findText(str(DEFAULT_MEMORY_QEMU_ARG)) == -1:
            self.mem_combo.insertItem(0, str(DEFAULT_MEMORY_QEMU_ARG))
        self.mem_combo.setCurrentText(str(DEFAULT_MEMORY_QEMU_ARG))

        line_edit = self.mem_combo.lineEdit()
        if line_edit is not None:
            line_edit.setValidator(QIntValidator(128, 65536)) # change here to raise the values
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

        self.boot_list = QListWidget()
        self.boot_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.boot_list.setDefaultDropAction(Qt.MoveAction)
        self.boot_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.boot_list.setDragEnabled(True)
        self.boot_list.viewport().setAcceptDrops(True)
        self.boot_list.setDropIndicatorShown(True)
        self.boot_list.model().rowsMoved.connect(self.save_boot_order)

        # Exemplo de dispositivos
        boot_devices = ["Hard Drive (c)", "CD-ROM (d)", "Network (n)"]
        for dev in boot_devices:
            self.boot_list.addItem(QListWidgetItem(dev))

        layout.addWidget(self.boot_list)

        save_btn = QPushButton("Save Boot Order")
        save_btn.clicked.connect(self.save_boot_order)
        layout.addWidget(save_btn)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    # === Signal Binding ===
    def bind_signals(self):
        # Signals - all connected to _on_hardware_config_changed
        # because sending signal directly to the PyQtSignal is a bad practice
        # and cause infinite loops, recursion and memory leaks
        self.cpu_combo.currentTextChanged.connect(self.hardware_config_changed)
        self.smp_cpu_spinbox.valueChanged.connect(self.hardware_config_changed)
        self.smp_passthrough_checkbox.toggled.connect(self.hardware_config_changed)
        self.cpu_mitigations_checkbox.toggled.connect(self.hardware_config_changed)
        self.topology_checkbox.toggled.connect(self.hardware_config_changed)
        self.smp_sockets_spinbox.valueChanged.connect(self.hardware_config_changed)
        self.smp_cores_spinbox.valueChanged.connect(self.hardware_config_changed)
        self.smp_threads_spinbox.valueChanged.connect(self.hardware_config_changed)

        self.smp_passthrough_checkbox.stateChanged.connect(self._on_passthrough_toggled)
        self.topology_checkbox.stateChanged.connect(self._on_topology_toggled)

        self.machine_combo.currentTextChanged.connect(self.hardware_config_changed)
        self.mem_combo.currentTextChanged.connect(self.hardware_config_changed)
        self.kvm_accel_checkbox.stateChanged.connect(self.hardware_config_changed)

        self.usb_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.mouse_usb_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.tablet_usb_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.rtc_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.nodefaults_checkbox.stateChanged.connect(self.hardware_config_changed)
        self.boot_list.model().rowsMoved.connect(self.save_boot_order)

        # Bios signal is separated because the QDialog is a different Widget and
        # needs to be updated separately
        self.bios_browse_btn.clicked.connect(self.on_bios_browse_clicked)
        # Update configuration via AppContext -> QemuConfig -> QemuHelper
        # to avoid recursion and infite loops, etc
        self.app_context.qemu_config_updated.connect(self.update_qemu_helper)

    # === Configuration Updates ===

    def save_boot_order(self):
        order = []
        for i in range(self.boot_list.count()):
            # 1. Pega o item primeiro e o armazena em uma variável
            item = self.boot_list.item(i)
            
            # 2. Verifica se o item realmente existe (não é None)
            if item is not None:
                # 3. Só então, acessa o método .text() com segurança
                order.append(item.text())
                
        print("[DEBUG] Boot order:", order)

    def _on_hardware_config_changed(self):
        """
        This method is called when some change in the HardwarePage GUI happens
        and needs to be reflected in the AppContext's QemuConfig.
        It will collect ALL the hardware data from the GUI of this page
        and send it in a dictionary to the AppContext to update the QemuConfig.
        """
        if self._loading_config or self._updating_cpu_ui or self.app_context._blocking_signals:
            return # That is for intentional recursion block, don't edit or remove!

        # Create a dictionary with all hardware data from the GUI
        hardware_data: Dict[str, Any] = {}

        # CPU Model (-cpu) and SMP (-smp)
        cpu_val = self.cpu_combo.currentText().strip()
        passthrough_enabled = self.smp_passthrough_checkbox.isChecked()
        topology_enabled = self.topology_checkbox.isChecked()

        if passthrough_enabled:
            hardware_data['cpu'] = HOST_CPU
        elif cpu_val and cpu_val != DEFAULT_CPU:
            hardware_data['cpu'] = cpu_val

        if topology_enabled:
            sockets = self.smp_sockets_spinbox.value()
            cores = self.smp_cores_spinbox.value()
            threads = self.smp_threads_spinbox.value()
            hardware_data['smp'] = {'sockets': sockets, 'cores': cores, 'threads': threads}
        elif not passthrough_enabled:
            smp_val = self.smp_cpu_spinbox.value()
            if smp_val != DEFAULT_MEMORY_QEMU_ARG: 
                hardware_data['smp'] = smp_val

        # CPU Mitigations (-cpu-mitigations)
        if self.cpu_mitigations_checkbox.isChecked():
            hardware_data['cpu-mitigations'] = 'on'
        else:
            hardware_data['cpu-mitigations'] = 'off'

        # Machine Type (-machine)
        machine_val = self.machine_combo.currentText().strip()
        if machine_val and machine_val != DEFAULT_MACHINE_QEMU_ARG:
            hardware_data['machine'] = machine_val

        # Memory (-m)
        mem_val_str = self.mem_combo.currentText().strip()
        try:
            mem_val_int = int(mem_val_str)
            if mem_val_int != DEFAULT_MEMORY_QEMU_ARG:
                hardware_data['m'] = mem_val_int
        except ValueError:
            pass

        # KVM Acceleration (-enable-kvm)
        hardware_data['enable-kvm'] = self.kvm_accel_checkbox.isChecked()

        # --- USB (BLOCO CORRIGIDO) ---
        hardware_data['usb'] = self.usb_checkbox.isChecked()

        current_devices = list(self.qemu_config.get("device", []))

        other_devices = [
            dev for dev in current_devices
            if isinstance(dev, dict) and dev.get("interface") not in ["usb-tablet", "usb-mouse"]
        ]

        new_device_list = other_devices
        if self.tablet_usb_checkbox.isChecked():
            new_device_list.append({"interface": "usb-tablet"})
        
        if self.mouse_usb_checkbox.isChecked():
            new_device_list.append({"interface": "usb-mouse"})

        hardware_data['device'] = new_device_list

        # RTC (-rtc)
        if self.rtc_checkbox.isChecked():
            hardware_data['rtc'] = {'base': 'localtime', 'clock': 'host'}
        else:
            hardware_data['rtc'] = False

        # No Defaults (-nodefaults)
        hardware_data['nodefaults'] = self.nodefaults_checkbox.isChecked()

        # BIOS Path (-bios)
        bios_path = self.bios_lineedit.text().strip()
        if bios_path:
            hardware_data['bios'] = bios_path

        # --- Boot order (-boot) (BLOCO CORRIGIDO) ---
        # Lê a ordem dos itens diretamente do QListWidget
        order_chars = []
        for i in range(self.boot_list.count()):
            # 1. Pega o item e armazena em uma variável
            item = self.boot_list.item(i)
            
            # 2. Garante que o item não é None antes de continuar
            if item is not None:
                item_text = item.text()
                # O resto da sua lógica vai dentro deste 'if'
                if "(c)" in item_text:
                    order_chars.append('c')
                elif "(d)" in item_text:
                    order_chars.append('d')
                elif "(n)" in item_text:
                    order_chars.append('n')
        
        boot_order_str = "".join(order_chars)

        if boot_order_str:
            # Salva no formato de dicionário para ser consistente
            hardware_data['boot'] = {'order': boot_order_str}
        else:
            # Garante que se a lista estiver vazia, a chave 'boot' seja removida
            if 'boot' in hardware_data:
                del hardware_data['boot']
        
        # Send data dict to AppContext.
        self.qemu_config.update_qemu_config_from_page(hardware_data)
        overview_page = self.app_context.get_page("overview")
        if overview_page:
            overview_page.refresh_display_from_qemu_config()
        self.app_context.mark_modified()        
        self._update_warning_only()
        self._update_cpu_config_and_ui()

    def _update_warning_only(self):
        # Calcule smp_cpus_calculated com base no estado atual dos widgets:
        if self.topology_checkbox.isChecked():
            sockets = self.smp_sockets_spinbox.value()
            cores = self.smp_cores_spinbox.value()
            threads = self.smp_threads_spinbox.value()
            smp_cpus_calculated = sockets * cores * threads
        elif self.smp_passthrough_checkbox.isChecked():
            smp_cpus_calculated = self.host_cpu_count
        else:
            smp_cpus_calculated = self.smp_cpu_spinbox.value()

        self.vcpu_warning_label.setVisible(smp_cpus_calculated > self.host_cpu_count)

    def _on_passthrough_toggled(self):
        is_passthrough = self.smp_passthrough_checkbox.isChecked()

        # Oculta checkbox topology e grupo topology quando passthrough ativo
        self.topology_checkbox.setVisible(not is_passthrough)
        self.topology_group.setVisible(not is_passthrough and self.topology_checkbox.isChecked())

        # Mostra spinbox CPU simples só se passthrough e topology desativados
        self.smp_cpu_spinbox.setEnabled(not is_passthrough and not self.topology_checkbox.isChecked())

        # Se passthrough ativado, força desmarcar topology
        if is_passthrough:
            self.topology_checkbox.setChecked(False)


    def _on_topology_toggled(self):
        is_checked = self.topology_checkbox.isChecked()

        # Mostra/oculta grupo topology
        self.topology_group.setVisible(is_checked)

        # Mostra/oculta spinbox CPU simples
        self.smp_cpu_spinbox.setEnabled(not is_checked)

        self._update_cpu_config_and_ui()


    def on_bios_browse_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select BIOS file")
        if path:
            self.bios_lineedit.setText(path)

    def _update_cpu_config_and_ui(self):
        if self._loading_config:
            return

        self._updating_cpu_ui = True
        self._set_cpu_signals_blocked(True)

        try:
            current_cpu = self.cpu_combo.currentText()
            passthrough_enabled = self.smp_passthrough_checkbox.isChecked()
            topology_enabled = self.topology_checkbox.isChecked()

            is_host_cpu_model = (current_cpu == HOST_CPU or current_cpu == "max")

            # Mostrar passthrough somente se cpu for host ou max
            if is_host_cpu_model:
                self.smp_passthrough_checkbox.setVisible(True)
            else:
                self.smp_passthrough_checkbox.setChecked(False)
                self.smp_passthrough_checkbox.setVisible(False)
                passthrough_enabled = False

            # Topology só pode ser habilitada se passthrough NÃO estiver ativo
            if passthrough_enabled:
                if self.topology_checkbox.isChecked():
                    self.topology_checkbox.setChecked(False)
                self.topology_checkbox.setEnabled(False)
                self.topology_group.setVisible(False)
                topology_enabled = False
            else:
                self.topology_checkbox.setEnabled(True)
                self.topology_group.setVisible(topology_enabled)

            # vCPU Spinbox sempre visível
            self.smp_cpu_spinbox.setVisible(True)

            # Calcula o número total de vCPUs
            if topology_enabled:
                sockets = self.smp_sockets_spinbox.value()
                cores = self.smp_cores_spinbox.value()
                threads = self.smp_threads_spinbox.value()
                vcpus_total = sockets * cores * threads
            elif passthrough_enabled:
                vcpus_total = self.host_cpu_count
            else:
                vcpus_total = self.smp_cpu_spinbox.value()

            self._last_topology_vcpus = vcpus_total

            # Atualiza spinbox com total e estado de edição
            self.smp_cpu_spinbox.blockSignals(True)
            self.smp_cpu_spinbox.setValue(vcpus_total)
            self.smp_cpu_spinbox.setEnabled(not topology_enabled and not passthrough_enabled)
            self.smp_cpu_spinbox.setVisible(True)
            self.smp_cpu_spinbox.blockSignals(False)

            # Atualiza aviso de excesso de CPUs
            self.vcpu_warning_label.setVisible(vcpus_total > self.host_cpu_count)

            # Mostrar/ocultar checkbox de passthrough
            self.smp_passthrough_checkbox.setVisible(is_host_cpu_model)
            self.smp_passthrough_checkbox.setEnabled(not topology_enabled)

        finally:
            self._updating_cpu_ui = False
            self._set_cpu_signals_blocked(False)

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
            self.usb_checkbox, self.tablet_usb_checkbox, self.mouse_usb_checkbox,
            self.rtc_checkbox, self.nodefaults_checkbox, self.boot_list
        ]
        for w in widgets:
            if isinstance(w, QWidget):
                w.blockSignals(blocked)

    # === QEMU Helper Updates ===

    def update_qemu_helper(self):
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
            qemu_args_dict = self.qemu_config.all_args
            # --- SMP ---
            smp_val = qemu_args_dict.get("smp")
            self.topology_checkbox.blockSignals(True)
            if isinstance(smp_val, dict):
                self.topology_checkbox.setChecked(True)

                self.smp_sockets_spinbox.blockSignals(True)
                self.smp_cores_spinbox.blockSignals(True)
                self.smp_threads_spinbox.blockSignals(True)

                sockets = smp_val.get('sockets', 1)
                cores = smp_val.get('cores', 1)
                threads = smp_val.get('threads', 1)

                self.smp_sockets_spinbox.setValue(sockets)
                self.smp_cores_spinbox.setValue(cores)
                self.smp_threads_spinbox.setValue(threads)

                self.smp_sockets_spinbox.blockSignals(False)
                self.smp_cores_spinbox.blockSignals(False)
                self.smp_threads_spinbox.blockSignals(False)

                total_vcpus = sockets * cores * threads
                self.smp_cpu_spinbox.blockSignals(True)
                self.smp_cpu_spinbox.setValue(total_vcpus)
                self.smp_cpu_spinbox.setEnabled(False)
                self.smp_cpu_spinbox.blockSignals(False)

                self._on_topology_toggled()

            elif isinstance(smp_val, int):
                self.topology_checkbox.setChecked(False)
                self.smp_cpu_spinbox.blockSignals(True)
                self.smp_cpu_spinbox.setValue(smp_val)
                self.smp_cpu_spinbox.setEnabled(True)
                self.smp_cpu_spinbox.blockSignals(False)
            else:
                self.topology_checkbox.setChecked(False)
                self.smp_cpu_spinbox.blockSignals(True)
                self.smp_cpu_spinbox.setValue(2)
                self.smp_cpu_spinbox.setEnabled(True)
                self.smp_cpu_spinbox.blockSignals(False)
            self.topology_checkbox.blockSignals(False)

            # --- CPU Model + Passthrough ---
            cpu_arg = qemu_args_dict.get("cpu", DEFAULT_CPU)
            if isinstance(cpu_arg, dict):
                cpu_model = cpu_arg.get("type", DEFAULT_CPU)
            else:
                cpu_model = cpu_arg

            passthrough = cpu_model == HOST_CPU
            self.smp_passthrough_checkbox.blockSignals(True)
            self.smp_passthrough_checkbox.setChecked(passthrough)
            self.smp_passthrough_checkbox.blockSignals(False)

            self.cpu_combo.blockSignals(True)
            if self.cpu_combo.findText(cpu_model) == -1:
                self.cpu_combo.setCurrentText(DEFAULT_CPU)
            else:
                self.cpu_combo.setCurrentText(cpu_model)
            self.cpu_combo.blockSignals(False)

            # --- CPU Mitigations ---
            mitig_val = qemu_args_dict.get("cpu-mitigations", False)
            self.cpu_mitigations_checkbox.setChecked(str(mitig_val).lower() == "true" or mitig_val is True)

            # --- Machine ---
            machine = qemu_args_dict.get("machine", DEFAULT_MACHINE_QEMU_ARG)
            if isinstance(machine, dict):
                machine = machine.get('type', DEFAULT_MACHINE_QEMU_ARG)
            self.machine_combo.setCurrentText(machine if self.machine_combo.findText(machine) != -1 else DEFAULT_MACHINE_QEMU_ARG)

            # --- Memory ---
            mem = str(qemu_args_dict.get("m", DEFAULT_MEMORY_QEMU_ARG))
            self.mem_combo.setCurrentText(mem if self.mem_combo.findText(mem) != -1 else str(DEFAULT_MEMORY_QEMU_ARG))

            # --- KVM ---
            self.kvm_accel_checkbox.setChecked(bool(qemu_args_dict.get("enable-kvm", False)))

            # --- USB (BLOCO CORRIGIDO) ---
            self.usb_checkbox.setChecked(bool(qemu_args_dict.get("usb", False)))

            devices = qemu_args_dict.get("device", [])
            if not isinstance(devices, list):
                devices = [devices]

            is_tablet_present = any(d.get("interface") == "usb-tablet" for d in devices if isinstance(d, dict))
            is_mouse_present = any(d.get("interface") == "usb-mouse" for d in devices if isinstance(d, dict))

            self.tablet_usb_checkbox.setChecked(is_tablet_present)
            self.mouse_usb_checkbox.setChecked(is_mouse_present)

            # --- RTC ---
            rtc_val = qemu_args_dict.get("rtc", False)
            self.rtc_checkbox.setChecked(isinstance(rtc_val, dict) or bool(rtc_val))

            # --- Nodefaults ---
            self.nodefaults_checkbox.setChecked(bool(qemu_args_dict.get("nodefaults", False)))

            # --- BIOS ---
            self.bios_lineedit.setText(str(qemu_args_dict.get("bios", "")))

            # --- Boot Order (BLOCO CORRIGIDO) ---
            boot_config = qemu_args_dict.get("boot", {})
            boot_order_str = ""
            if isinstance(boot_config, dict):
                boot_order_str = boot_config.get('order', '')
            elif isinstance(boot_config, str): # Suporte para formato antigo, se houver
                boot_order_str = boot_config

            self.boot_list.clear()
            
            # Mapeia o caractere de boot para o texto completo na UI
            device_map = {"c": "Hard Drive (c)", "d": "CD-ROM (d)", "n": "Network (n)"}
            
            # Adiciona os itens na ordem em que foram salvos
            saved_order_chars = list(boot_order_str)
            added_items = []
            for char in saved_order_chars:
                if char in device_map:
                    full_text = device_map[char]
                    self.boot_list.addItem(QListWidgetItem(full_text))
                    added_items.append(full_text)
            
            # Adiciona quaisquer outros dispositivos que não estavam na ordem salva
            for char, full_text in device_map.items():
                if full_text not in added_items:
                    self.boot_list.addItem(QListWidgetItem(full_text))

            # --- Atualizações visuais finais ---
            self._update_cpu_config_and_ui()
            self._update_warning_only()

        except Exception:
            # Estrutura de debug, caso outro erro ocorra no futuro
            import traceback
            traceback.print_exc()

        finally:
            self._loading_config = False
            self._set_all_signals_blocked(False)

