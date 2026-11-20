#!/usr/bin/env python3
"""Vice OS — Startup Apps Manager. Enable/disable XDG autostart entries, add custom."""

import sys
import os
import glob
import subprocess
import shutil

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 560

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 16px; height: 16px; background: #1a1a1a; border: 1px solid #00ffff; border-radius: 3px; }
QCheckBox::indicator:checked { background: #00ffff; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLabel { color: #00ffff; }
"""

AUTOSTART_DIRS = [
    os.path.expanduser("~/.config/autostart"),
    "/etc/xdg/autostart",
]


def parse_desktop_file(path):
    """Parse a .desktop file and return (name, exec, enabled)."""
    name = os.path.basename(path).replace(".desktop", "")
    exec_cmd = ""
    enabled = True
    try:
        with open(path) as f:
            in_main = False
            for line in f:
                line = line.strip()
                if line == "[Desktop Entry]":
                    in_main = True
                elif line.startswith("[") and in_main:
                    break
                elif in_main:
                    if line.startswith("Name="):
                        name = line.split("=", 1)[1]
                    elif line.startswith("Exec="):
                        exec_cmd = line.split("=", 1)[1]
                    elif line.startswith("X-GNOME-Autostart-enabled="):
                        enabled = line.split("=", 1)[1].strip().lower() == "true"
    except Exception as e:
        log_error(f"Parse failed {path}: {e}")
    return name, exec_cmd, enabled


def set_enabled(path, enabled):
    """Set X-GNOME-Autostart-enabled in a .desktop file."""
    try:
        with open(path) as f:
            lines = f.readlines()
        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("X-GNOME-Autostart-enabled="):
                new_lines.append(f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            # Insert before first section end (just append to [Desktop Entry])
            insert_at = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("[") and i > 0:
                    insert_at = i
                    break
            else:
                insert_at = len(new_lines)
            new_lines.insert(insert_at, f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}\n")
        with open(path, "w") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        log_error(f"Toggle failed {path}: {e}")
        return False


class AddStartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Startup Application")
        self.setFixedSize(460, 280)
        self.setStyleSheet(STYLE)
        layout = QFormLayout(self)

        self._name = QLineEdit()
        self._name.setPlaceholderText("My App")
        layout.addRow("Name:", self._name)

        self._exec = QLineEdit()
        self._exec.setPlaceholderText("/usr/bin/myapp --arg")
        layout.addRow("Command:", self._exec)

        browse_row = QHBoxLayout()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        browse_row.addWidget(browse_btn)
        browse_row.addStretch()
        layout.addRow("", browse_row)

        self._comment = QLineEdit()
        self._comment.setPlaceholderText("Optional description")
        layout.addRow("Comment:", self._comment)

        self._delay = QLineEdit()
        self._delay.setPlaceholderText("0 (seconds delay)")
        layout.addRow("Delay (s):", self._delay)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Executable",
                                              "/usr/bin", "All files (*)")
        if path:
            self._exec.setText(path)

    def values(self):
        return (self._name.text().strip(), self._exec.text().strip(),
                self._comment.text().strip(), self._delay.text().strip() or "0")


class StartupAppsManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Startup Apps Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._entries = []  # (path, name, exec, enabled, system)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Startup Applications")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Enabled", "Name", "Command", "Source"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellClicked.connect(self._on_cell_clicked)
        root.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Startup App")
        add_btn.clicked.connect(self._add_app)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("Delete Selected")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_btn.clicked.connect(self._delete_app)
        btn_row.addWidget(del_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._entries.clear()
        self._table.setRowCount(0)

        for d in AUTOSTART_DIRS:
            if not os.path.isdir(d):
                continue
            is_system = d == "/etc/xdg/autostart"
            for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
                name, exec_cmd, enabled = parse_desktop_file(path)
                self._entries.append((path, name, exec_cmd, enabled, is_system))

        for path, name, exec_cmd, enabled, is_system in self._entries:
            row = self._table.rowCount()
            self._table.insertRow(row)

            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(enabled)
            cb.toggled.connect(lambda on, p=path: self._toggle(p, on))
            cb_layout.addWidget(cb)
            self._table.setCellWidget(row, 0, cb_widget)

            self._table.setItem(row, 1, QTableWidgetItem(name))
            self._table.setItem(row, 2, QTableWidgetItem(exec_cmd))
            src_item = QTableWidgetItem("System" if is_system else "User")
            if is_system:
                from PyQt5.QtGui import QColor, QBrush
                src_item.setForeground(QBrush(QColor("#888888")))
            self._table.setItem(row, 3, src_item)

        self._status.setText(f"{len(self._entries)} autostart entries")

    def _on_cell_clicked(self, row, col):
        pass  # checkbox handles toggling directly

    def _toggle(self, path, enabled):
        ok = set_enabled(path, enabled)
        if ok:
            name = os.path.basename(path)
            self._status.setText(f"{'Enabled' if enabled else 'Disabled'}: {name}")
            log_info(f"Autostart {'enabled' if enabled else 'disabled'}: {name}")
        else:
            self._status.setText("Toggle failed")

    def _selected_entry(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _add_app(self):
        dlg = AddStartupDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        name, exec_cmd, comment, delay = dlg.values()
        if not name or not exec_cmd:
            QMessageBox.warning(self, "Missing Info", "Name and command required.")
            return

        user_dir = AUTOSTART_DIRS[0]
        os.makedirs(user_dir, exist_ok=True)
        safe_name = name.replace(" ", "-").lower()
        path = os.path.join(user_dir, f"{safe_name}.desktop")

        content = f"""[Desktop Entry]
Type=Application
Name={name}
Comment={comment}
Exec={exec_cmd}
X-GNOME-Autostart-enabled=true
"""
        if delay != "0":
            content += f"X-GNOME-Autostart-Delay={delay}\n"

        try:
            with open(path, "w") as f:
                f.write(content)
            self._status.setText(f"Added: {name}")
            log_info(f"Startup app added: {name} ({exec_cmd})")
            self._refresh()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _delete_app(self):
        entry = self._selected_entry()
        if not entry:
            QMessageBox.warning(self, "No Selection", "Select an entry first.")
            return
        path, name, _, _, is_system = entry
        if is_system:
            QMessageBox.information(
                self, "System Entry",
                "This is a system-wide entry. Disable it with the checkbox instead of deleting."
            )
            return
        if QMessageBox.question(self, "Delete", f"Delete startup app '{name}'?",
                                 QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            os.remove(path)
            self._status.setText(f"Deleted: {name}")
            log_info(f"Startup app deleted: {name}")
            self._refresh()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))


def main():
    app = QApplication(sys.argv)
    win = StartupAppsManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()