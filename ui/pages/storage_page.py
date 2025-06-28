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
import os
from typing import Any

class DriveWidget(QWidget):
    drive_changed = pyqtSignal()
    drive_removed = pyqtSignal(str)

    def __init__(self, drive_id, parent=None):
        super().__init__(parent)
        self.drive_id = drive_id
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
        self.if_combo.setToolTip("Tipo de interface do drive (controladora).")
        self.if_combo.addItems(["none", "ide", "scsi", "sd", "mtd", "virtio"])
        self.if_combo.currentTextChanged.connect(self.if_combo_changed) # Alterado aqui para lógica mais específica
        self.main_layout.addWidget(self.if_combo)

        self.remove_button = QPushButton("Remover")
        self.remove_button.clicked.connect(self._remove_self)
        self.main_layout.addWidget(self.remove_button)

        self.update_format_visibility(emit_signal=False)

    def on_drive_changed(self, *args, **kwargs): 
        self.drive_changed.emit() # type: ignore

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
                # Garante que o formato seja setado apenas se o combo tiver a opção
                if self.format_combo.findText(ext[1:]) != -1:
                    self.format_combo.setCurrentText(ext[1:])
            self.on_drive_changed() # Emite sinal após atualização pelo browse

    def update_format_visibility(self, emit_signal=True):
        is_cd = self.is_cdrom_checkbox.isChecked()
        self.format_combo.setVisible(not is_cd)
        if is_cd:
            # Se for CD-ROM, a interface IDE é comum. 'none' para -if do -drive
            # mas o -device correspondente geralmente será ide-cd.
            # Vamos manter o combo de interface para o usuário escolher o controlador do device.
            pass
        elif self.format_combo.currentText() == "iso":
            # Isso impede que "iso" fique selecionado no combo de formato para discos rígidos
            # Se a extensão do arquivo não for .iso e ele não for um cdrom, reverte para qcow2
            current_path = self.path_edit.text().strip()
            ext = os.path.splitext(current_path)[1].lower()
            if ext != ".iso" and self.format_combo.currentText() == "iso":
                 self.format_combo.setCurrentText("qcow2") # Fallback padrão

        if emit_signal:
            self.on_drive_changed()

    def if_combo_changed(self, text):
        # Lógica adicional, se necessária, quando a interface muda
        self.on_drive_changed()

    def _remove_self(self):
        self.drive_removed.emit(self.drive_id) # type: ignore

    def get_drive_data(self):
        # Adapta para retornar dados no formato que QemuConfig espera para -drive e -device
        path = self.path_edit.text().strip()
        if not path:
            return None

        is_cdrom = self.is_cdrom_checkbox.isChecked()
        interface_type = self.if_combo.currentText() # Ex: 'ide', 'virtio', 'scsi', 'none'
        
        drive_data = {
            'file': path,
            'id': self.drive_id,
            'if': interface_type, # QemuConfig usa 'if' para inferir o -device
            'media': 'cdrom' if is_cdrom else 'disk'
        }
        if not is_cdrom:
            drive_data['format'] = self.format_combo.currentText()

        return drive_data

    def set_drive_data(self, data):
        # Bloqueia sinais dos widgets durante o set para evitar loops
        # Use um contexto de bloqueio para garantir que os sinais sejam reativados
        with self.block_signals_context([self.path_edit, self.is_cdrom_checkbox, self.format_combo, self.if_combo]):
            self.path_edit.setText(data.get('file', ''))

            is_cdrom = (data.get('media', 'disk') == 'cdrom')
            self.is_cdrom_checkbox.setChecked(is_cdrom)

            if not is_cdrom:
                format_val = data.get('format', 'qcow2')
                if self.format_combo.findText(format_val) != -1:
                    self.format_combo.setCurrentText(format_val)
                else:
                    self.format_combo.setCurrentText("qcow2") # Fallback padrão para formato
            else:
                # Se é CD-ROM, garantir que o formato combo esteja em um estado consistente,
                # mesmo que invisível. Pode ser útil para lógica interna.
                if self.format_combo.findText("raw") != -1: # ISOs geralmente são tratadas como raw
                    self.format_combo.setCurrentText("raw")


            # A interface 'if' vem do -drive OU do -device, o parser deve normalizar isso.
            # Aqui, setamos a interface exibida na UI.
            if_val = data.get('if', 'none') # QemuConfig.all_args['drive'][x]['if']
            if self.if_combo.findText(if_val) != -1:
                self.if_combo.setCurrentText(if_val)
            else:
                self.if_combo.setCurrentText("none") # Fallback padrão para interface

            self.update_format_visibility(emit_signal=False)

    # Novo método para bloquear sinais de forma segura
    def block_signals_context(self, widgets):
        class SignalBlocker: 
            def __enter__(self_blocker): 
                for w in widgets: 
                    w.blockSignals(True) 
            def __exit__(self_blocker, exc_type, exc_val, exc_tb): 
                    w.blockSignals(False) #type: ignore
        return SignalBlocker() 
    
