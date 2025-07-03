# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QHBoxLayout, QFormLayout
)
from PyQt5.QtCore import Qt

from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from app.context.app_context import AppContext


class NetworkInterfaceWidget(QWidget):
    def __init__(self, idx: int, parent=None):
        super().__init__(parent)
        self.index = idx
        self.form_layout = QFormLayout()
        self.setLayout(self.form_layout)

        self.id_edit = QComboBox()
        self.id_edit.setEditable(True)
        self.id_edit.setEditText(f"net{idx}")

        self.backend_combo = QComboBox()
        self.backend_combo.addItems([
            "user", "tap", "bridge", "vde", "socket", "l2tpv3", "none"
        ])

        self.device_combo = QComboBox()
        self.device_combo.addItems([
            "virtio-net-pci", "e1000", "rtl8139", "ne2k_pci", "vmxnet3"
        ])

        self.form_layout.addRow("ID:", self.id_edit)
        self.form_layout.addRow("Backend:", self.backend_combo)
        self.form_layout.addRow("Device Model:", self.device_combo)

    def get_config(self) -> Dict[str, str]:
        return {
            "id": self.id_edit.currentText(),
            "backend": self.backend_combo.currentText(),
            "model": self.device_combo.currentText()
        }

    def set_config(self, data: Dict[str, str]):
        self.id_edit.setEditText(data.get("id", f"net{self.index}"))
        backend = data.get("backend", "user")
        device = data.get("model", "virtio-net-pci")

        if backend in [self.backend_combo.itemText(i) for i in range(self.backend_combo.count())]:
            self.backend_combo.setCurrentText(backend)

        if device in [self.device_combo.itemText(i) for i in range(self.device_combo.count())]:
            self.device_combo.setCurrentText(device)


class NetworkPage(QWidget):
    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.qemu_config = app_context.qemu_config
        self.interface_widgets: List[NetworkInterfaceWidget] = []

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.title = QLabel("Network Interfaces")
        self.title.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.main_layout.addWidget(self.title)

        self.interfaces_group = QGroupBox("Interfaces")
        self.interfaces_layout = QVBoxLayout()
        self.interfaces_group.setLayout(self.interfaces_layout)
        self.main_layout.addWidget(self.interfaces_group)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Interface")
        self.btn_remove = QPushButton("Remove Last")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        self.main_layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self.add_interface)
        self.btn_remove.clicked.connect(self.remove_last_interface)

        self.load_from_qemu_config()

    def add_interface(self, config: Dict[str, str] = {}):
        idx = len(self.interface_widgets)
        widget = NetworkInterfaceWidget(idx)
        if config:
            widget.set_config(config)
        self.interfaces_layout.addWidget(widget)
        self.interface_widgets.append(widget)
        self.update_qemu_config()

    def remove_last_interface(self):
        if self.interface_widgets:
            widget = self.interface_widgets.pop()
            widget.setParent(None) # type: ignore
            widget.deleteLater()
            self.update_qemu_config()

    def update_qemu_config(self):
        devices = []
        netdevs = []

        for iface in self.interface_widgets:
            cfg = iface.get_config()
            netdev_str = f"{cfg['backend']},id={cfg['id']}"
            device_str = f"{cfg['model']},netdev={cfg['id']}"

            netdevs.append(netdev_str)
            devices.append(device_str)

        self.qemu_config.update_qemu_config_from_page({
            "netdev": netdevs,
            "device": devices
        })

        self.app_context.qemu_config_updated.emit(self.qemu_config)
        self.app_context.mark_modified()

    def load_from_qemu_config(self):
        self.clear_all_interfaces()

        netdevs = self.qemu_config.get("netdev", [])
        devices = self.qemu_config.get("device", [])

        if isinstance(netdevs, str):
            netdevs = [netdevs]
        if isinstance(devices, str):
            devices = [devices]

        parsed_configs = []
        for nd, dev in zip(netdevs, devices):
            try:
                backend, id_part = nd.split(",", 1)
                id_value = id_part.split("=", 1)[1]

                model, netdev_part = dev.split(",", 1)
                netdev_id = netdev_part.split("=", 1)[1]

                if id_value != netdev_id:
                    continue

                parsed_configs.append({
                    "id": id_value,
                    "backend": backend.strip(),
                    "model": model.strip()
                })
            except Exception as e:
                print(f"[WARN] Skipping invalid net config: {nd}, {dev} - {e}")

        if parsed_configs:
            for cfg in parsed_configs:
                self.add_interface(cfg)
        else:
            self.add_interface()

    def clear_all_interfaces(self):
        for w in self.interface_widgets:
            w.setParent(None) # type: ignore
            w.deleteLater()
        self.interface_widgets.clear()
