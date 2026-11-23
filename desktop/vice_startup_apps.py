#!/usr/bin/env python3
"""Vice OS — Startup Apps Manager. Enable/disable XDG autostart entries, add custom."""

import glob
import os
import re
import shutil
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info, log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 580

USER_AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
SYSTEM_AUTOSTART_DIR = "/etc/xdg/autostart"
AUTOSTART_DIRS = [USER_AUTOSTART_DIR, SYSTEM_AUTOSTART_DIR]


def parse_desktop_file(path):
    """Parse a .desktop file and return (name, exec, enabled)."""
    name = os.path.basename(path).replace(".desktop", "")
    exec_cmd = ""
    enabled = True
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
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
                    elif line.startswith("Hidden="):
                        if line.split("=", 1)[1].strip().lower() == "true":
                            enabled = False
    except Exception as e:
        log_error(f"Parse failed {path}: {e}")
    return name, exec_cmd, enabled


def set_enabled(path, enabled):
    """Set X-GNOME-Autostart-enabled in a .desktop file, creating a user override if system-owned."""
    target_path = path
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(SYSTEM_AUTOSTART_DIR):
        os.makedirs(USER_AUTOSTART_DIR, exist_ok=True)
        user_override = os.path.join(USER_AUTOSTART_DIR, os.path.basename(path))
        if not os.path.exists(user_override):
            try:
                shutil.copy2(path, user_override)
            except OSError as e:
                log_error(f"Copy override failed {path}: {e}")
                return False
        target_path = user_override

    try:
        with open(target_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        found_auto = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("X-GNOME-Autostart-enabled="):
                new_lines.append(f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}\n")
                found_auto = True
            elif line.strip().startswith("Hidden="):
                new_lines.append(f"Hidden={'false' if enabled else 'true'}\n")
            else:
                new_lines.append(line)
        if not found_auto:
            insert_at = len(new_lines)
            for i, line in enumerate(new_lines):
                if line.strip().startswith("[") and i > 0:
                    insert_at = i
                    break
            new_lines.insert(insert_at, f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}\n")
        with open(target_path, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        log_error(f"Toggle failed {target_path}: {e}")
        return False


class AddStartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Startup Application")
        self.setFixedSize(460, 280)
        apply_app_theme(self)
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
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "/usr/bin", "All files (*)"
        )
        if path:
            self._exec.setText(path)

    def values(self):
        return (
            self._name.text().strip(),
            self._exec.text().strip(),
            self._comment.text().strip(),
            self._delay.text().strip() or "0",
        )


class StartupAppsManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Startup Apps Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(700, 460)
        apply_app_theme(self)
        self._entries = []  # (path, name, exec, enabled, system)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Startup Applications",
            subtitle="Enable, disable, or add XDG autostart entries for your session",
            icon_name="preferences-system",
            badge_text="XDG AUTOSTART",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Enabled", "Name", "Command", "Source"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        add_btn = make_button("+ Add Startup App", variant="primary", parent=self)
        add_btn.clicked.connect(self._add_app)
        btn_row.addWidget(add_btn)

        del_btn = make_button("Delete Selected", variant="danger", parent=self)
        del_btn.clicked.connect(self._delete_app)
        btn_row.addWidget(del_btn)

        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _refresh(self):
        self._entries.clear()
        self._table.setRowCount(0)

        seen_files = set()
        for d in AUTOSTART_DIRS:
            if not os.path.isdir(d):
                continue
            is_system = os.path.abspath(d) == os.path.abspath(SYSTEM_AUTOSTART_DIR)
            for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
                fname = os.path.basename(path)
                if fname in seen_files:
                    continue
                seen_files.add(fname)
                has_sys = os.path.exists(os.path.join(SYSTEM_AUTOSTART_DIR, fname))
                name, exec_cmd, enabled = parse_desktop_file(path)
                self._entries.append((path, name, exec_cmd, enabled, is_system or has_sys))

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
            label_src = "System" if is_system else "User"
            src_item = QTableWidgetItem(label_src)
            if is_system:
                src_item.setForeground(QBrush(QColor(COLORS["text_muted"])))
            self._table.setItem(row, 3, src_item)

        self._status.setText(f"{len(self._entries)} autostart entries")

    def _toggle(self, path, enabled):
        ok = set_enabled(path, enabled)
        if ok:
            name = os.path.basename(path)
            self._status.setText(f"{'Enabled' if enabled else 'Disabled'}: {name}")
            log_info(f"Autostart {'enabled' if enabled else 'disabled'}: {name}")
        else:
            self._status.setText("Toggle failed")
            self._refresh()

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

        os.makedirs(USER_AUTOSTART_DIR, exist_ok=True)
        safe_name = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-") or "startup-app"
        path = os.path.join(USER_AUTOSTART_DIR, f"{safe_name}.desktop")

        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Comment={comment}\n"
            f"Exec={exec_cmd}\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        if delay.isdigit() and int(delay) > 0:
            content += f"X-GNOME-Autostart-Delay={delay}\n"

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
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
        if is_system and os.path.dirname(os.path.abspath(path)) == os.path.abspath(SYSTEM_AUTOSTART_DIR):
            QMessageBox.information(
                self, "System Entry",
                "This is a system-wide entry. Disable it with the checkbox instead of deleting."
            )
            return
        if QMessageBox.question(
            self, "Delete", f"Remove entry '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
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
