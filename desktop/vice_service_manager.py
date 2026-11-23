#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Systemd Service Manager.
List, inspect, start, stop, restart, enable, and disable systemd system services.
"""

import html
import os
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QAbstractItemView, QComboBox
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

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

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660

STATE_COLORS = {
    "active": COLORS["success"],
    "running": COLORS["success"],
    "enabled": COLORS["accent_aqua"],
    "inactive": COLORS["text_secondary"],
    "dead": COLORS["text_muted"],
    "disabled": COLORS["text_muted"],
    "failed": COLORS["danger"],
    "error": COLORS["danger"],
}


def systemctl(*args, sudo=False):
    cmd = ["systemctl"] + list(args)
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if sudo and not is_root and shutil.which("pkexec"):
        cmd = ["pkexec"] + cmd
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (r.stdout or "").strip() or (r.stderr or "").strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class LoadWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, filter_state):
        super().__init__()
        self.filter_state = filter_state
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        args = ["list-units", "--type=service", "--no-pager", "--no-legend"]
        if self.filter_state != "all":
            args += [f"--state={self.filter_state}"]
        out, ok = systemctl(*args)
        services = []
        if ok and out and not self._stopped:
            for line in out.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    services.append({
                        "unit": parts[0],
                        "load": parts[1],
                        "active": parts[2],
                        "sub": parts[3],
                        "desc": parts[4] if len(parts) > 4 else "",
                    })
        if self._stopped:
            return
        enabled_out, _ = systemctl("list-unit-files", "--type=service", "--no-pager", "--no-legend")
        enabled_map = {}
        for line in enabled_out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                enabled_map[parts[0]] = parts[1]
        for s in services:
            s["enabled"] = enabled_map.get(s["unit"], "")
        if not self._stopped:
            self.done.emit(services)


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, args, sudo=False):
        super().__init__()
        self.args = args
        self.sudo = sudo
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        out, ok = systemctl(*self.args, sudo=self.sudo)
        if not self._stopped:
            self.done.emit(ok, out)


class ServiceManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Service Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        apply_app_theme(self)
        self._services = []
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Systemd Service Manager",
            subtitle="Inspect, start, stop, restart, enable, and disable systemd services",
            icon_name="applications-system",
            badge_text="SYSTEMD",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search services...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search)

        filter_row.addWidget(QLabel("State:"))
        self._state_combo = QComboBox()
        self._state_combo.addItems(["all", "active", "inactive", "failed"])
        self._state_combo.currentTextChanged.connect(lambda _: self._refresh())
        filter_row.addWidget(self._state_combo)

        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        filter_row.addWidget(refresh_btn)
        root.addLayout(filter_row)

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
        root.addWidget(self._table, 1)

        act_row = QHBoxLayout()
        for label, slot, variant in (
            ("Start", lambda: self._svc_cmd("start"), "primary"),
            ("Stop", lambda: self._svc_cmd("stop"), "danger"),
            ("Restart", lambda: self._svc_cmd("restart"), "secondary"),
            ("Enable", lambda: self._svc_cmd("enable"), "secondary"),
            ("Disable", lambda: self._svc_cmd("disable"), "danger"),
            ("Status", self._show_status, "secondary"),
        ):
            btn = make_button(label, variant=variant, parent=self)
            btn.clicked.connect(slot)
            act_row.addWidget(btn)
        act_row.addStretch()
        root.addLayout(act_row)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _stop_worker(self):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2000)

    def _refresh(self):
        self._stop_worker()
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

            for col, key in ((1, "active"), (2, "sub"), (3, "enabled")):
                val = s[key]
                item = QTableWidgetItem(val)
                color = next((c for k, c in STATE_COLORS.items() if k in val.lower()), COLORS["accent_aqua"])
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
        self._stop_worker()
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
        dlg.setText(f"<pre style='font-family:monospace;font-size:11px;'>{html.escape(out[:2000])}</pre>")
        dlg.exec_()

    def closeEvent(self, event):
        self._stop_worker()
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = ServiceManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
