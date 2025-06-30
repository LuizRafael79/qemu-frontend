# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QComboBox, QCheckBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from app.utils.qemu_helper import QemuConfig
from app.context.app_context import AppContext
import os, traceback
from typing import Any, List, Dict
from contextlib import contextmanager


# --- Início das Classes de Widget (DriveWidget, FloppyWidget) ---

class DriveWidget(QWidget):
    drive_changed = pyqtSignal()
    device_changed = pyqtSignal()
    drive_removed = pyqtSignal(str)
    device_removed = pyqtSignal(str)

    def __init__(self, drive_id, parent=None):
        super().__init__(parent)
        self.drive_id = drive_id
        # ... (O resto do __init__ pode ser mantido igual ao da versão anterior)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(f"Caminho do arquivo para {drive_id}")
        self.path_edit.setToolTip("Especifique o caminho para a imagem de disco (.qcow2, .img, .iso, etc.).")
        self.path_edit.textChanged.connect(self.on_drive_changed)
        self.main_layout.addWidget(self.path_edit)
        self.browse_button = QPushButton("Procurar")
        self.browse_button.clicked.connect(self._browse_file)
        self.main_layout.addWidget(self.browse_button)
        self.is_cdrom_checkbox = QCheckBox("CD-ROM")
        self.is_cdrom_checkbox.setToolTip("Marque se este drive for um CD-ROM.")
        self.is_cdrom_checkbox.toggled.connect(lambda checked: self.update_format_visibility(emit_signal=True))
        self.is_cdrom_checkbox.toggled.connect(self.on_drive_changed)
        self.main_layout.addWidget(self.is_cdrom_checkbox)
        self.format_combo = QComboBox()
        self.format_combo.setToolTip("Formato da imagem de disco. 'raw' é o padrão para a maioria.")
        self.format_combo.addItems(["qcow2", "raw", "vdi", "vmdk"])
        self.format_combo.currentTextChanged.connect(self.on_drive_changed)
        self.main_layout.addWidget(self.format_combo)
        self.if_combo = QComboBox()
        self.if_combo.setToolTip("Tipo de interface do drive (controladora que gerará o -device).")
        self.if_combo.addItems(["none", "ide", "sata", "scsi", "virtio", "usb"])
        self.if_combo.currentTextChanged.connect(self.if_combo_changed)
        self.main_layout.addWidget(self.if_combo)
        self.remove_button = QPushButton("Remover")
        self.remove_button.clicked.connect(self._remove_self)
        self.main_layout.addWidget(self.remove_button)
        self.update_format_visibility(emit_signal=False)


    def on_drive_changed(self, *args, **kwargs):
        self.drive_changed.emit() 
        self.device_changed.emit() 

    def _browse_file(self):
        # ... (sem alterações, pode manter sua versão)
        if self.is_cdrom_checkbox.isChecked():
            filter_str = "Imagens de CD-ROM (*.iso *.img *.cue *.bin);;Todos os Arquivos (*)"
        else:
            filter_str = "Imagens de Disco (*.qcow2 *.img *.raw *.vdi *.vmdk);;Todos os Arquivos (*)"

        file_path, _ = QFileDialog.getOpenFileName(self, f"Selecionar Arquivo para {self.drive_id}", "", filter_str)
        if file_path:
            self.path_edit.setText(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".iso":
                self.is_cdrom_checkbox.setChecked(True)
            elif ext in [".qcow2", ".vdi", ".vmdk"]:
                if self.format_combo.findText(ext[1:]) != -1:
                    self.format_combo.setCurrentText(ext[1:])
            self.on_drive_changed()

    def update_format_visibility(self, emit_signal=True):
        # ... (sem alterações, pode manter sua versão)
        is_cd = self.is_cdrom_checkbox.isChecked()
        self.format_combo.setVisible(not is_cd)
        if is_cd:
            if self.format_combo.findText("raw") != -1:
                self.format_combo.setCurrentText("raw")
        else:
            current_path = self.path_edit.text().strip()
            ext = os.path.splitext(current_path)[1].lower()
            if ext != ".iso" and self.format_combo.currentText() == "iso":
                self.format_combo.setCurrentText("qcow2")

        if emit_signal:
            self.on_drive_changed()

    def if_combo_changed(self, text):
        self.on_drive_changed()

    def _remove_self(self):
        self.drive_removed.emit(self.drive_id) 

    def get_drive_data(self) -> Dict[str, Any] | None:
        path = self.path_edit.text().strip()
        if not path:
            return None
        is_cdrom = self.is_cdrom_checkbox.isChecked()
        drive_data = {
            'file': path,
            'id': self.drive_id,
            'if': 'none',
            'media': 'cdrom' if is_cdrom else 'disk'
        }
        if not is_cdrom:
            drive_data['format'] = self.format_combo.currentText()
        return drive_data

    def get_device_data(self) -> Dict[str, Any] | None:
        iface = self.if_combo.currentText()
        if iface == "none":
            return None
        is_cdrom = self.is_cdrom_checkbox.isChecked()
        devmap_cdrom = {"ide": "ide-cd", "sata": "sata-cd", "scsi": "scsi-cd", "usb": "usb-storage"}
        devmap_disk = {"ide": "ide-hd", "sata": "sata-hd", "scsi": "scsi-hd", "virtio": "virtio-blk-pci", "usb": "usb-storage"}
        devmap = devmap_cdrom if is_cdrom else devmap_disk
        interface_name = devmap.get(iface)
        if not interface_name:
            return None
        return {"interface": interface_name, "drive": self.drive_id}

    def set_drive_data(self, data: Dict[str, Any]):
        with self.block_signals_context([self.path_edit, self.is_cdrom_checkbox, self.format_combo]):
            self.path_edit.setText(data.get('file', ''))
            is_cdrom = (data.get('media', 'disk') == 'cdrom')
            self.is_cdrom_checkbox.setChecked(is_cdrom)
            if not is_cdrom:
                format_val = data.get('format', 'qcow2')
                if self.format_combo.findText(format_val) != -1:
                    self.format_combo.setCurrentText(format_val)
            self.update_format_visibility(emit_signal=False)

    def set_device_data(self, data: Dict[str, Any]):
        """
        CORREÇÃO: Este método agora apenas configura a interface, sem
        modificar o estado de 'CD-ROM', que é definido por set_drive_data.
        """
        interface_name = data.get("interface", "")
        devmap_rev = {
            "scsi-hd": "scsi", "scsi-cd": "scsi", "virtio-blk-pci": "virtio",
            "ide-hd": "ide", "ide-cd": "ide", "sata-hd": "sata", "sata-cd": "sata",
            "usb-storage": "usb"
        }
        iface = devmap_rev.get(interface_name, "none")
        with self.block_signals_context([self.if_combo]):
            if self.if_combo.findText(iface) != -1:
                self.if_combo.setCurrentText(iface)
            else:
                self.if_combo.setCurrentText("none")

    @contextmanager
    def block_signals_context(self, widgets):
        for w in widgets:
            w.blockSignals(True)
        try:
            yield
        finally:
            for w in widgets:
                w.blockSignals(False)
class FloppyWidget(QWidget):
    # Nenhuma alteração lógica necessária aqui, mantido como está.
    floppy_changed = pyqtSignal()
    floppy_removed = pyqtSignal(int)

    def __init__(self, unit, parent=None):
        super().__init__(parent)
        self.unit = unit
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(f"Unidade {unit}:")
        self.main_layout.addWidget(self.label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(f"Caminho do arquivo para a unidade {unit}")
        self.path_edit.textChanged.connect(self.on_floppy_changed)
        self.main_layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("Procurar")
        self.browse_button.clicked.connect(self._browse_file)
        self.main_layout.addWidget(self.browse_button)

        self.remove_button = QPushButton("Remover")
        self.remove_button.clicked.connect(self._remove_self)
        self.main_layout.addWidget(self.remove_button)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar Imagem de Disquete para Unidade {self.unit}",
            "",
            "Imagens de Disquete (*.img *.ima *.vfd);;Todos os Arquivos (*)"
        )
        if file_path:
            self.path_edit.setText(file_path)
            self.on_floppy_changed()

    def on_floppy_changed(self, *args, **kwargs):
        self.floppy_changed.emit() 

    def _remove_self(self):
        self.floppy_removed.emit(self.unit) 

    def get_floppy_data(self):
        path = self.path_edit.text().strip()
        if not path:
            return None
        return {'file': path, 'unit': self.unit}

    def set_floppy_data(self, data):
        self.path_edit.blockSignals(True)
        self.path_edit.setText(data.get('file', ''))
        self.path_edit.blockSignals(False)

# --- Fim das Classes de Widget ---


class StoragePage(QWidget):
    storage_config_changed = pyqtSignal()  # Sinal para notificar sobre mudanças na StoragePage

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.qemu_config = self.app_context.qemu_config
        self.drive_widgets: List[DriveWidget] = []
        self.floppy_widgets: List[FloppyWidget] = []
        self.drive_count = 0
        self.floppy_count = 0
        self.loading = False

        self.setup_ui()
        self.bind_signals()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # ... (seu código de UI continua aqui, sem alterações)
        self.title_label = QLabel("Virtual Machine Storage")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(QLabel("Drives (HD/CD):"))
        self.btn_add_drive = QPushButton("Adicionar Drive")
        self.btn_add_drive.clicked.connect(self.add_drive)
        self.main_layout.addWidget(self.btn_add_drive)
        self.drive_container = QVBoxLayout()
        self.main_layout.addLayout(self.drive_container)
        self.main_layout.addWidget(QLabel("Drives de Disquete:"))
        self.btn_add_floppy = QPushButton("Adicionar Disquete")
        self.btn_add_floppy.clicked.connect(self.add_floppy)
        self.main_layout.addWidget(self.btn_add_floppy)
        self.floppy_container = QVBoxLayout()
        self.main_layout.addLayout(self.floppy_container)


    def bind_signals(self):
        self.app_context.qemu_config_updated.connect(self.load_from_qemu_config)

    def _on_storage_changed(self):
        """
        CORREÇÃO: Este método agora só é chamado por interação do usuário.
        Ele coleta os dados de todos os widgets e informa o contexto da aplicação
        que houve uma modificação a ser salva.
        """
        if self.loading:
            return
        
        try:
            drives_to_save = [d for d in (w.get_drive_data() for w in self.drive_widgets) if d]
            devices_to_save = [d for d in (w.get_device_data() for w in self.drive_widgets) if d]
            floppies_to_save = [d for d in (w.get_floppy_data() for w in self.floppy_widgets) if d]

            config_update = {
                "drive": drives_to_save or [],
                "device": devices_to_save or [],
                "floppy": floppies_to_save or [],
            }
            
            self.qemu_config.update_qemu_config_from_page(config_update)
            self.app_context.mark_modified()

            overview_page = self.app_context.get_page("overview")
            if overview_page:
                overview_page.refresh_display_from_qemu_config()

        except Exception as e:
            # Adicionado para ajudar a depurar qualquer erro inesperado durante a atualização.
            import traceback
            traceback.print_exc()

    def _connect_drive_signals(self, widget: DriveWidget):
        widget.drive_changed.connect(self._on_storage_changed) 
        widget.device_changed.connect(self._on_storage_changed)
        widget.drive_removed.connect(self._on_drive_removed) 
        widget.device_removed.connect(self._on_drive_removed) 

    def _connect_floppy_signals(self, widget: FloppyWidget):
        widget.floppy_changed.connect(self._on_storage_changed) 
        widget.floppy_removed.connect(self._on_floppy_removed) 

    def add_drive(self, is_loading: bool = False):
        drive_id = f"disk{self.drive_count}"
        self.drive_count += 1
        widget = DriveWidget(drive_id)
        self._connect_drive_signals(widget)
        self.drive_widgets.append(widget)
        self.drive_container.addWidget(widget)
        widget.show()
        # Só dispara o sinal de mudança se não estiver no meio do carregamento
        if not is_loading:
            self._on_storage_changed()

    def add_floppy(self, is_loading: bool = False):
        unit = self.floppy_count
        self.floppy_count += 1
        widget = FloppyWidget(unit)
        self._connect_floppy_signals(widget)
        self.floppy_widgets.append(widget)
        self.floppy_container.addWidget(widget)
        widget.show()
        if not is_loading:
            self._on_storage_changed()

    def _on_drive_removed(self, drive_id):
        widget_to_remove = next((w for w in self.drive_widgets if w.drive_id == drive_id), None)
        if widget_to_remove:
            self.drive_widgets.remove(widget_to_remove)
            widget_to_remove.setParent(None) # type: ignore
            widget_to_remove.deleteLater()
            self._on_storage_changed()

    def _on_floppy_removed(self, unit):
        widget_to_remove = next((w for w in self.floppy_widgets if w.unit == unit), None)
        if widget_to_remove:
            self.floppy_widgets.remove(widget_to_remove)
            widget_to_remove.setParent(None) # type: ignore
            widget_to_remove.deleteLater()
            self._on_storage_changed()

    def clear_all_drives(self):
        # Desconecta os sinais ANTES de deletar para evitar disparos indesejados
        for widget in self.drive_widgets:
            widget.drive_changed.disconnect() 
            widget.device_changed.disconnect() 
            widget.drive_removed.disconnect() 
            widget.device_removed.disconnect() 
            self.drive_container.removeWidget(widget)
            widget.setParent(None) # type: ignore
            widget.deleteLater()
        self.drive_widgets.clear()
        self.drive_count = 0

    def clear_all_floppies(self):
        for widget in self.floppy_widgets:
            widget.floppy_changed.disconnect() 
            widget.floppy_removed.disconnect() 
            self.floppy_container.removeWidget(widget)
            widget.setParent(None) # type: ignore
            widget.deleteLater()
        self.floppy_widgets.clear()
        self.floppy_count = 0

    def load_from_qemu_config(self, qemu_config_obj: Any):
        self.loading = True
        
        try:
            self.clear_all_drives()
            self.clear_all_floppies()

            qemu_args_dict = getattr(qemu_config_obj, 'all_args', {})
            
            all_drives_data = qemu_args_dict.get("drive", [])
            if isinstance(all_drives_data, dict):
                all_drives_data = [all_drives_data]

            hdd_cdrom_drives = []
            floppies_defined_as_drive = []
            for drive_entry in all_drives_data:
                if isinstance(drive_entry, dict) and drive_entry.get('if') == 'floppy':
                    floppies_defined_as_drive.append(drive_entry)
                else:
                    hdd_cdrom_drives.append(drive_entry)

            devices_data = qemu_args_dict.get("device", [])
            if isinstance(devices_data, dict):
                devices_data = [devices_data]
            
            drives_map = {d.get('id'): d for d in hdd_cdrom_drives if isinstance(d, dict) and 'id' in d}

            storage_devices = [
                dev for dev in devices_data
                if isinstance(dev, dict) and 'drive' in dev
            ]
            
            for device_entry in storage_devices:
                drive_id = device_entry.get('drive')
                if drive_id and drive_id in drives_map:
                    drive_data = drives_map.pop(drive_id)
                    self._add_drive_with_data_no_signal(drive_data, device_entry)

            for drive_id, drive_data in drives_map.items():
                self._add_drive_with_data_no_signal(drive_data, None)

            legacy_floppies = qemu_args_dict.get("floppy", [])
            if isinstance(legacy_floppies, dict):
                legacy_floppies = [legacy_floppies]
                
            all_floppy_data = legacy_floppies + floppies_defined_as_drive

            for floppy_entry in all_floppy_data:
                if isinstance(floppy_entry, dict):
                    self._add_floppy_with_data_no_signal(floppy_entry)

        except Exception:
            # --- PONTO MAIS IMPORTANTE ---
            # Se qualquer erro ocorrer no bloco 'try', ele será capturado aqui
            # e o traceback completo será impresso no console, sem derrubar o app.
            print("\n--- ERRO FATAL CAPTURADO NA STORAGEPAGE ---")
            traceback.print_exc()
            print("-------------------------------------------\n")

        finally:
            # Este bloco sempre será executado, garantindo que a flag 'loading'
            # seja desativada mesmo se ocorrer um erro.
            self.loading = False

    def _add_drive_with_data_no_signal(self, drive_data: Dict[str, Any], device_data: Dict[str, Any] | None):
        drive_id = drive_data.get('id')
        if not drive_id: drive_id = f"disk{self.drive_count}"
        
        try:
            num = int(drive_id.replace("disk", ""))
            if num >= self.drive_count: self.drive_count = num + 1
        except (ValueError, TypeError):
            self.drive_count += 1

        widget = DriveWidget(drive_id)
        # Ordem de população é importante: primeiro o drive, depois o device.
        widget.set_drive_data(drive_data)
        if device_data:
            widget.set_device_data(device_data)

        self._connect_drive_signals(widget)
        self.drive_widgets.append(widget)
        self.drive_container.addWidget(widget)
        widget.show()

    def _add_floppy_with_data_no_signal(self, data: Dict[str, Any]):
        raw_unit = data.get('unit')
        unit = -1 # Valor padrão inválido

        if raw_unit is not None:
            try:
                # Tenta converter a unidade para inteiro
                unit = int(raw_unit)
            except (ValueError, TypeError):
                print(f"AVISO: Valor de 'unit' inválido para disquete: {raw_unit}. Ignorando.")
                # Se a conversão falhar, não cria o widget
                return
        
        # Se 'unit' não foi fornecido no dicionário, usa o contador
        if unit == -1:
            unit = self.floppy_count

        if unit >= self.floppy_count:
            self.floppy_count = unit + 1

        widget = FloppyWidget(unit)
        widget.set_floppy_data(data)
        self._connect_floppy_signals(widget)
        self.floppy_widgets.append(widget)
        self.floppy_container.addWidget(widget)
        widget.show()