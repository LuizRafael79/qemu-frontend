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
from typing import Optional, List, Dict, Any
from app.utils.qemu_helper import QemuHelper
from app.context.app_context import AppContext
import sys
import os

# Constantes para as chaves de configuração
CPU_CONFIG = "cpu"
MACHINE_TYPE_CONFIG = "machine_type"
MEMORY_MB_CONFIG = "memory_mb"
KVM_ACCEL_CONFIG = "kvm_acceleration"
DEFAULT_KVM = False
SMP_PASSTHROUGH_CONFIG = "smp_passthrough"
SMP_CPUS_CONFIG = "smp_cpus"
CPU_MITIGATIONS_CONFIG = "cpu_mitigations"
TOPOLOGY_ENABLED_CONFIG = "topology_enabled"
SMP_SOCKETS_CONFIG = "smp_sockets"
SMP_CORES_CONFIG = "smp_cores"
SMP_THREADS_CONFIG = "smp_threads"

DEFAULT_CPU = "default"
DEFAULT_MACHINE = "pc"
DEFAULT_MEMORY = "1024"
HOST_CPU = "host"

ENABLE_USB = "enable_usb"
ENABLE_RTC = "enable_rtc"
DISABLE_NODEFAULTS = "disable_nodefaults"
BIOS_PATH = "bios_path"
BOOT_ORDER = "boot_order"


