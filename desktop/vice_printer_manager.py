#!/usr/bin/env python3
"""Vice OS — Printer Manager. CUPS printer list, add/remove, print queue, test page."""

import os
import subprocess
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600


def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out, r.returncode == 0
    except Exception as e:
        return str(e), False


def _priv_cmd(cmd):
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    return list(cmd) if is_root else ["pkexec"] + list(cmd)


class PrinterManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Printer Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 480)
        vt.apply_app_theme(self)
        self._init_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(10000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Printer Manager",
            "CUPS printer configuration, print queue and test printing",
            icon_name="printer",
            badge_text="CUPS",
            badge_variant="gold",
            parent=self,
        ))

        tabs = QTabWidget()
        root.addWidget(tabs)

        printers_tab = QWidget()
        pl = QVBoxLayout(printers_tab)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Printer", "Device URI", "Status", "Default", "Jobs"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        pl.addWidget(self._table)

        btn_row = QHBoxLayout()
        for label, slot, variant in (
            ("Add Printer", self._add_printer, "primary"),
            ("Set Default", self._set_default, "secondary"),
            ("Enable", lambda: self._printer_cmd("enable"), "secondary"),
            ("Disable", lambda: self._printer_cmd("disable"), "danger"),
            ("Remove", self._remove_printer, "danger"),
            ("Print Test Page", self._test_page, "secondary"),
        ):
            btn = vt.make_button(label, variant, parent=printers_tab)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        pl.addLayout(btn_row)
        tabs.addTab(printers_tab, "Printers")

        queue_tab = QWidget()
        ql = QVBoxLayout(queue_tab)

        self._queue_table = QTableWidget()
        self._queue_table.setColumnCount(5)
        self._queue_table.setHorizontalHeaderLabels(["Job ID", "User", "Title", "Status", "Size"])
        self._queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (0, 1, 3, 4):
            self._queue_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        ql.addWidget(self._queue_table)

        q_btn_row = QHBoxLayout()
        cancel_job_btn = vt.make_button("Cancel Selected Job", "danger", parent=queue_tab)
        cancel_job_btn.clicked.connect(self._cancel_job)
        q_btn_row.addWidget(cancel_job_btn)
        clear_all_btn = vt.make_button("Clear All Jobs", "danger", parent=queue_tab)
        clear_all_btn.clicked.connect(self._clear_all_jobs)
        q_btn_row.addWidget(clear_all_btn)
        q_btn_row.addStretch()
        ql.addLayout(q_btn_row)
        tabs.addTab(queue_tab, "Print Queue")

        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        ll.addWidget(self._log)
        log_btn_row = QHBoxLayout()
        refresh_log_btn = vt.make_button("Refresh Log", "secondary", parent=log_tab)
        refresh_log_btn.clicked.connect(self._load_log)
        log_btn_row.addWidget(refresh_log_btn)
        log_btn_row.addStretch()
        ll.addLayout(log_btn_row)
        tabs.addTab(log_tab, "CUPS Access Log")

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._load_printers()
        self._load_queue()

    def _load_printers(self):
        self._table.setRowCount(0)
        out, ok = run_cmd(["lpstat", "-p", "-d"])
        if not ok and "No destinations" not in out:
            self._status.setText("CUPS not available (lpstat failed)")
            return

        default_printer = ""
        for line in out.splitlines():
            if line.startswith("system default destination:") and ":" in line:
                default_printer = line.split(":", 1)[1].strip()

        for line in out.splitlines():
            if not line.startswith("printer "):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[1]
            status = " ".join(parts[2:]).strip()
            is_default = (name == default_printer)

            uri_out, _ = run_cmd(["lpoptions", "-p", name])
            uri = ""
            for opt in uri_out.split():
                if opt.startswith("device-uri="):
                    uri = opt.replace("device-uri=", "")

            jobs_out, jobs_ok = run_cmd(["lpstat", "-W", "not-completed", "-o", name])
            job_count = str(len(jobs_out.splitlines())) if (jobs_ok and jobs_out) else "0"

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(uri))
            status_item = QTableWidgetItem(status)
            if "idle" in status.lower() or "ready" in status.lower():
                status_item.setForeground(QBrush(QColor(vt.COLORS["success"])))
            elif "disabled" in status.lower() or "stopped" in status.lower():
                status_item.setForeground(QBrush(QColor(vt.COLORS["danger"])))
            self._table.setItem(row, 2, status_item)
            def_item = QTableWidgetItem("Yes" if is_default else "")
            if is_default:
                def_item.setForeground(QBrush(QColor(vt.COLORS["accent_aqua"])))
            self._table.setItem(row, 3, def_item)
            self._table.setItem(row, 4, QTableWidgetItem(job_count))

        self._status.setText(f"{self._table.rowCount()} printer(s) found")

    def _load_queue(self):
        self._queue_table.setRowCount(0)
        out, ok = run_cmd(["lpstat", "-o"])
        if not ok or not out:
            return
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            job_id = parts[0].split("-")[-1] if "-" in parts[0] else parts[0]
            row = self._queue_table.rowCount()
            self._queue_table.insertRow(row)
            self._queue_table.setItem(row, 0, QTableWidgetItem(job_id))
            self._queue_table.setItem(row, 1, QTableWidgetItem(parts[1] if len(parts) > 1 else ""))
            title = " ".join(parts[3:]) if len(parts) > 3 else ""
            self._queue_table.setItem(row, 2, QTableWidgetItem(title))
            self._queue_table.setItem(row, 3, QTableWidgetItem("Pending"))
            self._queue_table.setItem(row, 4, QTableWidgetItem(""))

    def _load_log(self):
        log_path = "/var/log/cups/access_log"
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-100:]
            self._log.setPlainText("".join(lines) or "Log is empty")
        except OSError:
            self._log.setPlainText("Log not available")

    def _selected_printer(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a printer first.")
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _add_printer(self):
        name, ok = QInputDialog.getText(self, "Add Printer", "Printer name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        device, ok = QInputDialog.getText(
            self, "Add Printer", "Device URI (e.g. ipp://192.168.1.50):"
        )
        if not ok or not device.strip():
            return
        device = device.strip()
        driver, ok = QInputDialog.getText(
            self, "Add Printer", "PPD/driver (leave blank to auto-detect):"
        )
        if not ok:
            return
        cmd = _priv_cmd(["lpadmin", "-p", name, "-E", "-v", device, "-m", driver.strip() or "everywhere"])
        out, success = run_cmd(cmd)
        if success:
            self._status.setText(f"Printer '{name}' added")
            log_info(f"Printer added: {name} @ {device}")
            self._refresh()
        else:
            self._status.setText(f"Add failed: {out[:80]}")
            QMessageBox.warning(self, "Error", out)

    def _set_default(self):
        name = self._selected_printer()
        if not name:
            return
        out, ok = run_cmd(_priv_cmd(["lpoptions", "-d", name]))
        if ok:
            self._status.setText(f"Default set to: {name}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Error", out)

    def _printer_cmd(self, action):
        name = self._selected_printer()
        if not name:
            return
        binary = "cupsenable" if action == "enable" else "cupsdisable"
        out, ok = run_cmd(_priv_cmd([binary, name]))
        if ok:
            self._status.setText(f"{action.capitalize()}d: {name}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Error", out)

    def _remove_printer(self):
        name = self._selected_printer()
        if not name:
            return
        if QMessageBox.question(
            self, "Remove", f"Remove printer '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        out, ok = run_cmd(_priv_cmd(["lpadmin", "-x", name]))
        if ok:
            self._status.setText(f"Removed: {name}")
            log_info(f"Printer removed: {name}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Error", out)

    def _test_page(self):
        name = self._selected_printer()
        if not name:
            return
        out, ok = run_cmd(["lp", "-d", name, "/usr/share/cups/data/testprint"])
        if ok:
            self._status.setText(f"Test page sent to {name}")
            log_info(f"Test page printed: {name}")
        else:
            QMessageBox.warning(self, "Error", out)

    def _cancel_job(self):
        row = self._queue_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a job first.")
            return
        item = self._queue_table.item(row, 0)
        if not item:
            return
        job_id = item.text()
        out, ok = run_cmd(["cancel", job_id])
        if ok:
            self._status.setText(f"Cancelled job {job_id}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Error", out)

    def _clear_all_jobs(self):
        if QMessageBox.question(
            self, "Clear Queue", "Cancel ALL pending jobs?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        run_cmd(["cancel", "-a"])
        self._status.setText("All jobs cancelled")
        self._refresh()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = PrinterManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