class FloppyWidget(QWidget):
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
            self.on_floppy_changed() # Emite sinal após atualização pelo browse

    def on_floppy_changed(self, *args, **kwargs):
        self.floppy_changed.emit() # type: ignore

    def _remove_self(self):
        self.floppy_removed.emit(self.unit) #type: ignore

    def get_floppy_data(self):
        path = self.path_edit.text().strip()
        if not path:
            return None
        # Retorna o dicionário no formato que QemuConfig espera para floppies
        return {'file': path, 'unit': self.unit}

    def set_floppy_data(self, data):
        # Bloqueia sinais dos widgets durante o set para evitar loops
        self.path_edit.blockSignals(True)
        self.path_edit.setText(data.get('file', ''))
        self.path_edit.blockSignals(False)


class StoragePage(QWidget):
    storage_config_changed = pyqtSignal() # Sinal para notificar o AppContext sobre mudanças na StoragePage

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.qemu_config = self.app_context.qemu_config
        self.drive_widgets = []
        self.floppy_widgets = []
        self.drive_count = 0
        self.floppy_count = 0
        self.loading = False # Flag para controlar o carregamento programático da UI

        self.setup_ui()
        self.bind_signals()

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
        # Conecta o sinal de atualização da QemuConfig do AppContext para o parse reverso
        self.app_context.qemu_config_updated.connect(self.load_from_qemu_config)

    def _on_storage_changed(self):
        """
        Chamado quando um DriveWidget ou FloppyWidget é alterado, adicionado ou removido.
        Coleta os dados atuais e notifica o AppContext sobre a mudança.
        """
        if self.loading: # Evita que a página dispare sinais durante o carregamento programático
            return
        
        # Coleta os dados de todos os widgets de drive
        current_drives_data = [w.get_drive_data() for w in self.drive_widgets if w.get_drive_data()]
        
        # Coleta os dados de todos os widgets de floppy
        current_floppies_data = [w.get_floppy_data() for w in self.floppy_widgets if w.get_floppy_data()]

        # Prepara o dicionário de atualização para o AppContext, usando as chaves esperadas pela QemuConfig
        config_update = {
            "drive": current_drives_data,  # Chave 'drive' para HDs/CDs
            "floppy": current_floppies_data, # Chave 'floppy' para disquetes
        }
        
        # Envia a atualização para o AppContext.
        # O AppContext.update_qemu_config_from_page() irá mesclar esses dados
        # com a QemuConfig existente e, por sua vez, emitirá qemu_config_updated.
        self.qemu_config.update_qemu_config_from_page(config_update)
        self.app_context.mark_modified()
        
        # O sinal storage_config_changed.emit() será acionado implicitamente
        # pelo app_context.on_page_config_changed que é o slot para este sinal.

    def _connect_drive_signals(self, widget: DriveWidget):
        widget.drive_changed.connect(self._on_storage_changed) #type: ignore
        widget.drive_removed.connect(self._on_drive_removed) #type: ignore

    def _connect_floppy_signals(self, widget: FloppyWidget):
        widget.floppy_changed.connect(self._on_storage_changed) #type: ignore
        widget.floppy_removed.connect(self._on_floppy_removed) #type: ignore

    def add_drive(self):
        drive_id = f"disk{self.drive_count}"
        self.drive_count += 1
        widget = DriveWidget(drive_id)
        self._connect_drive_signals(widget)
        self.drive_widgets.append(widget)
        self.drive_container.addWidget(widget)
        widget.show()
        self._on_storage_changed() # Aciona a atualização da config após adicionar

    def add_floppy(self):
        unit = self.floppy_count
        self.floppy_count += 1
        widget = FloppyWidget(unit)
        self._connect_floppy_signals(widget)
        self.floppy_widgets.append(widget)
        self.floppy_container.addWidget(widget)
        widget.show()
        self._on_storage_changed() # Aciona a atualização da config após adicionar

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

    def clear_all_drives(self):
        for widget in self.drive_widgets:
            widget.drive_changed.disconnect(self._on_storage_changed) # type: ignore
            widget.drive_removed.disconnect(self._on_drive_removed) # type: ignore
            self.drive_container.removeWidget(widget)  # Remove do layout
            widget.setParent(None)
            widget.deleteLater()
        self.drive_widgets.clear()
        self.drive_count = 0

    def clear_all_floppies(self):
        for widget in self.floppy_widgets:
            widget.floppy_changed.disconnect(self._on_storage_changed) # Desconecta para evitar triggers
            widget.floppy_removed.disconnect(self._on_floppy_removed)
            self.floppy_container.removeWidget(widget)  # Remove do layout
            widget.setParent(None)
            widget.deleteLater()
        self.floppy_widgets.clear()
        self.floppy_count = 0

    def load_from_qemu_config(self, qemu_config_obj: Any):
        """
        Popula a GUI da StoragePage com base nos argumentos QEMU parseados contidos no QemuConfig.
        Este método será chamado pelo AppContext.qemu_config_updated.
        """
        self.loading = True # Inicia o modo de carregamento da página para bloquear sinais
        
        # Usa o contexto de bloqueio de sinais do AppContext para toda a operação de carregamento
        with self.app_context.signal_blocker():
            # Limpa todos os widgets existentes antes de carregar os novos
            self.clear_all_drives()
            self.clear_all_floppies()

            qemu_args_dict = qemu_config_obj.get("all_args", [])

            # Carrega drives (HDs/CDs)
            parsed_drives_data = qemu_args_dict.get('drive', []) if isinstance(qemu_args_dict, dict) else [] 
            for drive_entry in parsed_drives_data:
                if isinstance(drive_entry, dict):
                    # Adiciona o drive usando o método que não dispara sinais imediatamente
                    self._add_drive_with_data_no_signal(drive_entry)

            # Carrega floppies
            parsed_floppies_data = qemu_args_dict.get('floppy', []) if isinstance(qemu_args_dict, dict) else []
            for floppy_entry in parsed_floppies_data:
                if isinstance(floppy_entry, dict):
                    # Adiciona o floppy usando o método que não dispara sinais imediatamente
                    self._add_floppy_with_data_no_signal(floppy_entry)

        self.loading = False # Finaliza o modo de carregamento da página
        
        # Após carregar tudo, força uma atualização para garantir que a OverviewPage
        # recalcule a linha de comando completa.
        # Isso é importante porque os widgets foram atualizados sem disparar sinais individuais.
        self.storage_config_changed.emit()

    def _add_drive_with_data_no_signal(self, data: dict):
        # Garante que o ID do drive seja único ou reutilizado se fornecido
        drive_id = data.get('id')
        if not drive_id:
            drive_id = f"disk{self.drive_count}"
            data['id'] = drive_id # Atualiza o dicionário de dados com o ID gerado

        self.drive_count += 1
        widget = DriveWidget(drive_id)
        widget.set_drive_data(data) # set_drive_data já bloqueia/desbloqueia sinais internos do widget
        
        self._connect_drive_signals(widget) # Conecta os sinais para futuras edições pelo usuário
        self.drive_widgets.append(widget)
        self.drive_container.addWidget(widget)
        widget.show()

    def _add_floppy_with_data_no_signal(self, data: dict):
        # Garante que a unit do floppy seja única ou reutilizada se fornecida
        unit = data.get('unit')
        if unit is None: # unit pode ser 0
            unit = self.floppy_count
            data['unit'] = unit # Atualiza o dicionário de dados com a unit gerada

        self.floppy_count += 1
        widget = FloppyWidget(unit)
        widget.set_floppy_data(data) # set_floppy_data já bloqueia/desbloqueia sinais internos do widget

        self._connect_floppy_signals(widget) # Conecta os sinais para futuras edições pelo usuário
        self.floppy_widgets.append(widget)
        self.floppy_container.addWidget(widget)
        widget.show()