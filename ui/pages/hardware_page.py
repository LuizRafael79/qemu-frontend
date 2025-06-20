from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QHBoxLayout,
    QPushButton, QSpinBox, QGroupBox, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, Qt
import subprocess
import os
import multiprocessing
from app.utils.qemu_helper import QemuHelper, QemuInfoCache

class HardwarePage(QWidget):
    hardware_config_changed = pyqtSignal()

    def __init__(self, app_context):
        super().__init__()
        
        self.app_context = app_context
        
        self.qemu_helper = None
       
        self.host_cpu_count = multiprocessing.cpu_count()

        self.setup_ui()
        self.bind_signals()
        
        self.load_cpu_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        self.title_label = QLabel("Virtual Machine Hardware")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # CPUs Section
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
        layout.addWidget(cpus_group)

        # Advanced Config Section
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
        adv_layout.addWidget(self.topology_group)

        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # Connect checkbox toggle for topology visibility
        self.topology_checkbox.toggled.connect(self.topology_group.setVisible)

        # Passthrough checkbox visibility linked to CPU model "host"
        self.cpu_combo.currentTextChanged.connect(
            lambda val: self.smp_passthrough_checkbox.setVisible(val == "host")
        )
        self.smp_passthrough_checkbox.setVisible(self.cpu_combo.currentText() == "host")

        # KVM acceleration checkbox
        self.kvm_accel_checkbox = QCheckBox("Enable KVM Acceleration")
        layout.addWidget(self.kvm_accel_checkbox)

        # Machine type
        self.machine_label = QLabel("Machine Type:")
        self.machine_combo = QComboBox()
        self.machine_combo.addItems(["pc", "q35", "isapc"])
        layout.addWidget(self.machine_label)
        layout.addWidget(self.machine_combo)

        # Memory size dropdown
        self.mem_label = QLabel("Memory (MB):")
        self.mem_combo = QComboBox()
        mem_sizes = [str(x) for x in [32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]]
        self.mem_combo.addItems(mem_sizes)
        layout.addWidget(self.mem_label)
        layout.addWidget(self.mem_combo)

        self.setLayout(layout)

    def bind_signals(self):
        # Usa o app_context para registrar callback da config global
        self.app_context.config_changed.connect(self.on_app_config_changed)

        self.cpu_combo.currentTextChanged.connect(self.on_cpu_changed)
        self.mem_combo.currentTextChanged.connect(self.on_mem_changed)
        self.kvm_accel_checkbox.stateChanged.connect(self.on_kvm_changed)
        self.smp_passthrough_checkbox.stateChanged.connect(self.on_smp_passthrough_changed)
        self.smp_cpu_spinbox.valueChanged.connect(self.on_smp_cpu_count_changed)
        self.machine_combo.currentTextChanged.connect(self.on_machine_changed)

        self.cpu_mitigations_checkbox.stateChanged.connect(self.on_cpu_mitigations_changed)

        self.topology_checkbox.toggled.connect(self.on_topology_toggled)
        self.smp_sockets_spinbox.valueChanged.connect(self.on_topology_values_changed)
        self.smp_cores_spinbox.valueChanged.connect(self.on_topology_values_changed)
        self.smp_threads_spinbox.valueChanged.connect(self.on_topology_values_changed)
        
    def update_qemu_helper(self):
        cfg = self.app_context.config
        bin_path = ""

        custom_exec = cfg.get("custom_executable", "").strip()
        if custom_exec and os.path.isfile(custom_exec):
            bin_path = custom_exec
        else:
            qemu_exec_name = cfg.get("qemu_executable", "").strip()
            qemu_binaries = getattr(self.app_context, "qemu_binaries", [])
            for full_path in qemu_binaries:
                if os.path.basename(full_path) == qemu_exec_name:
                    bin_path = full_path
                    break

        if bin_path and os.path.isfile(bin_path):
            self.qemu_helper = self.app_context.qemu_info_cache._get_helper(bin_path)
        else:
            self.qemu_helper = None

    def on_app_config_changed(self):
        # Se a config global mudar, atualiza lista de CPUs e UI
        self.update_qemu_helper()
        self.load_cpu_list()
        self.load_config_to_ui()
        self.load_machine_list()

    def on_cpu_changed(self, cpu_name):
        if not cpu_name:
            return
        # Atualiza config global via app_context
        self.app_context.update_config({"cpu": cpu_name})
        self.hardware_config_changed.emit()
        
        # Mostrar ou ocultar passthrough
        self.smp_passthrough_checkbox.setVisible(cpu_name == "host")
        
    def on_machine_changed(self, machine_type=None):
        if not machine_type:
            return
        self.app_context.update_config({"machine_type": machine_type})
        self.hardware_config_changed.emit()

    def on_mem_changed(self, mem_value):
        if not mem_value:
            return
        try:
            mem_int = int(mem_value)
        except ValueError:
            return
        self.app_context.update_config({"memory_mb": mem_int})
        self.hardware_config_changed.emit()

    def on_kvm_changed(self, state):
        enabled = (state == 2)
        self.app_context.update_config({"kvm_acceleration": enabled})
        self.hardware_config_changed.emit()
        
    def on_smp_passthrough_changed(self, state):
        enabled = (state == 2)
        self.app_context.update_config({"smp_passthrough": enabled})

        if enabled:
            half_cores = max(1, self.host_cpu_count // 2)
            self.smp_cpu_spinbox.setValue(half_cores)
            self.smp_cpu_spinbox.setEnabled(False)
        else:
            self.smp_cpu_spinbox.setEnabled(True)

        self.hardware_config_changed.emit()

    def on_smp_cpu_count_changed(self, value):
        if self.smp_passthrough_checkbox.isChecked():
            return
            
        if value > self.host_cpu_count:
            QMessageBox.warning(
                self,
                "Aviso de vCPUs",
                f"O número de vCPUs ({value}) excede o total de CPUs lógicas do host ({self.host_cpu_count})."
            )
            
        self.app_context.update_config({"smp_cpus": value})
        self.hardware_config_changed.emit()

    def on_cpu_mitigations_changed(self, state):
        enabled = (state == 2)
        self.app_context.update_config({"cpu_mitigations": enabled})
        self.hardware_config_changed.emit()

    def on_topology_toggled(self, checked):
        self.topology_group.setVisible(checked)   # controla a visibilidade do grupo inteiro
        self.smp_sockets_spinbox.setEnabled(checked)
        self.smp_cores_spinbox.setEnabled(checked)
        self.smp_threads_spinbox.setEnabled(checked)

        self.app_context.update_config({"topology_enabled": checked})
        self.hardware_config_changed.emit()

    def on_topology_values_changed(self):
        if not self.topology_checkbox.isChecked():
            self.topology_checkbox.setChecked(True)  # força marcar se não estiver

        sockets = self.smp_sockets_spinbox.value()
        cores = self.smp_cores_spinbox.value()
        threads = self.smp_threads_spinbox.value()

        total_vcpus = sockets * cores * threads

        if total_vcpus > self.host_cpu_count:
            QMessageBox.warning(
                self,
                "Aviso de vCPUs",
                f"O número total de vCPUs ({total_vcpus}) excede o total de CPUs lógicas do host ({self.host_cpu_count})."
            )

        self.app_context.update_config({
            "smp_sockets": sockets,
            "smp_cores": cores,
            "smp_threads": threads,
            "smp_cpus": total_vcpus,
            "smp_passthrough": False,
            "topology_enabled": True,
        })

        self.smp_passthrough_checkbox.setChecked(False)
        self.smp_cpu_spinbox.setValue(total_vcpus)
        self.hardware_config_changed.emit()
        
    def load_cpu_list(self):

        self.cpu_combo.blockSignals(True)
        self.cpu_combo.clear()

        if not self.qemu_helper:
            self.cpu_combo.addItem("default")
            self.cpu_combo.blockSignals(False)
            return

        cpu_output = self.qemu_helper.get_info("cpu_help")
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
                cpu_name = line.split()[0]
                cpus.append(cpu_name)

        if not cpus:
            cpus = ["default"]

        self.cpu_combo.addItems(cpus)

        selected_cpu = self.app_context.config.get("cpu", "")
        if selected_cpu in cpus:
            self.cpu_combo.setCurrentText(selected_cpu)
        else:
            self.cpu_combo.setCurrentIndex(0)

        self.cpu_combo.blockSignals(False)
        
    def load_machine_list(self):

        self.machine_combo.blockSignals(True)
        self.machine_combo.clear()

        if not self.qemu_helper:
            self.machine_combo.addItems(["pc", "q35", "isapc"])
            self.machine_combo.blockSignals(False)
            return

        machine_output = self.qemu_helper.get_info("machine_help")
        machines = []
        for line in machine_output.splitlines():
            line = line.strip()
            if line and not line.startswith("Supported machines are:"):
                machine_name = line.split()[0]
                if machine_name not in machines:
                    machines.append(machine_name)

        if not machines:
            machines = ["pc", "q35", "isapc"]

        self.machine_combo.addItems(machines)

        selected_machine = self.app_context.config.get("machine_type", "pc")
        if selected_machine in machines:
            self.machine_combo.setCurrentText(selected_machine)
        else:
            self.machine_combo.setCurrentText("pc")

        self.machine_combo.blockSignals(False)

    def load_config_to_ui(self):
        self.app_context.block_all_signals(True)
        try:
            cfg = self.app_context.config

            self.cpu_combo.blockSignals(True)
            self.machine_combo.blockSignals(True)
            self.mem_combo.blockSignals(True)
            self.kvm_accel_checkbox.blockSignals(True)
            self.smp_passthrough_checkbox.blockSignals(True)
            self.smp_cpu_spinbox.blockSignals(True)
            self.cpu_mitigations_checkbox.blockSignals(True)
            self.topology_checkbox.blockSignals(True)
            self.smp_sockets_spinbox.blockSignals(True)
            self.smp_cores_spinbox.blockSignals(True)
            self.smp_threads_spinbox.blockSignals(True)

            self.smp_passthrough_checkbox.setVisible(self.cpu_combo.currentText() == "host")

            cpu = cfg.get("cpu", "")
            if cpu and cpu in [self.cpu_combo.itemText(i) for i in range(self.cpu_combo.count())]:
                self.cpu_combo.setCurrentText(cpu)
            elif self.cpu_combo.count() > 0:
                self.cpu_combo.setCurrentIndex(0)

            machine = cfg.get("machine_type", "pc")
            if machine in [self.machine_combo.itemText(i) for i in range(self.machine_combo.count())]:
                self.machine_combo.setCurrentText(machine)
            else:
                self.machine_combo.setCurrentText("pc")

            mem = str(cfg.get("memory_mb", "1024"))
            if mem in [self.mem_combo.itemText(i) for i in range(self.mem_combo.count())]:
                self.mem_combo.setCurrentText(mem)
            else:
                self.mem_combo.setCurrentText("1024")

            kvm_enabled = cfg.get("kvm_acceleration", False)
            self.kvm_accel_checkbox.setChecked(kvm_enabled)

            smp_passthrough = cfg.get("smp_passthrough", False)
            self.smp_passthrough_checkbox.setChecked(smp_passthrough)

            if smp_passthrough:
                half_cores = max(1, self.host_cpu_count // 2)
                self.smp_cpu_spinbox.setValue(half_cores)
                self.smp_cpu_spinbox.setEnabled(False)
            else:
                smp_cpus = cfg.get("smp_cpus", 2)
                self.smp_cpu_spinbox.setValue(smp_cpus if smp_cpus >= 1 else 2)
                self.smp_cpu_spinbox.setEnabled(True)

            mitigations = cfg.get("cpu_mitigations", False)
            self.cpu_mitigations_checkbox.setChecked(mitigations)

            topology_enabled = cfg.get("topology_enabled", False)
            self.topology_checkbox.setChecked(topology_enabled)

            self.smp_sockets_spinbox.setEnabled(topology_enabled)
            self.smp_cores_spinbox.setEnabled(topology_enabled)
            self.smp_threads_spinbox.setEnabled(topology_enabled)
            self.on_topology_toggled(self.topology_checkbox.isChecked())

            sockets = cfg.get("smp_sockets", 1)
            cores = cfg.get("smp_cores", 1)
            threads = cfg.get("smp_threads", 1)

            self.smp_sockets_spinbox.setValue(sockets)
            self.smp_cores_spinbox.setValue(cores)
            self.smp_threads_spinbox.setValue(threads)

            self.cpu_combo.blockSignals(False)
            self.machine_combo.blockSignals(False)
            self.mem_combo.blockSignals(False)
            self.kvm_accel_checkbox.blockSignals(False)
            self.smp_passthrough_checkbox.blockSignals(False)
            self.smp_cpu_spinbox.blockSignals(False)
            self.cpu_mitigations_checkbox.blockSignals(False)
            self.topology_checkbox.blockSignals(False)
            self.smp_sockets_spinbox.blockSignals(False)
            self.smp_cores_spinbox.blockSignals(False)
            self.smp_threads_spinbox.blockSignals(False)
        finally:
            self.app_context.block_all_signals(False)
        
    def qemu_direct_parse(self, cmdline: list[str]):
        """
        Extrai opções relacionadas à CPU, SMP, machine, memória, KVM e atualiza UI.
        """
        cpu_name = None
        smp_val = None
        machine_type = None
        memory_mb = None
        kvm_enabled = False
        cpu_mitigations = False

        i = 0
        while i < len(cmdline):
            arg = cmdline[i]

            if arg == '-cpu' and i+1 < len(cmdline):
                cpu_name = cmdline[i+1]
                i += 2
                continue

            if arg == '-smp' and i+1 < len(cmdline):
                smp_val = cmdline[i+1]
                i += 2
                continue

            if arg == '-machine' and i+1 < len(cmdline):
                machine_type = cmdline[i+1]
                i += 2
                continue

            if arg == '-m' and i+1 < len(cmdline):
                mem_str = cmdline[i+1]
                try:
                    if mem_str.lower().endswith('g'):
                        memory_mb = int(float(mem_str[:-1]) * 1024)
                    elif mem_str.lower().endswith('m'):
                        memory_mb = int(mem_str[:-1])
                    else:
                        memory_mb = int(mem_str)
                except Exception:
                    memory_mb = None
                i += 2
                continue

            if arg == '-enable-kvm':
                kvm_enabled = True
                i += 1
                continue

            if arg == '-cpu-mitigations' and i+1 < len(cmdline):
                cpu_mitigations = cmdline[i+1].lower() == 'on'
                i += 2
                continue

            i += 1

        # Atualiza UI de acordo
        if cpu_name:
            if cpu_name in [self.cpu_combo.itemText(i) for i in range(self.cpu_combo.count())]:
                self.cpu_combo.setCurrentText(cpu_name)
            else:
                self.cpu_combo.setCurrentIndex(0)
        else:
            self.cpu_combo.setCurrentIndex(0)

        if smp_val:
            parts = smp_val.split(',')
            total_cpus = int(parts[0])

            sockets = cores = threads = 1
            for part in parts[1:]:
                if '=' in part:
                    k, v = part.split('=')
                    if k == 'sockets':
                        sockets = int(v)
                    elif k == 'cores':
                        cores = int(v)
                    elif k == 'threads':
                        threads = int(v)

            self.smp_cpu_spinbox.setValue(total_cpus)
            self.smp_sockets_spinbox.setValue(sockets)
            self.smp_cores_spinbox.setValue(cores)
            self.smp_threads_spinbox.setValue(threads)

            self.topology_checkbox.setChecked(len(parts) > 1)

        if machine_type:
            if machine_type in [self.machine_combo.itemText(i) for i in range(self.machine_combo.count())]:
                self.machine_combo.setCurrentText(machine_type)
            else:
                self.machine_combo.setCurrentText("pc")

        if memory_mb:
            mem_str = str(memory_mb)
            if mem_str in [self.mem_combo.itemText(i) for i in range(self.mem_combo.count())]:
                self.mem_combo.setCurrentText(mem_str)
            else:
                self.mem_combo.setCurrentText("1024")

        self.kvm_accel_checkbox.setChecked(kvm_enabled)
        self.cpu_mitigations_checkbox.setChecked(cpu_mitigations)

    def qemu_reverse_parse(self) -> list[str]:
        """
        Constrói a lista de argumentos QEMU para CPU, SMP, machine, memória, KVM.
        """
        args = []

        cpu = self.cpu_combo.currentText()
        if cpu and cpu != "default":
            args.extend(["-cpu", cpu])

        if self.smp_passthrough_checkbox.isChecked():
            args.extend(["-cpu", "host"])
        else:
            smp_cpus = self.smp_cpu_spinbox.value()
            if self.topology_checkbox.isChecked():
                sockets = self.smp_sockets_spinbox.value()
                cores = self.smp_cores_spinbox.value()
                threads = self.smp_threads_spinbox.value()
                smp_value = f"{smp_cpus},sockets={sockets},cores={cores},threads={threads}"
            else:
                smp_value = str(smp_cpus)
            args.extend(["-smp", smp_value])

        machine = self.machine_combo.currentText()
        if machine:
            args.extend(["-machine", machine])

        mem = self.mem_combo.currentText()
        if mem:
            args.extend(["-m", mem])

        if self.kvm_accel_checkbox.isChecked():
            args.append("-enable-kvm")

        if self.cpu_mitigations_checkbox.isChecked():
            args.extend(["-cpu-mitigations", "on"])
        else:
            args.extend(["-cpu-mitigations", "off"])

        return args

