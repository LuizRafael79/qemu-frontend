from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QHBoxLayout,
    QPushButton, QSpinBox, QGroupBox, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIntValidator
import multiprocessing
import os
from typing import Optional, List, Dict, Any
from app.utils.qemu_helper import QemuHelper
from app.context.app_context import AppContext
import sys
import os

# Constants for configuration keys and default values
CPU_CONFIG = "cpu"
MACHINE_TYPE_CONFIG = "machine_type"
MEMORY_MB_CONFIG = "memory_mb"
KVM_ACCEL_CONFIG = "kvm_acceleration"
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


class HardwarePage(QWidget):
    """
    A QWidget page for configuring QEMU hardware settings like CPU, memory, and machine type.
    It interacts with the main application context to load and save configuration.
    """
    hardware_config_changed = pyqtSignal()
    """Signal emitted when any hardware configuration value is changed by the user."""

    def __init__(self, app_context: AppContext):
        """
        Initializes the HardwarePage.

        Args:
            app_context: The application context for accessing shared state and configuration.
        """
        super().__init__()
        
        self.app_context = app_context
        self.qemu_helper: Optional[QemuHelper] = None
        self.host_cpu_count = multiprocessing.cpu_count()

        self._setup_ui()
        self.bind_signals()
        
        self.load_cpu_list()

    def _setup_ui(self):
        """Creates and arranges all UI widgets on the page."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel("Virtual Machine Hardware")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        self._setup_cpu_widgets(layout)
        self._setup_advanced_cpu_widgets(layout)
        self._setup_machine_and_memory_widgets(layout)
        
        self.setLayout(layout)

    def _setup_cpu_widgets(self, parent_layout: QVBoxLayout):
        """Sets up widgets for basic CPU configuration."""
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
        """Sets up widgets for advanced CPU configuration."""
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
        """Sets up widgets for CPU topology."""
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
        """Sets up widgets for machine type, memory, and KVM."""
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
        # Set validator on the line edit of the combo box
        line_edit = self.mem_combo.lineEdit()
        if line_edit is not None:
            line_edit.setValidator(QIntValidator(128, 65536))
        parent_layout.addWidget(self.mem_combo)

    def bind_signals(self):
        """Connects widget signals to their corresponding slots."""
        self.app_context.config_changed.connect(self.on_app_config_changed)

        # CPU and Topology
        self.cpu_combo.currentTextChanged.connect(self._update_cpu_config_and_ui)
        self.smp_cpu_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        self.smp_passthrough_checkbox.toggled.connect(self._update_cpu_config_and_ui)
        self.cpu_mitigations_checkbox.toggled.connect(self._update_cpu_config_and_ui)
        self.topology_checkbox.toggled.connect(self._update_cpu_config_and_ui)
        self.smp_sockets_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        self.smp_cores_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)
        self.smp_threads_spinbox.valueChanged.connect(self._update_cpu_config_and_ui)

        # Other hardware
        self.machine_combo.currentTextChanged.connect(self.on_machine_changed)
        self.mem_combo.currentTextChanged.connect(self.on_mem_changed)
        self.kvm_accel_checkbox.stateChanged.connect(self.on_kvm_changed)

    def update_qemu_helper(self):
        """Updates the QemuHelper instance based on the current application configuration."""
        config = self.app_context.config
        bin_path = ""

        custom_exec = config.get("custom_executable", "").strip()
        if custom_exec and os.path.isfile(custom_exec):
            bin_path = custom_exec
        else:
            qemu_exec_name = config.get("qemu_executable", "").strip()
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
        """
        Slot to handle global application config changes.
        Updates CPU/machine lists and reloads UI state.
        """
        self.update_qemu_helper()
        self.load_cpu_list()
        self.load_machine_list()
        self.load_config_to_ui()

    def on_cpu_changed(self, cpu_name: str):
        """Handles changes to the CPU model selection."""
        self._update_cpu_config_and_ui()
        
    def on_machine_changed(self, machine_type: str):
        """Handles changes to the machine type selection."""
        if not machine_type:
            return
        self.app_context.update_config({MACHINE_TYPE_CONFIG: machine_type})
        self.hardware_config_changed.emit()

    def on_mem_changed(self, mem_value: str):
        """Handles changes to the memory selection."""
        if not mem_value:
            return
        try:
            mem_int = int(mem_value)
            self.app_context.update_config({MEMORY_MB_CONFIG: mem_int})
            self.hardware_config_changed.emit()
        except ValueError:
            # Optionally, show a warning to the user
            return

    def on_kvm_changed(self, state: int):
        """Handles changes to the KVM acceleration checkbox."""
        enabled = (state == 2)  # Qt.Checked
        self.app_context.update_config({KVM_ACCEL_CONFIG: enabled})
        self.hardware_config_changed.emit()
        
    def on_smp_passthrough_changed(self, state: int):
        """Handles changes to the CPU passthrough checkbox."""
        self._update_cpu_config_and_ui()

    def on_smp_cpu_count_changed(self, value: int):
        """Handles changes to the vCPU count spinbox."""
        self._update_cpu_config_and_ui()

    def on_cpu_mitigations_changed(self, state: int):
        """Handles changes to the CPU mitigations checkbox."""
        self._update_cpu_config_and_ui()

    def on_topology_toggled(self, checked: bool):
        """Handles toggling the manual CPU topology definition."""
        self._update_cpu_config_and_ui()

    def on_topology_values_changed(self):
        """Handles changes to any of the CPU topology spinboxes."""
        self._update_cpu_config_and_ui()
        
    def load_cpu_list(self):
        """Loads the list of available CPUs from QEMU and populates the combo box."""
        self.cpu_combo.blockSignals(True)
        self.cpu_combo.clear()

        cpus = [DEFAULT_CPU]
        if self.qemu_helper:
            cpus = self.qemu_helper.get_cpu_list()

        self.cpu_combo.addItems(cpus)

        selected_cpu = self.app_context.config.get(CPU_CONFIG, "")
        if self.cpu_combo.findText(selected_cpu) != -1:
            self.cpu_combo.setCurrentText(selected_cpu)
        elif self.cpu_combo.count() > 0:
            self.cpu_combo.setCurrentIndex(0)

        self.cpu_combo.blockSignals(False)
        self._update_cpu_config_and_ui()
        
    def load_machine_list(self):
        """Loads the list of available machine types from QEMU."""
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

    def _set_all_signals_blocked(self, blocked: bool):
        """Blocks or unblocks signals for all configurable widgets."""
        widgets = [
            self.cpu_combo, self.machine_combo, self.mem_combo,
            self.kvm_accel_checkbox, self.smp_passthrough_checkbox,
            self.smp_cpu_spinbox, self.cpu_mitigations_checkbox,
            self.topology_checkbox, self.smp_sockets_spinbox,
            self.smp_cores_spinbox, self.smp_threads_spinbox
        ]
        for widget in widgets:
            widget.blockSignals(blocked)

    def load_config_to_ui(self):
        """Loads the current configuration from the app context and updates the UI widgets."""
        self._set_all_signals_blocked(True)
        try:
            config = self.app_context.config
            
            # CPU
            cpu = config.get(CPU_CONFIG, "")
            if self.cpu_combo.findText(cpu) != -1:
                self.cpu_combo.setCurrentText(cpu)
            elif self.cpu_combo.count() > 0:
                self.cpu_combo.setCurrentIndex(0)
            self._update_cpu_config_and_ui()

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
            self.kvm_accel_checkbox.setChecked(config.get(KVM_ACCEL_CONFIG, False))

            # SMP Passthrough and vCPUs
            smp_passthrough = config.get(SMP_PASSTHROUGH_CONFIG, False)
            self.smp_passthrough_checkbox.setChecked(smp_passthrough)
            smp_cpus = config.get(SMP_CPUS_CONFIG, 2)
            self.smp_cpu_spinbox.setValue(smp_cpus if smp_cpus >= 1 else 2)

            # Mitigations
            self.cpu_mitigations_checkbox.setChecked(config.get(CPU_MITIGATIONS_CONFIG, False))

            # Topology
            topology_enabled = config.get(TOPOLOGY_ENABLED_CONFIG, False)
            self.topology_checkbox.setChecked(topology_enabled)
            self.on_topology_toggled(topology_enabled)
            self.smp_sockets_spinbox.setValue(config.get(SMP_SOCKETS_CONFIG, 1))
            self.smp_cores_spinbox.setValue(config.get(SMP_CORES_CONFIG, 1))
            self.smp_threads_spinbox.setValue(config.get(SMP_THREADS_CONFIG, 1))

        finally:
            self._set_all_signals_blocked(False)

    def _update_cpu_config_and_ui(self):
        """
        Central function to update CPU-related UI elements and application config.
        This avoids recursion by centralizing logic and blocking signals.
        """
        # Use a guard flag to prevent recursion
        if getattr(self, "_updating_cpu_ui", False):
            return
        self._updating_cpu_ui = True

        try:
            # --- Read current UI state ---
            is_host_cpu = self.cpu_combo.currentText() == HOST_CPU
            passthrough_enabled = self.smp_passthrough_checkbox.isChecked()
            topology_enabled = self.topology_checkbox.isChecked()

            # --- Determine widget visibility and enabled states ---
            self.smp_passthrough_checkbox.setVisible(is_host_cpu)
            self.topology_group.setVisible(topology_enabled)

            # Passthrough overrides topology
            if is_host_cpu and passthrough_enabled:
                self.topology_checkbox.setEnabled(False)
                if topology_enabled:
                    self.topology_checkbox.setChecked(False)
                    topology_enabled = False
            else:
                self.topology_checkbox.setEnabled(True)

            self.smp_cpu_spinbox.setEnabled(not topology_enabled)
            
            # --- Calculate vCPUs ---
            smp_cpus = 0
            if topology_enabled:
                sockets = self.smp_sockets_spinbox.value()
                cores = self.smp_cores_spinbox.value()
                threads = self.smp_threads_spinbox.value()
                smp_cpus = sockets * cores * threads
                if self.smp_cpu_spinbox.value() != smp_cpus:
                    self.smp_cpu_spinbox.blockSignals(True)
                    self.smp_cpu_spinbox.setValue(smp_cpus)
                    self.smp_cpu_spinbox.blockSignals(False)
            elif is_host_cpu and passthrough_enabled:
                smp_cpus = max(1, self.host_cpu_count // 2)
                if self.smp_cpu_spinbox.value() != smp_cpus:
                    self.smp_cpu_spinbox.blockSignals(True)
                    self.smp_cpu_spinbox.setValue(smp_cpus)
                    self.smp_cpu_spinbox.blockSignals(False)
            else:
                smp_cpus = self.smp_cpu_spinbox.value()

            # --- Show warnings ---
            if smp_cpus > self.host_cpu_count:
                QMessageBox.warning(self, "vCPU Warning", f"vCPUs ({smp_cpus}) > host CPUs ({self.host_cpu_count}).")

            # --- Update application config ---
            config_update = {
                CPU_CONFIG: self.cpu_combo.currentText(),
                SMP_PASSTHROUGH_CONFIG: is_host_cpu and passthrough_enabled,
                CPU_MITIGATIONS_CONFIG: self.cpu_mitigations_checkbox.isChecked(),
                TOPOLOGY_ENABLED_CONFIG: topology_enabled,
                SMP_CPUS_CONFIG: smp_cpus,
                SMP_SOCKETS_CONFIG: self.smp_sockets_spinbox.value(),
                SMP_CORES_CONFIG: self.smp_cores_spinbox.value(),
                SMP_THREADS_CONFIG: self.smp_threads_spinbox.value(),
            }
            self.app_context.update_config(config_update)

        finally:
            self._updating_cpu_ui = False
        
        self.hardware_config_changed.emit()

    def _set_cpu_signals_blocked(self, blocked: bool):
        """Blocks or unblocks signals for CPU-related widgets."""
        widgets = [
            self.cpu_combo, self.smp_passthrough_checkbox,
            self.smp_cpu_spinbox, self.cpu_mitigations_checkbox,
            self.topology_checkbox, self.smp_sockets_spinbox,
            self.smp_cores_spinbox, self.smp_threads_spinbox
        ]
        for widget in widgets:
            widget.blockSignals(blocked)
