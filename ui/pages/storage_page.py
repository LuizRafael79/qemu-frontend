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
from app.utils.qemu_helper import QemuHelper, QemuInfoCache
from app.context.app_context import AppContext
import os
import re

class DriveWidget(QWidget):
    drive_changed = pyqtSignal()
    drive_removed = pyqtSignal(str)

    def __init__(self, drive_id, parent=None):
        super().__init__(parent)
        self.drive_id = drive_id
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(f"Caminho do arquivo para {drive_id}")
        self.path_edit.setToolTip("Especifique o caminho para a imagem de disco (.qcow2, .img, .iso, etc.).")
        self.path_edit.textChanged.connect(self.drive_changed.emit)
        self.layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("Procurar")
        self.browse_button.clicked.connect(self._browse_file)
        self.layout.addWidget(self.browse_button)

        self.is_cdrom_checkbox = QCheckBox("CD-ROM")
        self.is_cdrom_checkbox.setToolTip("Marque se este drive for um CD-ROM.")
        self.is_cdrom_checkbox.toggled.connect(lambda checked: self.update_format_visibility(emit_signal=True))
        self.is_cdrom_checkbox.toggled.connect(self.drive_changed.emit)
        self.layout.addWidget(self.is_cdrom_checkbox)

        self.format_combo = QComboBox()
        self.format_combo.setToolTip("Formato da imagem de disco. 'raw' é o padrão para a maioria.")
        self.format_combo.addItems(["qcow2", "raw", "vdi", "vmdk"])
        self.format_combo.currentTextChanged.connect(self.drive_changed.emit)
        self.layout.addWidget(self.format_combo)

        self.if_combo = QComboBox()
        self.if_combo.setToolTip("Tipo de interface do drive (controladora).")
        self.if_combo.addItems(["none", "ide", "scsi", "sd", "mtd", "virtio"])
        self.if_combo.currentTextChanged.connect(self.drive_changed.emit)
        self.layout.addWidget(self.if_combo)

        self.remove_button = QPushButton("Remover")
        self.remove_button.clicked.connect(self._remove_self)
        self.layout.addWidget(self.remove_button)

        self.update_format_visibility(emit_signal=False)

    def _browse_file(self):
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
                self.format_combo.setCurrentText(ext[1:])  # remove o ponto

    def update_format_visibility(self, emit_signal=True):
        is_cd = self.is_cdrom_checkbox.isChecked()
        self.format_combo.setVisible(not is_cd)
        if is_cd:
            self.if_combo.setCurrentText("none")
        elif self.format_combo.currentText() == "iso":
            self.format_combo.setCurrentText("qcow2")

        if emit_signal:
            self.drive_changed.emit()

    def _remove_self(self):
        self.drive_removed.emit(self.drive_id)

    def get_drive_data(self):
        path = self.path_edit.text().strip()
        if not path:
            return None

        is_cdrom = self.is_cdrom_checkbox.isChecked()
        media_type = 'cdrom' if is_cdrom else 'disk'

        drive_data = {
            'id': self.drive_id,
            'file': path,
            'if': self.if_combo.currentText(),
            'media': media_type
        }
        if not is_cdrom:
            drive_data['format'] = self.format_combo.currentText()

        return drive_data

    def set_drive_data(self, data):
        # Bloqueia sinais dos widgets durante o set
        for w in [self.path_edit, self.is_cdrom_checkbox, self.format_combo, self.if_combo]:
            w.blockSignals(True)

        self.path_edit.setText(data.get('file', ''))

        is_cdrom = (data.get('media', 'disk') == 'cdrom')
        self.is_cdrom_checkbox.setChecked(is_cdrom)

        if not is_cdrom:
            format_val = data.get('format', 'qcow2')
            if self.format_combo.findText(format_val) != -1:
                self.format_combo.setCurrentText(format_val)

        if_val = data.get('if', 'none')
        if self.if_combo.findText(if_val) != -1:
            self.if_combo.setCurrentText(if_val)

        self.update_format_visibility(emit_signal=False)

        for w in [self.path_edit, self.is_cdrom_checkbox, self.format_combo, self.if_combo]:
            w.blockSignals(False)


