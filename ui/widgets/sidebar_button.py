from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import QSize, Qt
import qtawesome as qta

class SidebarButton(QPushButton):
    def __init__(self, text, icon_name, *, text_color="#f8f8f2", icon_color="#8be9fd",
                 selected_bg="rgba(80, 92, 144, 0.3)", hover_bg="#505c90"):
        super().__init__(text)
        self.icon_name = icon_name
        self.text_color = text_color
        self.icon_color = icon_color
        self.selected_bg = selected_bg
        self.hover_bg = hover_bg

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(qta.icon(self.icon_name, color=self.icon_color))
        self.setIconSize(QSize(18, 18))
        self.setStyleSheet(self.build_style(normal=True))

    def build_style(self, normal=True, hover=False, checked=False):
        bg_color = "transparent"
        if checked:
            bg_color = self.selected_bg
        elif hover:
            bg_color = self.hover_bg

        return f"""
            SidebarButton {{
                text-align: left;
                padding: 8px 12px;
                border: none;
                background-color: {bg_color};
                color: {self.text_color};
                border-radius: 4px;
            }}
        """

    def update_icon_color(self, color):
        self.setIcon(qta.icon(self.icon_name, color=color))

    def enterEvent(self, event):
        if not self.isChecked():
            self.update_icon_color("white")
            self.setStyleSheet(self.build_style(hover=True))
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.isChecked():
            self.update_icon_color("white")
            self.setStyleSheet(self.build_style(checked=True))
        else:
            self.update_icon_color(self.icon_color)
            self.setStyleSheet(self.build_style())
        super().leaveEvent(event)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        if checked:
            self.update_icon_color("white")
            self.setStyleSheet(self.build_style(checked=True))
        else:
            self.update_icon_color(self.icon_color)
            self.setStyleSheet(self.build_style())
