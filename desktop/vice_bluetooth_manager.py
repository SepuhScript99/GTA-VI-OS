#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Bluetooth Manager
Frontend for bluetoothctl: device scanning, pairing, connecting, and adapter status.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QProgressBar, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""


def btctl(*args):
    try:
        r = subprocess.run(["bluetoothctl"] + list(args),
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class ScanWorker(QThread):
    device_found = pyqtSignal(dict)
    finished = pyqtSignal()

    def run(self):
        subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, timeout=5)
        proc = subprocess.Popen(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        import re, time
        start = time.time()
        while time.time() - start < 10:
            line = proc.stdout.readline()
            if not line:
                break
            m = re.search(r'\[NEW\] Device ([0-9A-F:]+) (.+)', line)
            if m:
                self.device_found.emit({"mac": m.group(1), "name": m.group(2).strip(), "paired": False, "connected": False})
        proc.terminate()
        subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, timeout=5)
        self.finished.emit()


class BtWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, args):
        super().__init__()
        self.args = args

    def run(self):
        out, ok = btctl(*self.args)
        self.done.emit(ok, out)


class BluetoothManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Bluetooth Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._scan_worker = None
        self._bt_worker = None
        self._init_ui()
        self._load_paired()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Bluetooth Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Power status
        status_row = QHBoxLayout()
        self._power_label = QLabel("Bluetooth: checking...")
        self._power_label.setFont(QFont("monospace", 11))
        status_row.addWidget(self._power_label)
        status_row.addStretch()
        self._power_btn = QPushButton("Turn On")
        self._power_btn.clicked.connect(self._toggle_power)
        status_row.addWidget(self._power_btn)
        root.addLayout(status_row)
        self._refresh_power()

        # Devices table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["MAC Address", "Name", "Paired", "Connected"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table)

        # Action buttons
        act_row = QHBoxLayout()
        self._scan_btn = QPushButton("Scan (10s)")
        self._scan_btn.clicked.connect(self._start_scan)
        act_row.addWidget(self._scan_btn)

        pair_btn = QPushButton("Pair")
        pair_btn.clicked.connect(self._pair_selected)
        act_row.addWidget(pair_btn)

        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self._connect_selected)
        act_row.addWidget(connect_btn)

        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.clicked.connect(self._disconnect_selected)
        act_row.addWidget(disconnect_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        remove_btn.clicked.connect(self._remove_selected)
        act_row.addWidget(remove_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_paired)
        act_row.addWidget(refresh_btn)
        root.addLayout(act_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh_power(self):
        out, _ = btctl("show")
        if "Powered: yes" in out:
            self._power_label.setText("Bluetooth: ON")
            self._power_label.setStyleSheet("color: #00ff88; font-weight: bold;")
            self._power_btn.setText("Turn Off")
        else:
            self._power_label.setText("Bluetooth: OFF")
            self._power_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self._power_btn.setText("Turn On")

    def _toggle_power(self):
        out, _ = btctl("show")
        if "Powered: yes" in out:
            btctl("power", "off")
        else:
            btctl("power", "on")
        self._refresh_power()

    def _load_paired(self):
        self._table.setRowCount(0)
        paired_out, _ = btctl("devices", "Paired")
        connected_out, _ = btctl("devices", "Connected")
        connected_macs = set()
        for line in connected_out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                connected_macs.add(parts[1])

        for line in paired_out.splitlines():
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            mac, name = parts[1], parts[2]
            self._add_row(mac, name, paired=True, connected=mac in connected_macs)
        self._status.setText(f"{self._table.rowCount()} paired device(s)")

    def _add_row(self, mac, name, paired=False, connected=False):
        for row in range(self._table.rowCount()):
            if self._table.item(row, 0) and self._table.item(row, 0).text() == mac:
                return
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(mac))
        self._table.setItem(row, 1, QTableWidgetItem(name))
        p_item = QTableWidgetItem("Yes" if paired else "No")
        p_item.setForeground(QBrush(QColor("#00ff88" if paired else "#888")))
        self._table.setItem(row, 2, p_item)
        c_item = QTableWidgetItem("Yes" if connected else "No")
        c_item.setForeground(QBrush(QColor("#00ff88" if connected else "#888")))
        self._table.setItem(row, 3, c_item)

    def _selected_mac(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _start_scan(self):
        self._scan_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Scanning for devices...")
        self._scan_worker = ScanWorker()
        self._scan_worker.device_found.connect(
            lambda d: self._add_row(d["mac"], d["name"], False, False)
        )
        self._scan_worker.finished.connect(self._scan_done)
        self._scan_worker.start()

    def _scan_done(self):
        self._scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText(f"Scan complete — {self._table.rowCount()} device(s)")

    def _pair_selected(self):
        mac = self._selected_mac()
        if mac:
            self._run_bt(["pair", mac], f"Pairing {mac}")

    def _connect_selected(self):
        mac = self._selected_mac()
        if mac:
            self._run_bt(["connect", mac], f"Connecting {mac}")

    def _disconnect_selected(self):
        mac = self._selected_mac()
        if mac:
            self._run_bt(["disconnect", mac], f"Disconnecting {mac}")

    def _remove_selected(self):
        mac = self._selected_mac()
        if not mac:
            return
        if QMessageBox.question(self, "Remove Device", f"Remove {mac}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._run_bt(["remove", mac], f"Removing {mac}")

    def _run_bt(self, args, msg):
        self._progress.setVisible(True)
        self._status.setText(msg)
        w = BtWorker(args)
        w.done.connect(self._bt_done)
        w.start()
        self._bt_worker = w

    def _bt_done(self, ok, out):
        self._progress.setVisible(False)
        self._status.setText("Done" if ok else f"Failed: {out[:60]}")
        if not ok:
            log_error(f"BT op failed: {out}")
        self._load_paired()


def main():
    app = QApplication(sys.argv)
    win = BluetoothManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