class FloppyWidget(QWidget):
    floppy_changed = pyqtSignal()
    floppy_removed = pyqtSignal(int)

    def __init__(self, unit, parent=None):
        super().__init__(parent)
        self.unit = unit
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(f"Unidade {unit}:")
        self.layout.addWidget(self.label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(f"Caminho do arquivo para a unidade {unit}")
        self.path_edit.textChanged.connect(self.floppy_changed.emit)
        self.layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("Procurar")
        self.browse_button.clicked.connect(self._browse_file)
        self.layout.addWidget(self.browse_button)

        self.remove_button = QPushButton("Remover")
        self.remove_button.clicked.connect(self._remove_self)
        self.layout.addWidget(self.remove_button)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar Imagem de Disquete para Unidade {self.unit}",
            "",
            "Imagens de Disquete (*.img *.ima *.vfd);;Todos os Arquivos (*)"
        )
        if file_path:
            self.path_edit.setText(file_path)

    def _remove_self(self):
        self.floppy_removed.emit(self.unit)

    def get_floppy_data(self):
        path = self.path_edit.text().strip()
        if not path:
            return None
        return {'unit': self.unit, 'file': path}

    def set_floppy_data(self, data):
        self.path_edit.blockSignals(True)
        self.path_edit.setText(data.get('file', ''))
        self.path_edit.blockSignals(False)


