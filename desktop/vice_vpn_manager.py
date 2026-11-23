#!/usr/bin/env python3
"""Vice OS — VPN Manager. OpenVPN + WireGuard profile manager with connect/disconnect/status."""

import glob
import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 580

VPN_DIR = os.path.expanduser("~/.config/vice-os/vpn")
OPENVPN_DIR = os.path.join(VPN_DIR, "openvpn")
WIREGUARD_DIR = os.path.join(VPN_DIR, "wireguard")


def run_cmd(cmd, sudo=False):
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    full = (["pkexec"] if (sudo and not is_root) else []) + list(cmd)
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=15)
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out, r.returncode == 0
    except Exception as e:
        return str(e), False


def _ovpn_pid_file(name):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return f"/run/vice-ovpn-{safe}.pid"


def _pid_alive(pid_path):
    try:
        with open(pid_path, encoding="utf-8") as f:
            pid = int(f.read().strip())
        return os.path.isdir(f"/proc/{pid}")
    except (OSError, ValueError):
        return False


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, sudo=False, parent=None):
        super().__init__(parent)
        self.cmd = list(cmd)
        self.sudo = sudo
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
        is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
        full = (["pkexec"] if (self.sudo and not is_root) else []) + self.cmd
        try:
            self._proc = subprocess.Popen(
                full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = self._proc.communicate(timeout=30)
            if not self._cancelled:
                out = (stdout or "").strip() or (stderr or "").strip()
                self.done.emit(self._proc.returncode == 0, out)
        except Exception as e:
            if not self._cancelled:
                self.done.emit(False, str(e))


class WGProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create WireGuard Profile")
        self.setMinimumSize(500, 380)
        vt.apply_app_theme(self)

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
        raw_name = self._name.text().strip() or "wg0"
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", raw_name)
        return {
            "name": safe_name,
            "private_key": self._private_key.text().strip(),
            "address": self._address.text().strip(),
            "dns": self._dns.text().strip(),
            "public_key": self._public_key.text().strip(),
            "endpoint": self._endpoint.text().strip(),
            "allowed_ips": self._allowed_ips.text().strip(),
            "keepalive": self._keepalive.value(),
        }


class VPNManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — VPN Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 480)
        vt.apply_app_theme(self)
        self._worker = None
        self._init_dirs()
        self._init_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_dirs(self):
        os.makedirs(OPENVPN_DIR, exist_ok=True)
        os.makedirs(WIREGUARD_DIR, exist_ok=True)

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "VPN Manager",
            "OpenVPN & WireGuard profiles — connect, disconnect and inspect status",
            icon_name="network-vpn",
            badge_text="TUNNEL",
            badge_variant="coral",
            parent=self,
        ))

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._ovpn_tab = self._create_tab("openvpn")
        self._wg_tab = self._create_tab("wireguard")

        self._tabs.addTab(self._ovpn_tab, "OpenVPN")
        self._tabs.addTab(self._wg_tab, "WireGuard")

        act_row = QHBoxLayout()
        refresh_btn = vt.make_button("Refresh", "secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        act_row.addWidget(refresh_btn)

        add_ovpn = vt.make_button("Add OpenVPN Profile", "primary", parent=self)
        add_ovpn.clicked.connect(lambda: self._add_profile("openvpn"))
        act_row.addWidget(add_ovpn)

        add_wg = vt.make_button("Add WireGuard Profile", "primary", parent=self)
        add_wg.clicked.connect(lambda: self._add_profile("wireguard"))
        act_row.addWidget(add_wg)

        act_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        act_row.addWidget(self._status)
        root.addLayout(act_row)

    def _create_tab(self, vpn_type):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        table = QTableWidget()
        table.setColumnCount(4 if vpn_type == "openvpn" else 5)
        if vpn_type == "openvpn":
            table.setHorizontalHeaderLabels(["Profile", "Server", "Status", "Auth Type"])
        else:
            table.setHorizontalHeaderLabels(["Profile", "Interface", "Endpoint", "Status", "Handshake"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        conn_btn = vt.make_button("Connect", "primary", parent=tab)
        conn_btn.clicked.connect(lambda: self._connect(vpn_type))
        btn_row.addWidget(conn_btn)

        disc_btn = vt.make_button("Disconnect", "secondary", parent=tab)
        disc_btn.clicked.connect(lambda: self._disconnect(vpn_type))
        btn_row.addWidget(disc_btn)

        del_btn = vt.make_button("Delete", "danger", parent=tab)
        del_btn.clicked.connect(lambda: self._delete_profile(vpn_type))
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        if vpn_type == "openvpn":
            self._ovpn_table = table
        else:
            self._wg_table = table
        return tab

    def _refresh(self):
        self._load_openvpn()
        self._load_wireguard()

    def _load_openvpn(self):
        self._ovpn_table.setRowCount(0)
        profiles = sorted(glob.glob(os.path.join(OPENVPN_DIR, "*.ovpn")))
        for prof in profiles:
            name = os.path.splitext(os.path.basename(prof))[0]
            server = ""
            auth = "certificate"
            try:
                with open(prof, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped.startswith("remote "):
                            parts = stripped.split()
                            if len(parts) >= 2:
                                server = parts[1]
                        elif "auth-user-pass" in stripped and not stripped.startswith(("#", ";")):
                            auth = "user/pass"
            except OSError:
                pass

            status = "Disconnected"
            if _pid_alive(_ovpn_pid_file(name)):
                status = "Connected"
            else:
                out, ok = run_cmd(["systemctl", "is-active", f"openvpn@{name}"])
                if ok and out == "active":
                    status = "Connected"

            row = self._ovpn_table.rowCount()
            self._ovpn_table.insertRow(row)
            self._ovpn_table.setItem(row, 0, QTableWidgetItem(name))
            self._ovpn_table.setItem(row, 1, QTableWidgetItem(server))
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QBrush(QColor(
                vt.COLORS["success"] if status == "Connected" else vt.COLORS["danger"]
            )))
            self._ovpn_table.setItem(row, 2, status_item)
            self._ovpn_table.setItem(row, 3, QTableWidgetItem(auth))

    def _load_wireguard(self):
        self._wg_table.setRowCount(0)
        profiles = sorted(glob.glob(os.path.join(WIREGUARD_DIR, "*.conf")))
        for prof in profiles:
            name = os.path.splitext(os.path.basename(prof))[0]
            interface = name
            endpoint = ""
            status = "Disconnected"
            handshake = ""
            try:
                with open(prof, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped.startswith(("#", ";")):
                            continue
                        if stripped.startswith("Endpoint") and "=" in stripped:
                            endpoint = stripped.split("=", 1)[1].strip()
            except OSError:
                pass

            if os.path.isdir(f"/sys/class/net/{name}"):
                status = "Connected"
            out, ok = run_cmd(["wg", "show", name, "latest-handshakes"])
            if ok and out:
                status = "Connected"
                handshake = out.strip()

            row = self._wg_table.rowCount()
            self._wg_table.insertRow(row)
            self._wg_table.setItem(row, 0, QTableWidgetItem(name))
            self._wg_table.setItem(row, 1, QTableWidgetItem(interface))
            self._wg_table.setItem(row, 2, QTableWidgetItem(endpoint))
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QBrush(QColor(
                vt.COLORS["success"] if status == "Connected" else vt.COLORS["danger"]
            )))
            self._wg_table.setItem(row, 3, status_item)
            self._wg_table.setItem(row, 4, QTableWidgetItem(handshake))

    def _selected_profile(self, vpn_type):
        kind = vpn_type.lower()
        table = self._ovpn_table if kind == "openvpn" else self._wg_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a profile first.")
            return None
        item = table.item(row, 0)
        return item.text() if item else None

    def _connect(self, vpn_type):
        kind = vpn_type.lower()
        name = self._selected_profile(kind)
        if not name:
            return
        if kind == "openvpn":
            prof = os.path.join(OPENVPN_DIR, f"{name}.ovpn")
            etc_conf = f"/etc/openvpn/{name}.conf"
            if os.path.exists(etc_conf):
                cmd = ["systemctl", "start", f"openvpn@{name}"]
            else:
                pid_file = _ovpn_pid_file(name)
                cmd = ["openvpn", "--config", prof, "--daemon", "--writepid", pid_file]
            self._run_cmd(cmd, True, f"Connecting {name}...")
        else:
            conf = os.path.join(WIREGUARD_DIR, f"{name}.conf")
            self._run_cmd(["wg-quick", "up", conf], True, f"Connecting {name}...")

    def _disconnect(self, vpn_type):
        kind = vpn_type.lower()
        name = self._selected_profile(kind)
        if not name:
            return
        if kind == "openvpn":
            pid_file = _ovpn_pid_file(name)
            if _pid_alive(pid_file):
                cmd = [
                    "sh", "-c",
                    'kill "$(cat "$1")" 2>/dev/null || true; rm -f "$1"',
                    "_", pid_file,
                ]
            else:
                cmd = ["systemctl", "stop", f"openvpn@{name}"]
            self._run_cmd(cmd, True, f"Disconnecting {name}...")
        else:
            conf = os.path.join(WIREGUARD_DIR, f"{name}.conf")
            self._run_cmd(["wg-quick", "down", conf], True, f"Disconnecting {name}...")

    def _delete_profile(self, vpn_type):
        kind = vpn_type.lower()
        name = self._selected_profile(kind)
        if not name:
            return
        if QMessageBox.question(
            self, "Delete", f"Delete profile {name}?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        target = (
            os.path.join(OPENVPN_DIR, f"{name}.ovpn")
            if kind == "openvpn"
            else os.path.join(WIREGUARD_DIR, f"{name}.conf")
        )
        try:
            os.remove(target)
        except OSError as e:
            QMessageBox.warning(self, "Delete Failed", str(e))
        self._refresh()

    def _add_profile(self, vpn_type):
        kind = vpn_type.lower()
        if kind == "openvpn":
            path, _ = QFileDialog.getOpenFileName(
                self, "Select OpenVPN Config", os.path.expanduser("~"),
                "OpenVPN (*.ovpn *.conf)",
            )
            if path:
                base = os.path.splitext(os.path.basename(path))[0] + ".ovpn"
                dest = os.path.join(OPENVPN_DIR, base)
                try:
                    shutil.copy2(path, dest)
                    self._refresh()
                except OSError as e:
                    QMessageBox.warning(self, "Import Failed", str(e))
        else:
            dlg = WGProfileDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                vals = dlg.get_values()
                content = (
                    "[Interface]\n"
                    f"PrivateKey = {vals['private_key']}\n"
                    f"Address = {vals['address']}\n"
                    f"DNS = {vals['dns']}\n\n"
                    "[Peer]\n"
                    f"PublicKey = {vals['public_key']}\n"
                    f"Endpoint = {vals['endpoint']}\n"
                    f"AllowedIPs = {vals['allowed_ips']}\n"
                    f"PersistentKeepalive = {vals['keepalive']}\n"
                )
                dest = os.path.join(WIREGUARD_DIR, f"{vals['name']}.conf")
                try:
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(content)
                    os.chmod(dest, 0o600)
                except OSError as e:
                    QMessageBox.warning(self, "Save Failed", str(e))
                self._refresh()

    def _run_cmd(self, cmd, sudo, msg):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "Another VPN operation is already running.")
            return
        self._status.setText(msg)
        w = CmdWorker(cmd, sudo, parent=self)
        w.done.connect(lambda ok, out: self._cmd_done(ok, out, cmd))
        self._worker = w
        w.start()

    def _cmd_done(self, ok, out, cmd):
        if ok:
            self._status.setText("Done")
            self._refresh()
        else:
            self._status.setText(f"Failed: {out[:80]}")
            QMessageBox.warning(self, "Error", out or "VPN command failed.")
        log_info(f"VPN cmd {' '.join(cmd)}: {'OK' if ok else 'FAIL'}")

    def closeEvent(self, event):
        self._timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = VPNManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
