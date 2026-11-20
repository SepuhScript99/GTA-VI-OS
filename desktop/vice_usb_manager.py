#!/usr/bin/env python3
"""Vice OS — USB Auto-Mount GUI. View, mount, unmount USB drives."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QCheckBox, QSpinBox, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 520

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 16px; height: 16px; background: #1a1a1a; border: 1px solid #00ffff; border-radius: 3px; }
QCheckBox::indicator:checked { background: #00ffff; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLabel { color: #00ffff; }
"""

DAEMON_SCRIPT = os.path.join(os.path.dirname(__file__), "system_utils", "vice_usb_automount.py")


class UsbWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            r = subprocess.run(self.cmd, capture_output=True, text=True, timeout=15)
            self.done.emit(r.returncode == 0, r.stdout.strip() or r.stderr.strip())
        except Exception as e:
            self.done.emit(False, str(e))


class USBManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — USB Auto-Mount Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — USB Auto-Mount Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Daemon status
        status_box = QGroupBox("Daemon Status")
        sl = QHBoxLayout(status_box)
        self._daemon_status = QLabel("Checking...")
        sl.addWidget(self._daemon_status)
        sl.addStretch()
        self._start_btn = QPushButton("Start Daemon")
        self._start_btn.clicked.connect(self._start_daemon)
        sl.addWidget(self._start_btn)
        self._stop_btn = QPushButton("Stop Daemon")
        self._stop_btn.clicked.connect(self._stop_daemon)
        sl.addWidget(self._stop_btn)
        root.addWidget(status_box)

        # Config
        cfg_box = QGroupBox("Auto-Mount Settings")
        cl = QVBoxLayout(cfg_box)

        self._auto_mount_cb = QCheckBox("Auto-mount USB drives on connect")
        self._auto_mount_cb.toggled.connect(self._save_config)
        cl.addWidget(self._auto_mount_cb)

        self._notify_cb = QCheckBox("Show desktop notifications")
        self._notify_cb.toggled.connect(self._save_config)
        cl.addWidget(self._notify_cb)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Mount options:"))
        self._opts_edit = QSpinBox()
        self._opts_edit.setRange(0, 100)
        opts_row.addWidget(self._opts_edit)
        cl.addLayout(opts_row)
        root.addWidget(cfg_box)

        # Devices table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Device", "FS Type", "Size", "Mount Point", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table)

        # Actions
        act_row = QHBoxLayout()
        self._mount_btn = QPushButton("Mount Selected")
        self._mount_btn.clicked.connect(self._mount_selected)
        act_row.addWidget(self._mount_btn)

        self._unmount_btn = QPushButton("Unmount Selected")
        self._unmount_btn.clicked.connect(self._unmount_selected)
        act_row.addWidget(self._unmount_btn)

        self._eject_btn = QPushButton("Eject")
        self._eject_btn.clicked.connect(self._eject_selected)
        act_row.addWidget(self._eject_btn)

        act_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        act_row.addWidget(refresh_btn)
        root.addLayout(act_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._update_daemon_status()
        self._load_devices()

    def _update_daemon_status(self):
        # Check if daemon is running
        pid_file = "/tmp/vice_usb_automount.pid"
        running = False
        if os.path.exists(pid_file):
            try:
                pid = int(open(pid_file).read().strip())
                os.kill(pid, 0)  # Check if process exists
                running = True
            except Exception:
                running = False

        if running:
            self._daemon_status.setText("Daemon: RUNNING")
            self._daemon_status.setStyleSheet("color: #00ff88; font-weight: bold;")
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
        else:
            self._daemon_status.setText("Daemon: STOPPED")
            self._daemon_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)

    def _load_devices(self):
        self._table.setRowCount(0)
        out, ok = subprocess.run(
            ["lsblk", "-o", "NAME,TYPE,FSTYPE,SIZE,TRAN,MOUNTPOINT", "-J"],
            capture_output=True, text=True, timeout=5
        ).stdout, True
        try:
            data = json.loads(out)
            for dev in data.get("blockdevices", []):
                if dev.get("tran") == "usb" and dev.get("type") == "part":
                    row = self._table.rowCount()
                    self._table.insertRow(row)
                    self._table.setItem(row, 0, QTableWidgetItem(dev.get("name", "")))
                    self._table.setItem(row, 1, QTableWidgetItem(dev.get("fstype", "")))
                    self._table.setItem(row, 2, QTableWidgetItem(dev.get("size", "")))
                    mp = dev.get("mountpoint", "")
                    self._table.setItem(row, 3, QTableWidgetItem(mp))
                    status = "Mounted" if mp else "Unmounted"
                    item = QTableWidgetItem(status)
                    item.setForeground(QBrush(QColor("#00ff88" if mp else "#ff4444")))
                    self._table.setItem(row, 4, item)
        except Exception as e:
            log_error(f"USB list failed: {e}")

    def _start_daemon(self):
        self._run_cmd([sys.executable, DAEMON_SCRIPT], "Starting daemon...")

    def _stop_daemon(self):
        self._run_cmd([sys.executable, DAEMON_SCRIPT, "stop"], "Stopping daemon...")

    def _mount_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return
        dev = self._table.item(row, 0).text()
        self._run_cmd(["udisksctl", "mount", "-b", f"/dev/{dev}"], f"Mounting {dev}...")

    def _unmount_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return
        dev = self._table.item(row, 0).text()
        mp = self._table.item(row, 3).text()
        if not mp:
            QMessageBox.information(self, "Not Mounted", "Device is not mounted.")
            return
        self._run_cmd(["udisksctl", "unmount", "-b", f"/dev/{dev}"], f"Unmounting {dev}...")

    def _eject_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return
        dev = self._table.item(row, 0).text()
        self._run_cmd(["udisksctl", "power-off", "-b", f"/dev/{dev}"], f"Ejecting {dev}...")

    def _save_config(self):
        # Could persist to ~/.config/vice-os/usb_automount.json
        log_info("USB auto-mount config updated")

    def _run_cmd(self, cmd, msg):
        self._status.setText(msg)
        self._mount_btn.setEnabled(False)
        self._unmount_btn.setEnabled(False)
        self._eject_btn.setEnabled(False)
        w = UsbWorker(cmd)
        w.done.connect(self._cmd_done)
        w.start()
        self._worker = w

    def _cmd_done(self, ok, out):
        self._mount_btn.setEnabled(True)
        self._unmount_btn.setEnabled(True)
        self._eject_btn.setEnabled(True)
        if ok:
            self._status.setText("Done")
            self._refresh()
        else:
            self._status.setText(f"Failed: {out[:80]}")
            QMessageBox.warning(self, "Error", out)


import json
def main():
    app = QApplication(sys.argv)
    win = USBManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()