#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Systemd Service Manager
List, inspect, start, stop, restart, enable, and disable systemd system and user services.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QAbstractItemView, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLabel { color: #00ffff; }
"""

STATE_COLORS = {
    "active":      "#00ff88",
    "running":     "#00ff88",
    "enabled":     "#00ffff",
    "inactive":    "#888888",
    "dead":        "#888888",
    "disabled":    "#444444",
    "failed":      "#ff4444",
    "error":       "#ff4444",
}


def systemctl(*args, sudo=False):
    cmd = (["sudo"] if sudo else []) + ["systemctl"] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class LoadWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, filter_state):
        super().__init__()
        self.filter_state = filter_state

    def run(self):
        args = [
            "list-units", "--type=service", "--no-pager",
            "--no-legend",
            "--output=json-short",
        ]
        if self.filter_state != "all":
            args += [f"--state={self.filter_state}"]
        out, ok = systemctl(*args)
        services = []
        if ok and out:
            for line in out.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    services.append({
                        "unit":   parts[0],
                        "load":   parts[1],
                        "active": parts[2],
                        "sub":    parts[3],
                        "desc":   parts[4] if len(parts) > 4 else "",
                    })
        # Also get enabled/disabled status for each
        enabled_out, _ = systemctl("list-unit-files", "--type=service", "--no-pager", "--no-legend")
        enabled_map = {}
        for line in enabled_out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                enabled_map[parts[0]] = parts[1]
        for s in services:
            s["enabled"] = enabled_map.get(s["unit"], "")
        self.done.emit(services)


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, args, sudo=False):
        super().__init__()
        self.args = args
        self.sudo = sudo

    def run(self):
        out, ok = systemctl(*self.args, sudo=self.sudo)
        self.done.emit(ok, out)


class ServiceManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Service Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._services = []
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Service Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search services...")
        self._search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search)

        filter_row.addWidget(QLabel("State:"))
        self._state_combo = QComboBox()
        self._state_combo.addItems(["all", "active", "inactive", "failed"])
        self._state_combo.currentTextChanged.connect(lambda _: self._refresh())
        filter_row.addWidget(self._state_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        filter_row.addWidget(refresh_btn)
        root.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Service", "Active", "Sub-state", "Enabled", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        root.addWidget(self._table)

        # Action buttons
        act_row = QHBoxLayout()
        for label, slot in [
            ("Start",   lambda: self._svc_cmd("start")),
            ("Stop",    lambda: self._svc_cmd("stop")),
            ("Restart", lambda: self._svc_cmd("restart")),
            ("Enable",  lambda: self._svc_cmd("enable")),
            ("Disable", lambda: self._svc_cmd("disable")),
            ("Status",  self._show_status),
        ]:
            btn = QPushButton(label)
            if label in ("Stop", "Disable"):
                btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
            btn.clicked.connect(slot)
            act_row.addWidget(btn)
        act_row.addStretch()
        root.addLayout(act_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._status.setText("Loading services...")
        state = self._state_combo.currentText()
        w = LoadWorker(state)
        w.done.connect(self._on_loaded)
        w.start()
        self._worker = w

    def _on_loaded(self, services):
        self._services = services
        self._apply_filter()
        self._status.setText(f"{len(services)} service(s)")

    def _apply_filter(self):
        search = self._search.text().lower()
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for s in self._services:
            if search and search not in s["unit"].lower() and search not in s["desc"].lower():
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s["unit"]))

            for col, key, in [(1, "active"), (2, "sub"), (3, "enabled")]:
                val = s[key]
                item = QTableWidgetItem(val)
                color = next((c for k, c in STATE_COLORS.items() if k in val.lower()), "#00ffff")
                item.setForeground(QBrush(QColor(color)))
                self._table.setItem(row, col, item)

            self._table.setItem(row, 4, QTableWidgetItem(s["desc"]))
        self._table.setSortingEnabled(True)

    def _selected_unit(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a service first.")
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _svc_cmd(self, action):
        unit = self._selected_unit()
        if not unit:
            return
        self._status.setText(f"{action.capitalize()}: {unit}")
        w = CmdWorker([action, unit], sudo=True)
        w.done.connect(lambda ok, out: self._cmd_done(ok, out, action, unit))
        w.start()
        self._worker = w

    def _cmd_done(self, ok, out, action, unit):
        if ok:
            self._status.setText(f"{action.capitalize()} OK: {unit}")
            log_info(f"systemctl {action} {unit}: OK")
        else:
            self._status.setText(f"{action.capitalize()} FAILED: {unit}")
            log_error(f"systemctl {action} {unit}: {out}")
            QMessageBox.warning(self, "Error", out[:300])
        self._refresh()

    def _show_status(self):
        unit = self._selected_unit()
        if not unit:
            return
        out, _ = systemctl("status", unit, "--no-pager", "-l")
        dlg = QMessageBox(self)
        dlg.setWindowTitle(f"Status: {unit}")
        dlg.setText(f"<pre style='font-family:monospace;font-size:11px;'>{out[:2000]}</pre>")
        dlg.setStyleSheet(STYLE)
        dlg.exec_()


def main():
    app = QApplication(sys.argv)
    win = ServiceManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
