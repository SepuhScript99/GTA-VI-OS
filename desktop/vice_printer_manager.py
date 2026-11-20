#!/usr/bin/env python3
"""Vice OS — Printer Manager. CUPS printer list, add/remove, print queue, test page."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QTabWidget, QTextEdit, QInputDialog, QComboBox,
    QLineEdit, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600

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


def run_cmd(cmd):
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class PrinterManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Printer Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(10000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Printer Manager (CUPS)")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Printers tab ---
        printers_tab = QWidget()
        pl = QVBoxLayout(printers_tab)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Printer", "Device URI", "Status", "Default", "Jobs"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        pl.addWidget(self._table)

        btn_row = QHBoxLayout()
        for label, slot, danger in [
            ("Add Printer", self._add_printer, False),
            ("Set Default", self._set_default, False),
            ("Enable", lambda: self._printer_cmd("enable"), False),
            ("Disable", lambda: self._printer_cmd("disable"), True),
            ("Remove", self._remove_printer, True),
            ("Print Test Page", self._test_page, False),
        ]:
            btn = QPushButton(label)
            if danger:
                btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        pl.addLayout(btn_row)
        tabs.addTab(printers_tab, "Printers")

        # --- Print Queue tab ---
        queue_tab = QWidget()
        ql = QVBoxLayout(queue_tab)

        self._queue_table = QTableWidget()
        self._queue_table.setColumnCount(5)
        self._queue_table.setHorizontalHeaderLabels(["Job ID", "User", "Title", "Status", "Size"])
        self._queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i in [0, 1, 3, 4]:
            self._queue_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        ql.addWidget(self._queue_table)

        q_btn_row = QHBoxLayout()
        cancel_job_btn = QPushButton("Cancel Selected Job")
        cancel_job_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        cancel_job_btn.clicked.connect(self._cancel_job)
        q_btn_row.addWidget(cancel_job_btn)
        clear_all_btn = QPushButton("Clear All Jobs")
        clear_all_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        clear_all_btn.clicked.connect(self._clear_all_jobs)
        q_btn_row.addWidget(clear_all_btn)
        q_btn_row.addStretch()
        ql.addLayout(q_btn_row)
        tabs.addTab(queue_tab, "Print Queue")

        # --- CUPS Log tab ---
        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        ll.addWidget(self._log)
        log_btn_row = QHBoxLayout()
        refresh_log_btn = QPushButton("Refresh Log")
        refresh_log_btn.clicked.connect(self._load_log)
        log_btn_row.addWidget(refresh_log_btn)
        log_btn_row.addStretch()
        ll.addLayout(log_btn_row)
        tabs.addTab(log_tab, "CUPS Access Log")

        # Status
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._load_printers()
        self._load_queue()

    def _load_printers(self):
        self._table.setRowCount(0)
        out, ok = run_cmd(["lpstat", "-p", "-d"])
        if not ok:
            self._status.setText("CUPS not available (lpstat failed)")
            return

        default_printer = ""
        for line in out.splitlines():
            if line.startswith("system default destination:"):
                default_printer = line.split(":")[1].strip()

        for line in out.splitlines():
            if not line.startswith("printer "):
                continue
            parts = line.split()
            name = parts[1]
            status = " ".join(parts[2:]).strip()
            is_default = (name == default_printer)

            # Get device URI
            uri_out, _ = run_cmd(["lpoptions", "-p", name])
            uri = ""
            for opt in uri_out.split():
                if opt.startswith("device-uri="):
                    uri = opt.replace("device-uri=", "")

            # Get job count
            jobs_out, _ = run_cmd(["lpstat", "-W", "not-completed", "-p", name])
            job_count = str(len(jobs_out.splitlines())) if jobs_out else "0"

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(uri))
            status_item = QTableWidgetItem(status)
            if "idle" in status.lower() or "ready" in status.lower():
                status_item.setForeground(QBrush(QColor("#00ff88")))
            elif "disabled" in status.lower() or "stopped" in status.lower():
                status_item.setForeground(QBrush(QColor("#ff4444")))
            self._table.setItem(row, 2, status_item)
            def_item = QTableWidgetItem("Yes" if is_default else "")
            if is_default:
                def_item.setForeground(QBrush(QColor("#ff00ff")))
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
        out, _ = run_cmd("tail -n 100 /var/log/cups/access_log 2>/dev/null || echo 'Log not available'")
        self._log.setPlainText(out)

    def _selected_printer(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a printer first.")
            return None
        return self._table.item(row, 0).text()

    def _add_printer(self):
        name, ok = QInputDialog.getText(self, "Add Printer", "Printer name:")
        if not ok or not name:
            return
        device, ok = QInputDialog.getText(self, "Add Printer",
                                          "Device URI (e.g. ipp://192.168.1.50):")
        if not ok or not device:
            return
        driver, ok = QInputDialog.getText(self, "Add Printer",
                                          "PPD/driver (leave blank to auto-detect):")
        cmd = ["sudo", "lpadmin", "-p", name, "-E", "-v", device]
        if driver:
            cmd += ["-m", driver]
        else:
            cmd += ["-m", "everywhere"]
        out, success = run_cmd(cmd)
        if success:
            self._status.setText(f"Printer '{name}' added")
            log_info(f"Printer added: {name} @ {device}")
        else:
            self._status.setText(f"Add failed: {out[:80]}")
            QMessageBox.warning(self, "Error", out)

    def _set_default(self):
        name = self._selected_printer()
        if not name:
            return
        out, ok = run_cmd(["sudo", "lpoptions", "-d", name])
        if ok:
            self._status.setText(f"Default set to: {name}")
        else:
            QMessageBox.warning(self, "Error", out)

    def _printer_cmd(self, action):
        name = self._selected_printer()
        if not name:
            return
        flag = "-E" if action == "enable" else "-E"
        out, ok = run_cmd(["sudo", "cupsenable" if action == "enable" else "cupsdisable", name])
        if ok:
            self._status.setText(f"{action.capitalize()}d: {name}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Error", out)

    def _remove_printer(self):
        name = self._selected_printer()
        if not name:
            return
        if QMessageBox.question(self, "Remove", f"Remove printer '{name}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        out, ok = run_cmd(["sudo", "lpadmin", "-x", name])
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
        job_id = self._queue_table.item(row, 0).text()
        out, ok = run_cmd(["cancel", job_id])
        if ok:
            self._status.setText(f"Cancelled job {job_id}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Error", out)

    def _clear_all_jobs(self):
        if QMessageBox.question(self, "Clear Queue", "Cancel ALL pending jobs?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        run_cmd(["cancel", "-a"])
        self._status.setText("All jobs cancelled")
        self._refresh()


def main():
    app = QApplication(sys.argv)
    win = PrinterManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()