#!/usr/bin/env python3
"""Vice OS — WiFi Connect. nmcli frontend: scan, list, connect, forget, hotspot."""

import re
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600


def nmcli(args, timeout=15):
    try:
        r = subprocess.run(["nmcli"] + list(args), capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out, r.returncode == 0
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
        if s >= 80:
            return "[||||]"
        if s >= 60:
            return "[||| ]"
        if s >= 40:
            return "[||  ]"
        if s >= 20:
            return "[|   ]"
        return "[    ]"
    except ValueError:
        return "[    ]"


def security_label(security):
    if not security or security == "--":
        return "Open"
    if "WPA" in security or "WEP" in security or "SAE" in security:
        return security
    return "Secured"


class ScanWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        iface = get_wifi_interface()
        if not iface or self._cancelled:
            self.done.emit([])
            return
        nmcli(["device", "wifi", "rescan"], timeout=8)
        if self._cancelled:
            return
        out, _ = nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"])
        networks = []
        seen = set()
        for line in out.splitlines():
            parts = [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]
            if len(parts) < 4:
                continue
            ssid, signal, security, in_use = parts[0], parts[1], parts[2], parts[3]
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            networks.append({
                "ssid": ssid, "signal": signal, "security": security,
                "in_use": in_use == "*",
            })
        if not self._cancelled:
            self.done.emit(networks)


class ConnectWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, args, parent=None):
        super().__init__(parent)
        self._args = list(args)
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        safe_args = [
            "***" if i > 0 and self._args[i - 1] == "password" else a
            for i, a in enumerate(self._args)
        ]
        self.line.emit("$ nmcli " + " ".join(safe_args))
        try:
            self._proc = subprocess.Popen(
                ["nmcli"] + self._args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            if self._proc.stdout:
                for line in self._proc.stdout:
                    if self._cancelled:
                        break
                    self.line.emit(line.rstrip())
            rc = self._proc.wait()
            if not self._cancelled:
                self.finished.emit(rc == 0)
        except Exception as e:
            if not self._cancelled:
                self.line.emit(f"Error: {e}")
                self.finished.emit(False)


class PasswordDialog(QDialog):
    def __init__(self, ssid, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Connect to {ssid}")
        self.setMinimumSize(420, 180)
        vt.apply_app_theme(self)
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
        self.setMinimumSize(420, 220)
        vt.apply_app_theme(self)
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
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        vt.apply_app_theme(self)
        self._scan_worker = None
        self._conn_worker = None
        self._pending_autoconnect = None
        self._pending_ssid = None
        self._init_ui()
        self._refresh_status()
        self._scan()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "WiFi Connect",
            "Scan nearby networks, connect, manage saved profiles and hotspots",
            icon_name="network-wireless",
            badge_text="WIFI",
            badge_variant="aqua",
            parent=self,
        ))

        status_row = QHBoxLayout()
        self._wifi_status = QLabel("WiFi: checking...")
        self._wifi_status.setFont(QFont("monospace", 11, QFont.Bold))
        status_row.addWidget(self._wifi_status)
        status_row.addStretch()

        scan_btn = vt.make_button("Rescan", "secondary", parent=self)
        scan_btn.clicked.connect(self._scan)
        status_row.addWidget(scan_btn)

        hotspot_btn = vt.make_button("Create Hotspot", "secondary", parent=self)
        hotspot_btn.clicked.connect(self._create_hotspot)
        status_row.addWidget(hotspot_btn)

        wifi_toggle = vt.make_button("WiFi On/Off", "secondary", parent=self)
        wifi_toggle.clicked.connect(self._toggle_wifi)
        status_row.addWidget(wifi_toggle)
        root.addLayout(status_row)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["SSID", "Signal", "Security", "In Use"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellDoubleClicked.connect(lambda r, c: self._connect_selected())
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        connect_btn = vt.make_button("Connect", "primary", parent=self)
        connect_btn.clicked.connect(self._connect_selected)
        btn_row.addWidget(connect_btn)

        forget_btn = vt.make_button("Forget Network", "danger", parent=self)
        forget_btn.clicked.connect(self._forget_selected)
        btn_row.addWidget(forget_btn)

        saved_btn = vt.make_button("Saved Networks", "secondary", parent=self)
        saved_btn.clicked.connect(self._show_saved)
        btn_row.addWidget(saved_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(110)
        root.addWidget(self._log)

        self._status = QLabel("Ready — double-click a network to connect")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh_status(self):
        out, _ = nmcli(["-t", "-f", "WIFI,STATE", "general"])
        wifi_enabled = out.startswith("enabled")
        self._wifi_status.setText("WiFi: " + ("ENABLED" if wifi_enabled else "DISABLED"))
        self._wifi_status.setStyleSheet(
            f"color: {vt.COLORS['success']}; font-weight: bold;" if wifi_enabled
            else f"color: {vt.COLORS['danger']}; font-weight: bold;"
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
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        self._table.setRowCount(0)
        self._status.setText("Scanning...")
        self._scan_worker = ScanWorker(parent=self)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, networks):
        self._table.setRowCount(0)
        for net in networks:
            row = self._table.rowCount()
            self._table.insertRow(row)

            ssid_item = QTableWidgetItem(net["ssid"])
            if net["in_use"]:
                ssid_item.setForeground(QBrush(QColor(vt.COLORS["success"])))
            self._table.setItem(row, 0, ssid_item)

            self._table.setItem(row, 1, QTableWidgetItem(
                signal_bars(net["signal"]) + f" ({net['signal']}%)"
            ))
            self._table.setItem(row, 2, QTableWidgetItem(security_label(net["security"])))

            use_item = QTableWidgetItem("Connected" if net["in_use"] else "")
            use_item.setForeground(QBrush(QColor(vt.COLORS["success"])))
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

        row = self._table.currentRow()
        sec_item = self._table.item(row, 2)
        sec_text = sec_item.text() if sec_item else "Open"
        args = ["device", "wifi", "connect", ssid]
        autoconnect = "yes"
        if sec_text != "Open":
            dlg = PasswordDialog(ssid, self)
            if dlg.exec_() != QDialog.Accepted:
                return
            password, autoconnect = dlg.values()
            if password:
                args += ["password", password]

        self._pending_ssid = ssid
        self._pending_autoconnect = autoconnect
        self._run_connect(args)

    def _run_connect(self, args):
        if self._conn_worker is not None and self._conn_worker.isRunning():
            QMessageBox.information(self, "Busy", "Connection already in progress.")
            return
        self._progress.setVisible(True)
        self._conn_worker = ConnectWorker(args, parent=self)
        self._conn_worker.line.connect(self._log.appendPlainText)
        self._conn_worker.finished.connect(self._connect_done)
        self._conn_worker.start()

    def _connect_done(self, ok):
        self._progress.setVisible(False)
        if ok and self._pending_ssid and self._pending_autoconnect == "no":
            nmcli(["connection", "modify", "id", self._pending_ssid, "connection.autoconnect", "no"])
        self._pending_ssid = None
        self._pending_autoconnect = None
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
        if QMessageBox.question(
            self, "Forget", f"Remove saved credentials for '{ssid}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        out, ok = nmcli(["connection", "delete", "id", ssid])
        if ok:
            self._status.setText(f"Forgot: {ssid}")
            log_info(f"WiFi forgotten: {ssid}")
        else:
            self._status.setText(f"Forget failed: {out[:60]}")

    def _show_saved(self):
        out, _ = nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show"])
        wifi_conns = [line for line in out.splitlines() if ":802-11" in line]
        msg = "\n".join(wifi_conns) if wifi_conns else "No saved WiFi networks."
        QMessageBox.information(self, "Saved Networks", msg)

    def _create_hotspot(self):
        dlg = HotspotDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        ssid, password, band = dlg.values()
        if not ssid:
            QMessageBox.warning(self, "Invalid SSID", "Hotspot SSID cannot be empty.")
            return
        if len(password) < 8:
            QMessageBox.warning(self, "Weak Password", "Hotspot password must be at least 8 characters.")
            return
        iface = get_wifi_interface()
        args = ["device", "wifi", "hotspot"]
        if iface:
            args += ["ifname", iface]
        args += ["ssid", ssid, "password", password, "band", band]
        self._pending_ssid = None
        self._pending_autoconnect = None
        self._run_connect(args)

    def closeEvent(self, event):
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._scan_worker.stop()
            self._scan_worker.wait(2000)
        if self._conn_worker is not None and self._conn_worker.isRunning():
            self._conn_worker.stop()
            self._conn_worker.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = WifiConnect()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
