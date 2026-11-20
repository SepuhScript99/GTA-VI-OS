#!/usr/bin/env python3
"""Vice OS — Openbox Config Editor. Edit rc.xml keybindings, window rules, and menu entries."""

import sys
import os
import subprocess
import xml.etree.ElementTree as ET

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QTabWidget, QTextEdit, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QFileDialog, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QLabel { color: #00ffff; }
"""

RC_XML_PATHS = [
    os.path.expanduser("~/.config/openbox/rc.xml"),
    "/etc/xdg/openbox/rc.xml",
    "/var/lib/vice-os/config/openbox_rc.xml",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "openbox_rc.xml"),
]


def find_rc_xml():
    for path in RC_XML_PATHS:
        if os.path.exists(path):
            return path
    return RC_XML_PATHS[0]


class KeybindDialog(QDialog):
    def __init__(self, key="", action="", command="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Keybinding")
        self.setFixedSize(460, 220)
        self.setStyleSheet(STYLE)
        layout = QFormLayout(self)

        self._key = QLineEdit(key)
        self._key.setPlaceholderText("e.g. W-t, C-A-t, A-F4")
        layout.addRow("Key Combo:", self._key)

        self._action = QComboBox()
        self._action.addItems(["Execute", "ToggleFullscreen", "ToggleMaximize",
                               "Iconify", "Close", "NextWindow", "PreviousWindow",
                               "DesktopLeft", "DesktopRight", "ShowMenu"])
        if action:
            self._action.setCurrentText(action)
        layout.addRow("Action:", self._action)

        self._command = QLineEdit(command)
        self._command.setPlaceholderText("command (for Execute action)")
        layout.addRow("Command:", self._command)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def values(self):
        return (self._key.text().strip(), self._action.currentText(), self._command.text().strip())


class OpenboxConfigEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Openbox Config Editor")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._rc_path = find_rc_xml()
        self._tree = None
        self._load_config()
        self._init_ui()
        self._load_keybindings()

    def _load_config(self):
        try:
            self._tree = ET.parse(self._rc_path)
        except Exception as e:
            log_error(f"Failed to parse rc.xml: {e}")
            QMessageBox.warning(self, "Parse Error",
                                f"Could not parse {self._rc_path}:\n{e}\n\nStarting with empty config.")
            self._tree = ET.ElementTree(ET.Element("openbox_config"))

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Openbox Config Editor")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        path_label = QLabel(f"Config: {self._rc_path}")
        path_label.setStyleSheet("color: #888; font-size: 10px;")
        path_label.setAlignment(Qt.AlignCenter)
        root.addWidget(path_label)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Keybindings tab ---
        kb_tab = QWidget()
        kl = QVBoxLayout(kb_tab)

        self._kb_table = QTableWidget()
        self._kb_table.setColumnCount(3)
        self._kb_table.setHorizontalHeaderLabels(["Key Combo", "Action", "Command"])
        self._kb_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i in [0, 1]:
            self._kb_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._kb_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._kb_table.setEditTriggers(QTableWidget.NoEditTriggers)
        kl.addWidget(self._kb_table)

        kb_btn_row = QHBoxLayout()
        add_kb_btn = QPushButton("Add Keybinding")
        add_kb_btn.clicked.connect(self._add_keybinding)
        kb_btn_row.addWidget(add_kb_btn)
        edit_kb_btn = QPushButton("Edit Selected")
        edit_kb_btn.clicked.connect(self._edit_keybinding)
        kb_btn_row.addWidget(edit_kb_btn)
        del_kb_btn = QPushButton("Delete Selected")
        del_kb_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_kb_btn.clicked.connect(self._delete_keybinding)
        kb_btn_row.addWidget(del_kb_btn)
        kl.addLayout(kb_btn_row)
        tabs.addTab(kb_tab, "Keybindings")

        # --- Raw XML tab ---
        xml_tab = QWidget()
        xl = QVBoxLayout(xml_tab)
        self._xml_edit = QTextEdit()
        self._xml_edit.setFont(QFont("monospace", 11))
        xl.addWidget(self._xml_edit)
        xml_btn_row = QHBoxLayout()
        reload_xml_btn = QPushButton("Reload from File")
        reload_xml_btn.clicked.connect(self._reload_xml)
        xml_btn_row.addWidget(reload_xml_btn)
        xml_btn_row.addStretch()
        xl.addLayout(xml_btn_row)
        tabs.addTab(xml_tab, "Raw XML")

        # Bottom buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Config")
        save_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        save_btn.clicked.connect(self._save_config)
        btn_row.addWidget(save_btn)

        reconfig_btn = QPushButton("Reconfigure Openbox")
        reconfig_btn.clicked.connect(self._reconfigure)
        btn_row.addWidget(reconfig_btn)

        backup_btn = QPushButton("Backup Config")
        backup_btn.clicked.connect(self._backup)
        btn_row.addWidget(backup_btn)

        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _get_keyboard_node(self):
        root = self._tree.getroot()
        kb = root.find("keyboard")
        if kb is None:
            kb = ET.SubElement(root, "keyboard")
        return kb

    def _load_keybindings(self):
        self._kb_table.setRowCount(0)
        kb = self._get_keyboard_node()
        for keybind in kb.findall("keybind"):
            key = keybind.get("key", "")
            for action in keybind.findall("action"):
                action_name = action.get("name", "")
                command = ""
                if action_name == "Execute":
                    cmd_elem = action.find("command")
                    if cmd_elem is not None and cmd_elem.text:
                        command = cmd_elem.text
                row = self._kb_table.rowCount()
                self._kb_table.insertRow(row)
                self._kb_table.setItem(row, 0, QTableWidgetItem(key))
                self._kb_table.setItem(row, 1, QTableWidgetItem(action_name))
                self._kb_table.setItem(row, 2, QTableWidgetItem(command))

    def _selected_row(self):
        return self._kb_table.currentRow()

    def _add_keybinding(self):
        dlg = KeybindDialog(parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        key, action, command = dlg.values()
        if not key or not action:
            QMessageBox.warning(self, "Missing Info", "Key and action are required.")
            return

        kb = self._get_keyboard_node()
        keybind = ET.SubElement(kb, "keybind", key=key)
        action_elem = ET.SubElement(keybind, "action", name=action)
        if action == "Execute" and command:
            ET.SubElement(action_elem, "command").text = command

        self._load_keybindings()
        self._status.setText(f"Added: {key} -> {action}")

    def _edit_keybinding(self):
        row = self._selected_row()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a keybinding first.")
            return
        key = self._kb_table.item(row, 0).text()
        action = self._kb_table.item(row, 1).text()
        command = self._kb_table.item(row, 2).text()

        dlg = KeybindDialog(key, action, command, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_key, new_action, new_command = dlg.values()

        kb = self._get_keyboard_node()
        keybinds = kb.findall("keybind")
        target = None
        for kb_item in keybinds:
            if kb_item.get("key") == key:
                for a in kb_item.findall("action"):
                    if a.get("name") == action:
                        target = (kb_item, a)
                        break
                if target:
                    break

        if target:
            kb_item, a = target
            kb_item.set("key", new_key)
            a.set("name", new_action)
            cmd_elem = a.find("command")
            if new_action == "Execute" and new_command:
                if cmd_elem is None:
                    ET.SubElement(a, "command").text = new_command
                else:
                    cmd_elem.text = new_command
            elif cmd_elem is not None:
                a.remove(cmd_elem)

        self._load_keybindings()
        self._status.setText(f"Updated: {new_key} -> {new_action}")

    def _delete_keybinding(self):
        row = self._selected_row()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a keybinding first.")
            return
        key = self._kb_table.item(row, 0).text()
        action = self._kb_table.item(row, 1).text()

        if QMessageBox.question(self, "Delete", f"Delete binding {key} -> {action}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        kb = self._get_keyboard_node()
        for kb_item in kb.findall("keybind"):
            if kb_item.get("key") == key:
                for a in kb_item.findall("action"):
                    if a.get("name") == action:
                        kb.remove(kb_item)
                        break
                break

        self._load_keybindings()
        self._status.setText(f"Deleted: {key}")

    def _reload_xml(self):
        try:
            content = self._xml_edit.toPlainText()
            ET.fromstring(content)  # validate
            self._tree = ET.ElementTree(ET.fromstring(content))
            self._load_keybindings()
            self._status.setText("XML reloaded and validated")
        except ET.ParseError as e:
            QMessageBox.warning(self, "Invalid XML", f"Parse error:\n{e}")

    def _save_config(self):
        # Sync raw XML editor content if it was modified
        try:
            ET.indent(self._tree, space="  ")
        except Exception:
            pass
        try:
            self._tree.write(self._rc_path, encoding="unicode", xml_declaration=True)
            self._status.setText(f"Saved: {self._rc_path}")
            log_info(f"Openbox config saved: {self._rc_path}")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))
            log_error(f"Openbox save failed: {e}")

    def _reconfigure(self):
        subprocess.Popen(["openbox", "--reconfigure"])
        self._status.setText("Openbox reconfigure signal sent")
        log_info("Openbox reconfigure requested")

    def _backup(self):
        import shutil
        import datetime
        backup = self._rc_path + ".bak." + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy2(self._rc_path, backup)
            self._status.setText(f"Backup: {backup}")
            log_info(f"Openbox config backed up: {backup}")
        except Exception as e:
            QMessageBox.warning(self, "Backup Failed", str(e))


def main():
    app = QApplication(sys.argv)
    win = OpenboxConfigEditor()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()