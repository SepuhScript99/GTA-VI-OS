#!/usr/bin/env python3
"""Vice OS — Openbox Config Editor. Edit rc.xml keybindings, window rules, and menu entries."""

import datetime
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640

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


def _xml_ns(root):
    if root is not None and root.tag.startswith("{"):
        return root.tag.split("}", 1)[0][1:]
    return ""


def _qname(ns, name):
    return f"{{{ns}}}{name}" if ns else name


class KeybindDialog(QDialog):
    def __init__(self, key="", action="", command="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Keybinding")
        self.setMinimumSize(460, 220)
        vt.apply_app_theme(self)
        layout = QFormLayout(self)

        self._key = QLineEdit(key)
        self._key.setPlaceholderText("e.g. W-t, C-A-t, A-F4")
        layout.addRow("Key Combo:", self._key)

        self._action = QComboBox()
        self._action.addItems([
            "Execute", "ToggleFullscreen", "ToggleMaximize", "Iconify", "Close",
            "NextWindow", "PreviousWindow", "DesktopLeft", "DesktopRight", "ShowMenu",
        ])
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
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        vt.apply_app_theme(self)
        self._rc_path = find_rc_xml()
        self._tree = None
        self._bindings = []
        self._load_config()
        self._init_ui()
        self._load_keybindings()
        self._sync_xml_editor()

    def _load_config(self):
        try:
            self._tree = ET.parse(self._rc_path)
        except Exception as e:
            log_error(f"Failed to parse rc.xml: {e}")
            QMessageBox.warning(
                self, "Parse Error",
                f"Could not parse {self._rc_path}:\n{e}\n\nStarting with empty config.",
            )
            self._tree = ET.ElementTree(ET.Element("openbox_config"))

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Openbox Config Editor",
            f"Config: {self._rc_path}",
            icon_name="preferences-system-windows",
            badge_text="RC.XML",
            badge_variant="aqua",
            parent=self,
        ))

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        kb_tab = QWidget()
        kl = QVBoxLayout(kb_tab)

        self._kb_table = QTableWidget()
        self._kb_table.setColumnCount(3)
        self._kb_table.setHorizontalHeaderLabels(["Key Combo", "Action", "Command"])
        self._kb_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (0, 1):
            self._kb_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._kb_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._kb_table.setEditTriggers(QTableWidget.NoEditTriggers)
        kl.addWidget(self._kb_table)

        kb_btn_row = QHBoxLayout()
        add_kb_btn = vt.make_button("Add Keybinding", "primary", parent=kb_tab)
        add_kb_btn.clicked.connect(self._add_keybinding)
        kb_btn_row.addWidget(add_kb_btn)
        edit_kb_btn = vt.make_button("Edit Selected", "secondary", parent=kb_tab)
        edit_kb_btn.clicked.connect(self._edit_keybinding)
        kb_btn_row.addWidget(edit_kb_btn)
        del_kb_btn = vt.make_button("Delete Selected", "danger", parent=kb_tab)
        del_kb_btn.clicked.connect(self._delete_keybinding)
        kb_btn_row.addWidget(del_kb_btn)
        kl.addLayout(kb_btn_row)
        self._tabs.addTab(kb_tab, "Keybindings")

        xml_tab = QWidget()
        xl = QVBoxLayout(xml_tab)
        self._xml_edit = QTextEdit()
        self._xml_edit.setFont(QFont("monospace", 11))
        xl.addWidget(self._xml_edit)
        xml_btn_row = QHBoxLayout()
        apply_xml_btn = vt.make_button("Apply Raw XML", "primary", parent=xml_tab)
        apply_xml_btn.clicked.connect(self._apply_raw_xml)
        xml_btn_row.addWidget(apply_xml_btn)
        reload_xml_btn = vt.make_button("Reload from File", "secondary", parent=xml_tab)
        reload_xml_btn.clicked.connect(self._reload_from_file)
        xml_btn_row.addWidget(reload_xml_btn)
        xml_btn_row.addStretch()
        xl.addLayout(xml_btn_row)
        self._tabs.addTab(xml_tab, "Raw XML")

        btn_row = QHBoxLayout()
        save_btn = vt.make_button("Save Config", "primary", parent=self)
        save_btn.clicked.connect(self._save_config)
        btn_row.addWidget(save_btn)

        reconfig_btn = vt.make_button("Reconfigure Openbox", "secondary", parent=self)
        reconfig_btn.clicked.connect(self._reconfigure)
        btn_row.addWidget(reconfig_btn)

        backup_btn = vt.make_button("Backup Config", "secondary", parent=self)
        backup_btn.clicked.connect(self._backup)
        btn_row.addWidget(backup_btn)

        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _get_keyboard_node(self):
        root = self._tree.getroot()
        ns = _xml_ns(root)
        kb = root.find(_qname(ns, "keyboard"))
        if kb is None:
            kb = ET.SubElement(root, _qname(ns, "keyboard"))
        return kb, ns

    def _load_keybindings(self):
        self._kb_table.setRowCount(0)
        self._bindings = []
        kb, ns = self._get_keyboard_node()
        for keybind in kb.findall(_qname(ns, "keybind")):
            key = keybind.get("key", "")
            for action in keybind.findall(_qname(ns, "action")):
                action_name = action.get("name", "")
                command = ""
                if action_name == "Execute":
                    cmd_elem = action.find(_qname(ns, "command"))
                    if cmd_elem is not None and cmd_elem.text:
                        command = cmd_elem.text
                self._bindings.append((keybind, action, ns))
                row = self._kb_table.rowCount()
                self._kb_table.insertRow(row)
                self._kb_table.setItem(row, 0, QTableWidgetItem(key))
                self._kb_table.setItem(row, 1, QTableWidgetItem(action_name))
                self._kb_table.setItem(row, 2, QTableWidgetItem(command))

    def _sync_xml_editor(self):
        try:
            root = self._tree.getroot()
            ns = _xml_ns(root)
            if ns:
                ET.register_namespace("", ns)
            self._xml_edit.setPlainText(ET.tostring(root, encoding="unicode"))
        except Exception:
            pass

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

        kb, ns = self._get_keyboard_node()
        keybind = ET.SubElement(kb, _qname(ns, "keybind"), key=key)
        action_elem = ET.SubElement(keybind, _qname(ns, "action"), name=action)
        if action == "Execute" and command:
            ET.SubElement(action_elem, _qname(ns, "command")).text = command

        self._load_keybindings()
        self._sync_xml_editor()
        self._status.setText(f"Added: {key} -> {action}")

    def _edit_keybinding(self):
        row = self._selected_row()
        if row < 0 or row >= len(self._bindings):
            QMessageBox.warning(self, "No Selection", "Select a keybinding first.")
            return
        kb_item, act_elem, ns = self._bindings[row]
        key = self._kb_table.item(row, 0).text()
        action = self._kb_table.item(row, 1).text()
        command = self._kb_table.item(row, 2).text()

        dlg = KeybindDialog(key, action, command, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_key, new_action, new_command = dlg.values()
        if not new_key or not new_action:
            return

        kb_item.set("key", new_key)
        act_elem.set("name", new_action)
        cmd_elem = act_elem.find(_qname(ns, "command"))
        if new_action == "Execute" and new_command:
            if cmd_elem is None:
                ET.SubElement(act_elem, _qname(ns, "command")).text = new_command
            else:
                cmd_elem.text = new_command
        elif cmd_elem is not None:
            act_elem.remove(cmd_elem)

        self._load_keybindings()
        self._sync_xml_editor()
        self._status.setText(f"Updated: {new_key} -> {new_action}")

    def _delete_keybinding(self):
        row = self._selected_row()
        if row < 0 or row >= len(self._bindings):
            QMessageBox.warning(self, "No Selection", "Select a keybinding first.")
            return
        kb_item, act_elem, ns = self._bindings[row]
        key = self._kb_table.item(row, 0).text()
        action = self._kb_table.item(row, 1).text()

        if QMessageBox.question(
            self, "Delete", f"Delete binding {key} -> {action}?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        kb, _ = self._get_keyboard_node()
        kb_item.remove(act_elem)
        if not kb_item.findall(_qname(ns, "action")):
            kb.remove(kb_item)

        self._load_keybindings()
        self._sync_xml_editor()
        self._status.setText(f"Deleted: {key}")

    def _apply_raw_xml(self):
        try:
            content = self._xml_edit.toPlainText()
            root = ET.fromstring(content)
            self._tree = ET.ElementTree(root)
            self._load_keybindings()
            self._status.setText("Raw XML applied and validated")
            return True
        except ET.ParseError as e:
            QMessageBox.warning(self, "Invalid XML", f"Parse error:\n{e}")
            return False

    def _reload_from_file(self):
        self._load_config()
        self._load_keybindings()
        self._sync_xml_editor()
        self._status.setText(f"Reloaded: {self._rc_path}")

    def _save_config(self):
        if self._tabs.currentIndex() == 1 and not self._apply_raw_xml():
            return
        target = self._rc_path
        parent_dir = os.path.dirname(target)
        if (os.path.exists(target) and not os.access(target, os.W_OK)) or (
            not os.path.exists(target) and parent_dir and not os.access(parent_dir, os.W_OK)
        ):
            target = RC_XML_PATHS[0]
            self._rc_path = target
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            root = self._tree.getroot()
            ns = _xml_ns(root)
            if ns:
                ET.register_namespace("", ns)
            if hasattr(ET, "indent"):
                ET.indent(self._tree, space="  ")
            self._tree.write(target, encoding="unicode", xml_declaration=True)
            self._sync_xml_editor()
            self._status.setText(f"Saved: {target}")
            log_info(f"Openbox config saved: {target}")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))
            log_error(f"Openbox save failed: {e}")

    def _reconfigure(self):
        if not shutil.which("openbox"):
            QMessageBox.warning(self, "Not Found", "openbox binary not found in PATH.")
            return
        subprocess.Popen(["openbox", "--reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._status.setText("Openbox reconfigure signal sent")
        log_info("Openbox reconfigure requested")

    def _backup(self):
        if not os.path.exists(self._rc_path):
            QMessageBox.warning(self, "No Config", f"File not found:\n{self._rc_path}")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self._rc_path + ".bak." + ts
        if not os.access(os.path.dirname(backup) or ".", os.W_OK):
            backup_dir = os.path.dirname(RC_XML_PATHS[0])
            os.makedirs(backup_dir, exist_ok=True)
            backup = os.path.join(backup_dir, os.path.basename(self._rc_path) + ".bak." + ts)
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
