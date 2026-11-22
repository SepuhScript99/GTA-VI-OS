#!/usr/bin/env python3
"""Vice OS — VPN Manager. OpenVPN + WireGuard profile manager with connect/disconnect/status."""

import sys
import os
import subprocess
import glob
import json

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QFileDialog, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QCheckBox { color: #00ffff; }
QLabel { color: #00ffff; }
"""

VPN_DIR = os.path.expanduser("~/.config/vice-os/vpn")
OPENVPN_DIR = os.path.join(VPN_DIR, "openvpn")
WIREGUARD_DIR = os.path.join(VPN_DIR, "wireguard")


def run_cmd(cmd, sudo=False):
    full = (["sudo"] if sudo else []) + cmd
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=15)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class VPNManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — VPN Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_dirs()
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_dirs(self):
        os.makedirs(OPENVPN_DIR, exist_ok=True)
        os.makedirs(WIREGUARD_DIR, exist_ok=True)

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — VPN Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Tab: OpenVPN | WireGuard
        from PyQt5.QtWidgets import QTabWidget
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._ovpn_tab = self._create_tab("OpenVPN")
        self._wg_tab = self._create_tab("WireGuard")

        self._tabs.addTab(self._ovpn_tab, "OpenVPN")
        self._tabs.addTab(self._wg_tab, "WireGuard")

        # Common actions
        act_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        act_row.addWidget(refresh_btn)

        add_ovpn = QPushButton("Add OpenVPN Profile")
        add_ovpn.clicked.connect(lambda: self._add_profile("openvpn"))
        act_row.addWidget(add_ovpn)

        add_wg = QPushButton("Add WireGuard Profile")
        add_wg.clicked.connect(lambda: self._add_profile("wireguard"))
        act_row.addWidget(add_wg)

        act_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        act_row.addWidget(self._status)
        root.addLayout(act_row)

    def _create_tab(self, vpn_type):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        table = QTableWidget()
        table.setColumnCount(4 if vpn_type == "OpenVPN" else 5)
        if vpn_type == "OpenVPN":
            table.setHorizontalHeaderLabels(["Profile", "Server", "Status", "Auth Type"])
        else:
            table.setHorizontalHeaderLabels(["Profile", "Interface", "Endpoint", "Status", "Handshake"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        conn_btn = QPushButton("Connect")
        conn_btn.clicked.connect(lambda: self._connect(vpn_type))
        btn_row.addWidget(conn_btn)

        disc_btn = QPushButton("Disconnect")
        disc_btn.clicked.connect(lambda: self._disconnect(vpn_type))
        btn_row.addWidget(disc_btn)

        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_btn.clicked.connect(lambda: self._delete_profile(vpn_type))
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        if vpn_type == "OpenVPN":
            self._ovpn_table = table
        else:
            self._wg_table = table
        return tab

    def _refresh(self):
        self._load_openvpn()
        self._load_wireguard()

    def _load_openvpn(self):
        self._ovpn_table.setRowCount(0)
        profiles = glob.glob(os.path.join(OPENVPN_DIR, "*.ovpn"))
        for prof in profiles:
            name = os.path.basename(prof).replace(".ovpn", "")
            # Parse server from ovpn file
            server = ""
            auth = "password"
            try:
                with open(prof) as f:
                    for line in f:
                        if line.startswith("remote "):
                            server = line.split()[1]
                        elif "auth-user-pass" in line:
                            auth = "user/pass"
            except Exception:
                pass

            # Check if connected
            status = "Disconnected"
            try:
                out, _ = run_cmd(["systemctl", "is-active", f"openvpn@{name}"])
                if out == "active":
                    status = "Connected"
            except Exception:
                pass

            row = self._ovpn_table.rowCount()
            self._ovpn_table.insertRow(row)
            self._ovpn_table.setItem(row, 0, QTableWidgetItem(name))
            self._ovpn_table.setItem(row, 1, QTableWidgetItem(server))
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QBrush(QColor("#00ff88" if status == "Connected" else "#ff4444")))
            self._ovpn_table.setItem(row, 2, status_item)
            self._ovpn_table.setItem(row, 3, QTableWidgetItem(auth))

    def _load_wireguard(self):
        self._wg_table.setRowCount(0)
        profiles = glob.glob(os.path.join(WIREGUARD_DIR, "*.conf"))
        for prof in profiles:
            name = os.path.basename(prof).replace(".conf", "")
            interface = ""
            endpoint = ""
            status = "Disconnected"
            handshake = ""
            try:
                with open(prof) as f:
                    for line in f:
                        if line.strip().startswith("Interface"):
                            interface = name
                        elif "Endpoint" in line:
                            endpoint = line.split("=")[1].strip()
            except Exception:
                pass

            out, _ = run_cmd(["wg", "show", name, "latest-handshakes"])
            if out:
                status = "Connected"
                handshake = out.strip()

            row = self._wg_table.rowCount()
            self._wg_table.insertRow(row)
            self._wg_table.setItem(row, 0, QTableWidgetItem(name))
            self._wg_table.setItem(row, 1, QTableWidgetItem(interface or name))
            self._wg_table.setItem(row, 2, QTableWidgetItem(endpoint))
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QBrush(QColor("#00ff88" if status == "Connected" else "#ff4444")))
            self._wg_table.setItem(row, 3, status_item)
            self._wg_table.setItem(row, 4, QTableWidgetItem(handshake))

    def _selected_profile(self, vpn_type):
        table = self._ovpn_table if vpn_type == "openvpn" else self._wg_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a profile first.")
            return None
        return table.item(row, 0).text()

    def _connect(self, vpn_type):
        name = self._selected_profile(vpn_type)
        if not name:
            return
        if vpn_type == "openvpn":
            self._run_cmd(["systemctl", "start", f"openvpn@{name}"], True, f"Connecting {name}...")
        else:
            self._run_cmd(["wg-quick", "up", name], True, f"Connecting {name}...")

    def _disconnect(self, vpn_type):
        name = self._selected_profile(vpn_type)
        if not name:
            return
        if vpn_type == "openvpn":
            self._run_cmd(["systemctl", "stop", f"openvpn@{name}"], True, f"Disconnecting {name}...")
        else:
            self._run_cmd(["wg-quick", "down", name], True, f"Disconnecting {name}...")

    def _delete_profile(self, vpn_type):
        name = self._selected_profile(vpn_type)
        if not name:
            return
        if QMessageBox.question(self, "Delete", f"Delete profile {name}?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if vpn_type == "openvpn":
            os.remove(os.path.join(OPENVPN_DIR, f"{name}.ovpn"))
        else:
            os.remove(os.path.join(WIREGUARD_DIR, f"{name}.conf"))
        self._refresh()

    def _add_profile(self, vpn_type):
        if vpn_type == "openvpn":
            path, _ = QFileDialog.getOpenFileName(self, "Select OpenVPN Config", os.path.expanduser("~"), "OpenVPN (*.ovpn *.conf)")
            if path:
                dest = os.path.join(OPENVPN_DIR, os.path.basename(path))
                import shutil
                shutil.copy2(path, dest)
                self._refresh()
        else:
            dlg = WGProfileDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                vals = dlg.get_values()
                content = f"""[Interface]
PrivateKey = {vals['private_key']}
Address = {vals['address']}
DNS = {vals['dns']}

[Peer]
PublicKey = {vals['public_key']}
Endpoint = {vals['endpoint']}
AllowedIPs = {vals['allowed_ips']}
PersistentKeepalive = {vals['keepalive']}
"""
                dest = os.path.join(WIREGUARD_DIR, f"{vals['name']}.conf")
                with open(dest, "w") as f:
                    f.write(content)
                self._refresh()

    def _run_cmd(self, cmd, sudo, msg):
        self._status.setText(msg)
        w = CmdWorker(cmd, sudo)
        w.done.connect(lambda ok, out: self._cmd_done(ok, out, cmd))
        w.start()
        self._worker = w

    def _cmd_done(self, ok, out, cmd):
        if ok:
            self._status.setText("Done")
            self._refresh()
        else:
            self._status.setText(f"Failed: {out[:80]}")
            QMessageBox.warning(self, "Error", out)
        log_info(f"VPN cmd {' '.join(cmd)}: {'OK' if ok else 'FAIL'}")


class WGProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create WireGuard Profile")
        self.setFixedSize(500, 380)
        self.setStyleSheet("""
            QWidget { background: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
            QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
            QLabel { color: #00ffff; }
            QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px 12px; }
        """)

        layout = QFormLayout(self)
        self._name = QLineEdit("wg0")
        layout.addRow("Name:", self._name)

        self._private_key = QLineEdit()
        layout.addRow("Private Key:", self._private_key)

        self._address = QLineEdit("10.0.0.2/24")
        layout.addRow("Address:", self._address)

        self._dns = QLineEdit("1.1.1.1")
        layout.addRow("DNS:", self._dns)

        self._public_key = QLineEdit()
        layout.addRow("Peer Public Key:", self._public_key)

        self._endpoint = QLineEdit("vpn.example.com:51820")
        layout.addRow("Endpoint:", self._endpoint)

        self._allowed_ips = QLineEdit("0.0.0.0/0")
        layout.addRow("Allowed IPs:", self._allowed_ips)

        self._keepalive = QSpinBox()
        self._keepalive.setRange(0, 3600)
        self._keepalive.setValue(25)
        layout.addRow("Keepalive:", self._keepalive)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_values(self):
        return {
            "name": self._name.text().strip() or "wg0",
            "private_key": self._private_key.text().strip(),
            "address": self._address.text().strip(),
            "dns": self._dns.text().strip(),
            "public_key": self._public_key.text().strip(),
            "endpoint": self._endpoint.text().strip(),
            "allowed_ips": self._allowed_ips.text().strip(),
            "keepalive": self._keepalive.value(),
        }


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, sudo=False):
        super().__init__()
        self.cmd = cmd
        self.sudo = sudo

    def run(self):
        out, ok = run_cmd(self.cmd, self.sudo)
        self.done.emit(ok, out)


def main():
    app = QApplication(sys.argv)
    win = VPNManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()