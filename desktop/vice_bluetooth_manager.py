#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Bluetooth Manager.
Frontend for bluetoothctl: device scanning, pairing, connecting, and adapter status.
"""

import os
import re
import shutil
import subprocess
import sys
import time

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QProgressBar
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 580


def btctl(*args):
    if not shutil.which("bluetoothctl"):
        return "bluetoothctl not installed", False
    try:
        r = subprocess.run(
            ["bluetoothctl"] + list(args),
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class ScanWorker(QThread):
    device_found = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._stopped = False
        self._proc = None

    def stop(self):
        self._stopped = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.3)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass

    def run(self):
        if not shutil.which("bluetoothctl"):
            if not self._stopped:
                self.finished.emit()
            return
        try:
            subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, timeout=5)
            self._proc = subprocess.Popen(
                ["bluetoothctl", "scan", "on"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            start = time.time()
            while not self._stopped and time.time() - start < 10:
                line = self._proc.stdout.readline()
                if not line:
                    break
                m = re.search(r"\[NEW\] Device ([0-9A-F:]+) (.+)", line)
                if m:
                    self.device_found.emit({
                        "mac": m.group(1),
                        "name": m.group(2).strip(),
                        "paired": False,
                        "connected": False,
                    })
        except Exception:
            pass
        finally:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=0.5)
                except Exception:
                    self._proc.kill()
            self._proc = None
            try:
                subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, timeout=3)
            except Exception:
                pass
        if not self._stopped:
            self.finished.emit()


class BtWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, args):
        super().__init__()
        self.args = args
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        out, ok = btctl(*self.args)
        if not self._stopped:
            self.done.emit(ok, out)


class BluetoothManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Bluetooth Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(700, 480)
        apply_app_theme(self)
        self._scan_worker = None
        self._bt_worker = None
        self._init_ui()
        self._load_paired()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Bluetooth Manager",
            subtitle="Scan nearby devices, pair peripherals, and manage adapter power",
            icon_name="bluetooth",
            badge_text="BLUETOOTH",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        status_row = QHBoxLayout()
        self._power_label = QLabel("Bluetooth: checking...")
        self._power_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self._power_label)
        status_row.addStretch()
        self._power_btn = make_button("Turn On", variant="secondary", parent=self)
        self._power_btn.clicked.connect(self._toggle_power)
        status_row.addWidget(self._power_btn)
        root.addLayout(status_row)
        self._refresh_power()

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["MAC Address", "Name", "Paired", "Connected"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        act_row = QHBoxLayout()
        self._scan_btn = make_button("Scan (10s)", variant="primary", parent=self)
        self._scan_btn.clicked.connect(self._start_scan)
        act_row.addWidget(self._scan_btn)

        pair_btn = make_button("Pair", variant="secondary", parent=self)
        pair_btn.clicked.connect(self._pair_selected)
        act_row.addWidget(pair_btn)

        connect_btn = make_button("Connect", variant="secondary", parent=self)
        connect_btn.clicked.connect(self._connect_selected)
        act_row.addWidget(connect_btn)

        disconnect_btn = make_button("Disconnect", variant="secondary", parent=self)
        disconnect_btn.clicked.connect(self._disconnect_selected)
        act_row.addWidget(disconnect_btn)

        remove_btn = make_button("Remove", variant="danger", parent=self)
        remove_btn.clicked.connect(self._remove_selected)
        act_row.addWidget(remove_btn)

        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._load_paired)
        act_row.addWidget(refresh_btn)
        root.addLayout(act_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _refresh_power(self):
        out, _ = btctl("show")
        if "Powered: yes" in out:
            self._power_label.setText("Bluetooth: ON")
            self._power_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
            self._power_btn.setText("Turn Off")
        else:
            self._power_label.setText("Bluetooth: OFF")
            self._power_label.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
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
        p_item.setForeground(QBrush(QColor(COLORS["success"] if paired else COLORS["text_muted"])))
        self._table.setItem(row, 2, p_item)
        c_item = QTableWidgetItem("Yes" if connected else "No")
        c_item.setForeground(QBrush(QColor(COLORS["success"] if connected else COLORS["text_muted"])))
        self._table.setItem(row, 3, c_item)

    def _selected_mac(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _start_scan(self):
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
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
        if QMessageBox.question(
            self, "Remove Device", f"Remove {mac}?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_bt(["remove", mac], f"Removing {mac}")

    def _run_bt(self, args, msg):
        if self._bt_worker is not None and self._bt_worker.isRunning():
            self._status.setText("Another Bluetooth command is running...")
            return
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

    def closeEvent(self, event):
        for w in (self._scan_worker, self._bt_worker):
            if w is not None:
                w.stop()
        for w in (self._scan_worker, self._bt_worker):
            if w is not None and w.isRunning():
                w.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = BluetoothManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
