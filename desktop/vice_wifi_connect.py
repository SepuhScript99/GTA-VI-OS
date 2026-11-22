#!/usr/bin/env python3
"""Vice OS — WiFi Connect. nmcli frontend: scan, list, connect, forget, hotspot."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QComboBox, QProgressBar, QTabWidget, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QPlainTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QLabel { color: #00ffff; }
"""


def nmcli(args, timeout=15):
    try:
        r = subprocess.run(["nmcli"] + args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_wifi_status():
    out, _ = nmcli(["-t", "-f", "WIFI,STATE", "general"])
    parts = out.splitlines()
    return parts[0] if parts else "unknown"


def get_wifi_interface():
    out, _ = nmcli(["-t", "-f", "DEVICE,TYPE", "device"])
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "wifi":
            return parts[0]
    return None


def signal_bars(signal):
    try:
        s = int(signal)
        if s >= 80: return "▓▓▓▓"
        if s >= 60: return "▓▓▓░"
        if s >= 40: return "▓▓░░"
        if s >= 20: return "▓░░░"
        return "░░░░"
    except ValueError:
        return "░░░░"


def security_icon(security):
    if not security or security == "--":
        return "🔓 Open"
    if "WPA" in security or "WEP" in security or "SAE" in security:
        return "🔒 " + security
    return "🔒 Secured"


class ScanWorker(QThread):
    done = pyqtSignal(list)

    def run(self):
        iface = get_wifi_interface()
        if not iface:
            self.done.emit([])
            return
        nmcli(["device", "wifi", "rescan"], timeout=8)
        out, _ = nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"])
        networks = []
        seen = set()
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            ssid, signal, security, in_use = parts[0], parts[1], parts[2], parts[3]
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            networks.append({"ssid": ssid, "signal": signal, "security": security,
                             "in_use": in_use == "*"})
        self.done.emit(networks)


class ConnectWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, args):
        super().__init__()
        self._args = args

    def run(self):
        self.line.emit("$ nmcli " + " ".join(self._args))
        try:
            proc = subprocess.Popen(
                ["nmcli"] + self._args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self.line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode == 0)
        except Exception as e:
            self.line.emit(f"Error: {e}")
            self.finished.emit(False)