class HardwarePage(QWidget):
    hardware_config_changed = pyqtSignal()

    def __init__(self, app_context: AppContext):       
        super().__init__()        
        self.app_context = app_context
        self.qemu_helper: Optional[QemuHelper] = None
        self.host_cpu_count = multiprocessing.cpu_count()
        self._loading_config = False

        self._setup_ui()
        self.bind_signals()
        self.hardware_config_changed.connect(self.app_context.config_changed.emit)

        self.load_config_to_ui()

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
        self.smp_cpu_spinbox.setValue(4)
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
        self.machine_combo.addItems([DEFAULT_MACHINE, "q35", "isapc"])
        parent_layout.addWidget(self.machine_combo)

        parent_layout.addWidget(QLabel("Memory (MB):"))
        self.mem_combo = QComboBox()
        self.mem_combo.setEditable(True)
        mem_sizes = [str(2**i) for i in range(8, 16)]  # 256MB to 32768MB
        self.mem_combo.addItems(mem_sizes)
        line_edit = self.mem_combo.lineEdit()
        if line_edit is not None:
            line_edit.setValidator(QIntValidator(128, 65536))
        parent_layout.addWidget(self.mem_combo)

    def _setup_misc_widgets(self, parent_layout: QVBoxLayout):
        group = QGroupBox("Extras")
        layout = QVBoxLayout()

        self.usb_checkbox = QCheckBox("Enable legacy USB support (-usb)")
        layout.addWidget(self.usb_checkbox)

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
        self.app_context.config_changed.connect(self.on_app_config_changed)

        # CPU and topology signals
        self.cpu_combo.currentTextChanged.connect(self._update_cpu_config_and_ui)
        self.smp_cpu_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        self.smp_passthrough_checkbox.toggled.connect(self._update_cpu_config_and_ui)
        self.cpu_mitigations_checkbox.toggled.connect(self._update_cpu_config_and_ui)
        self.topology_checkbox.toggled.connect(self._update_cpu_config_and_ui)
        self.smp_sockets_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        self.smp_cores_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        self.smp_threads_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        
        # Memory signals
        self.mem_combo.currentTextChanged.connect(self._update_cpu_config_and_ui)
        self.kvm_accel_checkbox.stateChanged.connect(self._update_cpu_config_and_ui)

        # Misc signals
        self.usb_checkbox.stateChanged.connect(lambda s: self._update_misc_config())
        self.rtc_checkbox.stateChanged.connect(lambda s: self._update_misc_config())
        self.nodefaults_checkbox.stateChanged.connect(lambda s: self._update_misc_config())
        self.bios_lineedit.textChanged.connect(self._update_misc_config)
        self.bios_browse_btn.clicked.connect(self.on_bios_browse_clicked)
        self.boot_combo.currentTextChanged.connect(lambda s: self._update_misc_config())

        # Other hardware signals
        self.machine_combo.currentTextChanged.connect(self.on_machine_changed)
        self.mem_combo.currentTextChanged.connect(self.on_mem_changed)
        self.kvm_accel_checkbox.stateChanged.connect(self.on_kvm_changed)

    # === Configuration Updates ===

    def _update_misc_config(self):
        config_update = {
            ENABLE_USB: self.usb_checkbox.isChecked(),
            ENABLE_RTC: self.rtc_checkbox.isChecked(),
            DISABLE_NODEFAULTS: self.nodefaults_checkbox.isChecked(),            
            BIOS_PATH: self.bios_lineedit.text().strip(),
            BOOT_ORDER: self.boot_combo.currentText().strip()
        }
        self.app_context.update_config(config_update)
        self.hardware_config_changed.emit()

    def on_bios_browse_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select BIOS file")
        if path:
            self.bios_lineedit.setText(path)  # Aqui usa setText, pois é QLineEdit
            self._update_misc_config()  # Atualiza config com novo caminho


    def _update_cpu_config_and_ui(self):
        if getattr(self, "_loading_config", False):
            return  # ← impede sobrescrita de valores do JSON
        if getattr(self, "_updating_cpu_ui", False):
            return
        self._updating_cpu_ui = True        
        try:
            current_cpu = self.cpu_combo.currentText()
            passthrough_enabled = self.smp_passthrough_checkbox.isChecked()
            topology_enabled = self.topology_checkbox.isChecked()

            # Apenas mostra checkbox de passthrough se cpu for "host" ou "max"
            is_host_cpu = current_cpu in ("host", "max")
            self.smp_passthrough_checkbox.setVisible(is_host_cpu)

            # Se não for cpu especial, força checkbox passthrough desativada e invisível
            if not is_host_cpu and passthrough_enabled:
                # Se o usuário mudou para cpu não-host mas checkbox estava marcado, limpa ela
                self.smp_passthrough_checkbox.setChecked(False)
                passthrough_enabled = False

            # Topology só pode estar habilitada se passthrough não estiver ativo
            if passthrough_enabled:
                # Quando passthrough está ativo, topologia é desabilitada e desmarcada
                self.topology_checkbox.setChecked(False)
                self.topology_checkbox.setEnabled(False)
                self.topology_group.setVisible(False)
                topology_enabled = False
            else:
                # Quando passthrough não está ativo, topologia fica habilitada e visível de acordo com checkbox
                self.topology_checkbox.setEnabled(True)
                self.topology_group.setVisible(topology_enabled)

            # vCPU spinbox só habilitado se topologia NÃO estiver ativada
            self.smp_cpu_spinbox.setEnabled(not topology_enabled)

            # Calcula o valor de smp_cpus com base na topologia ou spinbox ou passthrough
            smp_cpus = 0
            if topology_enabled:
                sockets = self.smp_sockets_spinbox.value()
                cores = self.smp_cores_spinbox.value()
                threads = self.smp_threads_spinbox.value()
                smp_cpus = sockets * cores * threads
                # Sincroniza spinbox para refletir a topologia
                if self.smp_cpu_spinbox.value() != smp_cpus:
                    self.smp_cpu_spinbox.blockSignals(True)
                    self.smp_cpu_spinbox.setValue(smp_cpus)
                    self.smp_cpu_spinbox.blockSignals(False)
            elif passthrough_enabled:
                # Se passthrough ativado, geralmente usa metade das CPUs do host, no mínimo 1
                smp_cpus = max(1, self.host_cpu_count // 2)
                if self.smp_cpu_spinbox.value() != smp_cpus:
                    self.smp_cpu_spinbox.blockSignals(True)
                    self.smp_cpu_spinbox.setValue(smp_cpus)
                    self.smp_cpu_spinbox.blockSignals(False)
            else:
                # Senão usa valor do spinbox mesmo
                smp_cpus = self.smp_cpu_spinbox.value()

            # Alerta se vCPUs selecionadas ultrapassam CPUs do host
            if smp_cpus > self.host_cpu_count:
                QMessageBox.warning(self, "vCPU Warning", f"vCPUs selecionadas ({smp_cpus}) excedem CPUs físicas do host ({self.host_cpu_count}).")

            # Prepara update
            config_update = {
                CPU_CONFIG: current_cpu,
                SMP_PASSTHROUGH_CONFIG: passthrough_enabled,
                CPU_MITIGATIONS_CONFIG: self.cpu_mitigations_checkbox.isChecked(),
                TOPOLOGY_ENABLED_CONFIG: topology_enabled,
                SMP_CPUS_CONFIG: smp_cpus,
                SMP_SOCKETS_CONFIG: self.smp_sockets_spinbox.value(),
                SMP_CORES_CONFIG: self.smp_cores_spinbox.value(),
                SMP_THREADS_CONFIG: self.smp_threads_spinbox.value(),
            }

            # Compara o estado atual para evitar update desnecessário
            current_config_subset = {k: self.app_context.config.get(k) for k in config_update}
            if config_update != current_config_subset:
                try:
                    self.app_context.config_changed.disconnect(self.on_app_config_changed)
                except Exception:
                    pass  # sinal pode já estar desconectado

                self.app_context.update_config(config_update)

                self.app_context.config_changed.connect(self.on_app_config_changed)

                self.hardware_config_changed.emit()

        finally:
            self._updating_cpu_ui = False
    

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
        self._loading_config = True
        self.cpu_combo.blockSignals(True)
        self.cpu_combo.clear()

        cpus = [DEFAULT_CPU]
        if self.qemu_helper:
            print("QEMU Helper não disponível na HardwarePage")
            cpus = self.qemu_helper.get_cpu_list()
            print(f"[load_cpu_list] CPUs carregadas: {cpus}")

        self.cpu_combo.addItems(cpus)

        selected_cpu = self.app_context.config.get(CPU_CONFIG, "")
        if self.cpu_combo.findText(selected_cpu) != -1:
            self.cpu_combo.setCurrentText(selected_cpu)
        elif self.cpu_combo.count() > 0:
            self.cpu_combo.setCurrentIndex(0)
            print("Combo de CPU: adicionou fallback 'default'")

        self.cpu_combo.blockSignals(False)
        self._update_cpu_config_and_ui()
        self._loading_config = False

    def load_machine_list(self):
        self.machine_combo.blockSignals(True)
        self.machine_combo.clear()

        machines = [DEFAULT_MACHINE, "q35", "isapc"]
        if self.qemu_helper:
            machines = self.qemu_helper.get_machine_list()

        self.machine_combo.addItems(machines)

        selected_machine = self.app_context.config.get(MACHINE_TYPE_CONFIG, DEFAULT_MACHINE)
        if self.machine_combo.findText(selected_machine) != -1:
            self.machine_combo.setCurrentText(selected_machine)
        else:
            self.machine_combo.setCurrentText(DEFAULT_MACHINE)

        self.machine_combo.blockSignals(False)

    def load_config_to_ui(self):
        if self._loading_config:
            return
        self._loading_config = True
        try:
            self._set_all_signals_blocked(True)              
            config = self.app_context.config

            # Machine
            machine = config.get(MACHINE_TYPE_CONFIG, DEFAULT_MACHINE)
            if self.machine_combo.findText(machine) != -1:
                self.machine_combo.setCurrentText(machine)
            else:
                self.machine_combo.setCurrentText(DEFAULT_MACHINE)

            # Memory
            mem = str(config.get(MEMORY_MB_CONFIG, DEFAULT_MEMORY))
            if self.mem_combo.findText(mem) != -1:
                self.mem_combo.setCurrentText(mem)
            else:
                self.mem_combo.setCurrentText(DEFAULT_MEMORY)

            # KVM
            kvm_accel = config.get(KVM_ACCEL_CONFIG, False)
            self.kvm_accel_checkbox.setChecked(kvm_accel)

            # SMP Passthrough and vCPUs
            self.smp_passthrough_checkbox.setChecked(config.get(SMP_PASSTHROUGH_CONFIG, False))
            smp_cpu = config.get(SMP_CPUS_CONFIG, 2)
            self.smp_cpu_spinbox.setValue(smp_cpu if smp_cpu >= 1 else 2)

            # Mitigations
            self.cpu_mitigations_checkbox.setChecked(config.get(CPU_MITIGATIONS_CONFIG, False))

            # Topology
            topology_enabled = config.get(TOPOLOGY_ENABLED_CONFIG, False)
            self.topology_checkbox.setChecked(topology_enabled)
            self.topology_group.setVisible(topology_enabled)
            self.smp_sockets_spinbox.setValue(config.get(SMP_SOCKETS_CONFIG, 1))
            self.smp_cores_spinbox.setValue(config.get(SMP_CORES_CONFIG, 1))
            self.smp_threads_spinbox.setValue(config.get(SMP_THREADS_CONFIG, 1))

            # USB, RTC, nodefaults
            self.usb_checkbox.setChecked(config.get(ENABLE_USB, False))
            self.rtc_checkbox.setChecked(config.get(ENABLE_RTC, False))
            self.nodefaults_checkbox.setChecked(config.get(DISABLE_NODEFAULTS, False))

            # BIOS path
            bios_path = config.get(BIOS_PATH, "")
            self.bios_lineedit.setText(bios_path)

            # Boot order
            boot = config.get(BOOT_ORDER, "")
            idx = self.boot_combo.findText(boot)
            if idx != -1:
                self.boot_combo.setCurrentIndex(idx)

        finally:
            self._loading_config = True
            self.load_cpu_list()
            self.load_machine_list()
            self._loading_config = False
            self._set_all_signals_blocked(False)

    def _set_all_signals_blocked(self, blocked: bool):
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
            w.blockSignals(blocked)

    # === QEMU Helper Updates ===

    def update_qemu_helper(self):
        print("update_qemu_helper chamado")
        config = self.app_context.config
        bin_path = ""

        try:
            custom_exec = config.get("qemu_executable", "").strip()
            print(f"Executável Qemu: {custom_exec}")
            
            if custom_exec and os.path.isfile(custom_exec):
                bin_path = custom_exec
            elif custom_exec:
                from shutil import which
                full_path = which(custom_exec)
                if full_path and os.path.isfile(full_path):
                    bin_path = full_path

            if not bin_path:
                print("Nenhum binário válido encontrado para QEMU.")
                return

        except Exception as e:
            print(f"Erro ao obter caminho do executável QEMU: {e}")
            return

        # Usa o cache corretamente via app_context
        qemu_info_cache = getattr(self.app_context, "qemu_info_cache", None)
        if not qemu_info_cache:
            print("qemu_info_cache não disponível na app_context.")
            return

        helper = qemu_info_cache._get_helper(bin_path)
        if helper is None:
            print(f"Erro ao obter helper para: {bin_path}")
            return

        # Seta o helper e usa os métodos que já existem
        self.qemu_helper = helper
        self.load_config_to_ui()

    # === Event Handlers ===

    def on_machine_changed(self, text):
        self.app_context.update_config({MACHINE_TYPE_CONFIG: text})
        self.hardware_config_changed.emit()

    def on_mem_changed(self, text):
        self.app_context.update_config({MEMORY_MB_CONFIG: int(text) if text.isdigit() else 1024})
        self.hardware_config_changed.emit()

    def on_kvm_changed(self, state):
        self.app_context.update_config({KVM_ACCEL_CONFIG: bool(state)})
        self.hardware_config_changed.emit()

    def on_app_config_changed(self):        
        if self._loading_config:
            return
        self._loading_config = True 

        # Verifica se o QEMU mudou
        config = self.app_context.config
        qemu_exec = config.get("qemu_executable", "").strip()
        if self.qemu_helper is None or (self.qemu_helper.qemu_path != qemu_exec):
            self.update_qemu_helper()
        self._loading_config = False

        # === Parse Direct / Reverse ===

    def qemu_direct_parse(self, args_list: list[str]) -> list[str]:
        it = iter(args_list)
        leftover = []

        while True:
            try:
                arg = next(it)
            except StopIteration:
                break

            if arg == "-cpu":
                val = next(it, None)
                if val:
                    self.cpu_combo.setCurrentText(val)
                continue

            elif arg == "-smp":
                val = next(it, None)
                if val:
                    try:
                        if "=" in val:
                            parts = val.split(",")
                            for part in parts:
                                k, v = part.split("=")
                                v_int = int(v)
                                if k == "sockets":
                                    self.smp_sockets_spinbox.setValue(v_int)
                                elif k == "cores":
                                    self.smp_cores_spinbox.setValue(v_int)
                                elif k == "threads":
                                    self.smp_threads_spinbox.setValue(v_int)
                            total = (
                                self.smp_sockets_spinbox.value()
                                * self.smp_cores_spinbox.value()
                                * self.smp_threads_spinbox.value()
                            )
                            self.smp_cpu_spinbox.setValue(total)
                        else:
                            smp_num = int(val)
                            self.smp_cpu_spinbox.setValue(smp_num)
                    except:
                        pass
                continue

            elif arg == "-machine":
                val = next(it, None)
                if val:
                    self.machine_combo.setCurrentText(val)
                continue

            elif arg == "-m":
                val = next(it, None)
                if val:
                    self.mem_combo.setCurrentText(val)
                continue

            elif arg == "-bios":
                val = next(it, None)
                if val:
                    self.bios_lineedit.setText(val)
                continue

            elif arg == "-boot":
                val = next(it, None)
                if val:
                    self.boot_combo.setCurrentText(val)
                continue

            else:
                leftover.append(arg)

        return leftover


    def qemu_reverse_parse(self) -> list[str]:
        args = []

        cpu_val = self.cpu_combo.currentText().strip()
        if cpu_val and cpu_val != DEFAULT_CPU:
            args += ["-cpu", cpu_val]

        if self.topology_checkbox.isChecked():
            sockets = self.smp_sockets_spinbox.value()
            cores = self.smp_cores_spinbox.value()
            threads = self.smp_threads_spinbox.value()
            smp_str = f"sockets={sockets},cores={cores},threads={threads}"
            args += ["-smp", smp_str]
        else:
            smp_val = str(self.smp_cpu_spinbox.value())
            args += ["-smp", smp_val]

        machine_val = self.machine_combo.currentText().strip()
        if machine_val:
            args += ["-machine", machine_val]

        mem_val = self.mem_combo.currentText().strip()
        if mem_val:
            args += ["-m", mem_val]

        if self.kvm_accel_checkbox.isChecked():
            args += ["-enable-kvm"]

        if self.smp_passthrough_checkbox.isChecked():
            args += ["-cpu", "host"]

        bios_val = self.bios_lineedit.text().strip()
        if bios_val:
            args += ["-bios", bios_val]

        boot_val = self.boot_combo.currentText().strip()
        if boot_val:
            args += ["-boot", boot_val]

        return args
     
        




