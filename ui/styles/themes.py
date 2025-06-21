# This file is part of qemu-frontend.
# Copyright (C) 2025 Luiz Rafael
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License v3.
# See the LICENSE file for more details.
#
# This file contains the stylesheets for dark and light themes used in the application.
# It provides functions to retrieve the stylesheets as strings.
# -*- coding: utf-8 -*-
def get_dark_stylesheet():
    return """
        QWidget { 
            font-size: 14px; 
            background-color: #282a36; 
            color: #f8f8f2;
        }
        QLabel { color: #f8f8f2; }
        QPushButton {
            background-color: #44475a;
            color: #f8f8f2;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #6272a4;
        }
        QComboBox {
            background-color: #44475a;
            color: #f8f8f2;
            border: 1px solid #6272a4;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QLineEdit {
            background-color: #44475a;
            color: #f8f8f2;
            border: 1px solid #6272a4;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QTextEdit {
            background-color: #1e1f29;
            color: #f8f8f2;
            border: 1px solid #6272a4;
            border-radius: 4px;
        }
        QTabWidget::pane {
            border: 1px solid #6272a4;
            border-radius: 4px;
            background: #282a36;
        }
        QTabBar::tab {
            background: #44475a;
            color: #f8f8f2;
            padding: 6px 12px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #6272a4;
        }
    """

def get_light_stylesheet():
    return """
        QWidget {
            font-size: 14px;
            background-color: #f0f0f0;
            color: #1a1a1a;
        }
        QLabel {
            color: #1a1a1a;
        }
        QPushButton {
            background-color: #e0e0e0;
            color: #1a1a1a;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #c0c0c0;
        }
        QComboBox {
            background-color: #ffffff;
            color: #1a1a1a;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #1a1a1a;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QTextEdit {
            background-color: #ffffff;
            color: #1a1a1a;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
        }
        QTabWidget::pane {
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            background: #f0f0f0;
        }
        QTabBar::tab {
            background: #e0e0e0;
            color: #1a1a1a;
            padding: 6px 12px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #c0c0c0;
        }
    """