class PasswordDialog(QDialog):
    def __init__(self, ssid, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Connect to {ssid}")
        self.setFixedSize(420, 180)
        self.setStyleSheet(STYLE)
        layout = QFormLayout(self)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("Wi-Fi password")
        layout.addRow("Password:", self._password)

        self._autoconnect = QComboBox()
        self._autoconnect.addItems(["yes", "no"])
        layout.addRow("Auto-connect:", self._autoconnect)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def values(self):
        return self._password.text(), self._autoconnect.currentText()


class HotspotDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Hotspot")
        self.setFixedSize(420, 220)
        self.setStyleSheet(STYLE)
        layout = QFormLayout(self)

        self._ssid = QLineEdit("Vice-OS-Hotspot")
        layout.addRow("SSID:", self._ssid)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("min 8 characters")
        layout.addRow("Password:", self._password)

        self._band = QComboBox()
        self._band.addItems(["a", "bg"])
        layout.addRow("Band:", self._band)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def values(self):
        return self._ssid.text().strip(), self._password.text(), self._band.currentText()


class WifiConnect(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — WiFi Connect")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._scan_worker = None
        self._conn_worker = None
        self._init_ui()
        self._refresh_status()
        self._scan()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — WiFi Connect")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Status row
        status_row = QHBoxLayout()
        self._wifi_status = QLabel("WiFi: checking...")
        self._wifi_status.setFont(QFont("monospace", 11, QFont.Bold))
        status_row.addWidget(self._wifi_status)
        status_row.addStretch()

        scan_btn = QPushButton("↻ Rescan")
        scan_btn.clicked.connect(self._scan)
        status_row.addWidget(scan_btn)

        hotspot_btn = QPushButton("📡 Create Hotspot")
        hotspot_btn.clicked.connect(self._create_hotspot)
        status_row.addWidget(hotspot_btn)

        wifi_toggle = QPushButton("WiFi On/Off")
        wifi_toggle.clicked.connect(self._toggle_wifi)
        status_row.addWidget(wifi_toggle)
        root.addLayout(status_row)

        # Networks table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["SSID", "Signal", "Security", "In Use"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellDoubleClicked.connect(lambda r, c: self._connect_selected())
        root.addWidget(self._table, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        connect_btn = QPushButton("Connect")
        connect_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        connect_btn.clicked.connect(self._connect_selected)
        btn_row.addWidget(connect_btn)

        forget_btn = QPushButton("Forget Network")
        forget_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        forget_btn.clicked.connect(self._forget_selected)
        btn_row.addWidget(forget_btn)

        saved_btn = QPushButton("Saved Networks")
        saved_btn.clicked.connect(self._show_saved)
        btn_row.addWidget(saved_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Progress + log
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(110)
        root.addWidget(self._log)

        self._status = QLabel("Ready — double-click a network to connect")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh_status(self):
        out, _ = nmcli(["-t", "-f", "WIFI,STATE", "general"])
        wifi_enabled = out.startswith("enabled")
        self._wifi_status.setText("WiFi: " + ("ENABLED" if wifi_enabled else "DISABLED"))
        self._wifi_status.setStyleSheet(
            "color: #00ff88; font-weight: bold;" if wifi_enabled
            else "color: #ff4444; font-weight: bold;"
        )

    def _toggle_wifi(self):
        out, _ = nmcli(["-t", "-f", "WIFI", "general"])
        if out.startswith("enabled"):
            nmcli(["radio", "wifi", "off"])
        else:
            nmcli(["radio", "wifi", "on"])
        self._refresh_status()
        self._scan()

    def _scan(self):
        self._table.setRowCount(0)
        self._status.setText("Scanning...")
        self._scan_worker = ScanWorker()
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, networks):
        self._table.setRowCount(0)
        for net in networks:
            row = self._table.rowCount()
            self._table.insertRow(row)

            ssid_item = QTableWidgetItem(net["ssid"])
            if net["in_use"]:
                ssid_item.setForeground(QBrush(QColor("#00ff88")))
            self._table.setItem(row, 0, ssid_item)

            self._table.setItem(row, 1, QTableWidgetItem(signal_bars(net["signal"]) + f" ({net['signal']}%)"))
            self._table.setItem(row, 2, QTableWidgetItem(security_icon(net["security"])))

            use_item = QTableWidgetItem("● Connected" if net["in_use"] else "")
            use_item.setForeground(QBrush(QColor("#00ff88")))
            self._table.setItem(row, 3, use_item)

        self._status.setText(f"{len(networks)} network(s) found")

    def _selected_ssid(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _connect_selected(self):
        ssid = self._selected_ssid()
        if not ssid:
            QMessageBox.warning(self, "No Selection", "Select a network first.")
            return

        # Check if open or secured
        row = self._table.currentRow()
        sec_text = self._table.item(row, 2).text()
        password = ""
        autoconnect = "yes"
        if "Open" not in sec_text:
            dlg = PasswordDialog(ssid, self)
            if dlg.exec_() != QDialog.Accepted:
                return
            password, autoconnect = dlg.values()

        self._run_connect(["device", "wifi", "connect", ssid,
                           "password", password or "dummy"])
        if autoconnect == "yes" and password:
            self._log.appendPlainText("Note: connection is saved by NetworkManager for auto-reconnect.")

    def _run_connect(self, args):
        self._progress.setVisible(True)
        self._conn_worker = ConnectWorker(args)
        self._conn_worker.line.connect(self._log.appendPlainText)
        self._conn_worker.finished.connect(self._connect_done)
        self._conn_worker.start()

    def _connect_done(self, ok):
        self._progress.setVisible(False)
        self._refresh_status()
        if ok:
            self._status.setText("Connected")
            self._log.appendPlainText("[OK] Connection established")
            log_info("WiFi connected")
        else:
            self._status.setText("Connection failed — check password")
            self._log.appendPlainText("[FAIL] Connection failed")
        self._scan()

    def _forget_selected(self):
        ssid = self._selected_ssid()
        if not ssid:
            QMessageBox.warning(self, "No Selection", "Select a network first.")
            return
        if QMessageBox.question(self, "Forget", f"Remove saved credentials for '{ssid}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        out, ok = nmcli(["connection", "delete", "id", ssid])
        if ok:
            self._status.setText(f"Forgot: {ssid}")
            log_info(f"WiFi forgotten: {ssid}")
        else:
            self._status.setText(f"Forget failed: {out[:60]}")

    def _show_saved(self):
        out, _ = nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show"])
        wifi_conns = [l for l in out.splitlines() if ":802-11" in l]
        msg = "\n".join(wifi_conns) if wifi_conns else "No saved WiFi networks."
        QMessageBox.information(self, "Saved Networks", msg)

    def _create_hotspot(self):
        dlg = HotspotDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        ssid, password, band = dlg.values()
        if len(password) < 8:
            QMessageBox.warning(self, "Weak Password", "Hotspot password must be at least 8 characters.")
            return
        iface = get_wifi_interface()
        args = ["device", "wifi", "hotspot"]
        if iface:
            args += ["ifname", iface]
        args += ["ssid", ssid, "password", password, "band", band]
        self._run_connect(args)


def main():
    app = QApplication(sys.argv)
    win = WifiConnect()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()