class StoragePage(QWidget):
    storage_config_changed = pyqtSignal()

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.drive_widgets = []
        self.floppy_widgets = []
        self.drive_count = 0
        self.floppy_count = 0
        self.loading = False

        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        self.app_context.config_loaded.connect(self.load_config_to_ui)
        self.storage_config_changed.connect(self.app_context.config_changed.emit)


    # ---------- Parse direto CLI string -> widgets ----------

    def qemu_direct_parse(self, cmdline_str):
        tokens = self.app_context.split_shell_command(cmdline_str)

        # Evita disparos de sinal ao popular UI
        self.loading = True
        self.clear_all_drives()
        self.clear_all_floppies()

        drive_map = {}
        device_map = {}
        extra_args = []

        i = 0
        while i < len(tokens):
            arg = tokens[i]

            if arg == "-drive" and i + 1 < len(tokens):
                drive_str = tokens[i + 1]
                parts = drive_str.split(",")
                info = {
                    "file": "",
                    "id": "",
                    "if": "none",
                    "readonly": False,
                    "format": "raw",
                    "unit": None,
                    "media": "disk",
                }
                for p in parts:
                    if "=" not in p:
                        continue
                    k, v = p.split("=", 1)
                    if k == "file":
                        info["file"] = v
                    elif k == "id":
                        info["id"] = v
                    elif k == "if":
                        info["if"] = v
                    elif k == "readonly":
                        info["readonly"] = (v.lower() == "on")
                    elif k == "format":
                        info["format"] = v
                    elif k == "unit":
                        try:
                            info["unit"] = int(v)
                        except Exception:
                            info["unit"] = None
                    elif k == "media":
                        info["media"] = v
                drive_map[info["id"]] = info
                i += 2
                continue

            elif arg == "-device" and i + 1 < len(tokens):
                dev_str = tokens[i + 1]
                m = re.search(r"drive=([^, ]+)", dev_str)
                if m:
                    drive_id = m.group(1)
                    dev_type = dev_str.lower().split(',')[0].strip()

                    # Novo bloco genérico
                    interface = "none"
                    media = "disk"

                    if "cd" in dev_type:
                        media = "cdrom"
                    if "ide" in dev_type:
                        interface = "ide"
                    elif "scsi" in dev_type:
                        interface = "scsi"
                    elif "virtio" in dev_type:
                        interface = "virtio"
                    elif "sd" in dev_type:
                        interface = "sd"
                    elif "mtd" in dev_type:
                        interface = "mtd"

                    device_map[drive_id] = {
                        "media": media,
                        "if": interface,
                        "device_type": dev_type
                    }
                else:
                    extra_args.append(arg)
                    extra_args.append(tokens[i + 1])
                i += 2
                continue


            else:
                extra_args.append(arg)
                i += 1

        scsi_needed = False
        virtio_needed = False

        for did, info in drive_map.items():
            dev_info = device_map.get(did, {})

            media = dev_info.get("media", info.get("media", "disk"))
            interface = dev_info.get("if") or "none"

            if interface == "scsi":
                scsi_needed = True
            if interface == "virtio":
                virtio_needed = True

            if interface == "floppy" or did.startswith("floppy"):
                self.add_floppy({
                    "unit": info.get("unit", 0),
                    "file": info.get("file", "")
                })
            else:
                file = info.get("file", "")
                ext = file.split('.')[-1].lower() if '.' in file else ''
                fmt = info.get("format", "raw")

                if media == "cdrom":
                    fmt = "raw"
                elif ext == "qcow2":
                    fmt = "qcow2"
                else:
                    fmt = "raw"

                self.add_drive({
                    "file": file,
                    "id": did,
                    "if": interface,
                    "media": media,
                    "format": fmt,
                })

        self.loading = False
        self._on_storage_changed()

        self.app_context.update_config({
            "scsi_controller_needed": scsi_needed,
            "virtio_controller_needed": virtio_needed,
            "extra_args": extra_args
        })
        return extra_args

    def qemu_reverse_parse_args(self):
        args = []

        for index, widget in enumerate(self.drive_widgets):
            data = widget.get_drive_data()
            if not data:
                continue

            file = data['file']
            drive_id = data['id']
            interface = data['if']
            media = data['media']
            ext = file.split('.')[-1].lower() if '.' in file else ''

            # Detectar formato
            if media == 'cdrom':
                fmt = 'raw'  # CD-ROMs geralmente são .iso -> raw
            elif ext == 'qcow2':
                fmt = 'qcow2'
            else:
                fmt = 'raw'

            # Monta -drive
            parts = [
                f"file={file}",
                f"id={drive_id}",
                f"if=none",  # Sempre "none", interface vai no -device
                f"format={fmt}"
            ]
            if media == 'cdrom':
                parts.append("media=cdrom")

            args.append("-drive")
            args.append(",".join(parts))

            # Monta -device correspondente
            dev_type = f"{interface}-cd" if media == "cdrom" else f"{interface}-hd"
            args.append("-device")
            args.append(f"{dev_type},drive={drive_id}")

        for widget in self.floppy_widgets:
            data = widget.get_floppy_data()
            if not data:
                continue
            args.append("-drive")
            args.append(f"file={data['file']},if=floppy,unit={data['unit']}")

        return args        
  
    def args_list_to_multiline_str(self, args_list):
        lines = []
        i = 0
        while i < len(args_list):
            part = args_list[i]
            if i + 1 < len(args_list) and not args_list[i+1].startswith("-"):
                lines.append(f"{part} {args_list[i+1]} \\")
                i += 2
            else:
                lines.append(f"{part} \\")
                i += 1
        if lines:
            lines[-1] = lines[-1].rstrip(" \\")
        return "\n".join(lines)
  
    def _on_storage_changed(self):
        if self.loading:
            return
        drives = [w.get_drive_data() for w in self.drive_widgets if w.get_drive_data()]
        floppies = [w.get_floppy_data() for w in self.floppy_widgets if w.get_floppy_data()]

        args = self.qemu_reverse_parse_args()
        qemu_args_str = self.args_list_to_multiline_str(args)

        self.app_context.update_config({
            "drives": drives,
            "floppies": floppies,
            "qemu_args": qemu_args_str
        })
        self.storage_config_changed.emit()    

    def _connect_drive_signals(self, widget: DriveWidget):
        widget.drive_changed.connect(self._on_storage_changed)
        widget.drive_removed.connect(self._on_drive_removed)

    def _connect_floppy_signals(self, widget: FloppyWidget):
        widget.floppy_changed.connect(self._on_storage_changed)
        widget.floppy_removed.connect(self._on_floppy_removed)

    def add_drive(self, data=None):
        drive_id = f"disk{self.drive_count}"
        self.drive_count += 1
        widget = DriveWidget(drive_id)
        if data:
            widget.set_drive_data(data)
        self._connect_drive_signals(widget)
        self.drive_widgets.append(widget)
        self.drive_container.addWidget(widget)
        widget.show()
        self._on_storage_changed()

    def add_floppy(self, data=None):
        unit = self.floppy_count
        self.floppy_count += 1
        widget = FloppyWidget(unit)
        if data:
            widget.set_floppy_data(data)
        self._connect_floppy_signals(widget)
        self.floppy_widgets.append(widget)
        self.floppy_container.addWidget(widget)
        widget.show()
        self._on_storage_changed()

    def _remove_drive_by_id(self, drive_id):
        for widget in self.drive_widgets:
            if widget.drive_id == drive_id:
                self.drive_widgets.remove(widget)
                widget.setParent(None)
                widget.deleteLater()
                break
        self._on_storage_changed()

    def _remove_floppy_by_unit(self, unit):
        for widget in self.floppy_widgets:
            if widget.unit == unit:
                self.floppy_widgets.remove(widget)
                widget.setParent(None)
                widget.deleteLater()
                break
        self._on_storage_changed()

    def _on_drive_removed(self, drive_id):
        self._remove_drive_by_id(drive_id)

    def _on_floppy_removed(self, unit):
        self._remove_floppy_by_unit(unit)

    def _clear_all_widgets(self):
        for w in self.drive_widgets:
            w.setParent(None)
            w.deleteLater()
        self.drive_widgets.clear()
        self.drive_count = 0

        for w in self.floppy_widgets:
            w.setParent(None)
            w.deleteLater()
        self.floppy_widgets.clear()
        self.floppy_count = 0      

    def clear_all_drives(self): # <--- AQUI ESTÁ ELA!
        for widget in self.drive_widgets:
            widget.drive_removed.disconnect(self._on_drive_removed) # Desconecta para evitar chamada duplicada
            widget.deleteLater()
        self.drive_widgets.clear()
        self.drive_count = 0

    def clear_all_floppies(self): # <--- E AQUI ESTÁ ELA!
        for widget in self.floppy_widgets:
            widget.floppy_removed.disconnect(self._on_floppy_removed) # Desconecta para evitar chamada duplicada
            widget.deleteLater()
        self.floppy_widgets.clear()
        self.floppy_count = 0

    def load_config_to_ui(self):
        self.loading = True # Inicia o modo de carregamento da página
        self.blockSignals(True)
        self.clear_all_drives()
        self.clear_all_floppies()

        for data in self.app_context.config.get("drives", []):
            self._add_drive_without_signals(data)

        for data in self.app_context.config.get("floppies", []):
            self._add_floppy_without_signals(data)

        self.loading = False # Finaliza o modo de carregamento da página
        self.blockSignals(False)

    def _add_drive_without_signals(self, data):
        drive_id = f"disk{self.drive_count}"
        self.drive_count += 1
        widget = DriveWidget(drive_id)
        # bloqueia sinais para evitar disparos no load
        for w in [widget.path_edit, widget.is_cdrom_checkbox, widget.format_combo, widget.if_combo]:
            w.blockSignals(True)
        widget.set_drive_data(data)
        for w in [widget.path_edit, widget.is_cdrom_checkbox, widget.format_combo, widget.if_combo]:
            w.blockSignals(False)
        self._connect_drive_signals(widget)
        self.drive_widgets.append(widget)
        self.drive_container.addWidget(widget)
        widget.show()

    def _add_floppy_without_signals(self, data):
        unit = self.floppy_count
        self.floppy_count += 1
        widget = FloppyWidget(unit)
        widget.path_edit.blockSignals(True)
        widget.set_floppy_data(data)
        widget.path_edit.blockSignals(False)
        self._connect_floppy_signals(widget)
        self.floppy_widgets.append(widget)
        self.floppy_container.addWidget(widget)
        widget.show()

