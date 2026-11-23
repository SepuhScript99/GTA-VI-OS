#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Net Shield.
Unified VPN, Tor, Privoxy, Secure DNS, and UFW Firewall control deck:
OpenVPN (.ovpn) & WireGuard (.conf) profile import/creation/connect/disconnect,
on-demand Tor & Privoxy service toggles with SOCKS5/HTTP hints, Cloudflare/Quad9/
Mullvad/DHCP DNS presets via NetworkManager, UFW status/toggle, and live public
IP & DNS verification. Styled via vice_theme (Noto Sans CJK fallback).
"""

import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import urllib.request

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QRadioButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    MONO_STACK,
    apply_app_theme,
    load_tool_icon,
    make_button,
    make_card,
    make_header,
    qcolor,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


VPN_DIR = os.path.expanduser("~/.config/vice-os/vpn")
OPENVPN_DIR = os.path.join(VPN_DIR, "openvpn")
WIREGUARD_DIR = os.path.join(VPN_DIR, "wireguard")

DNS_PRESETS = [
    ("system", "System Default (DHCP Auto)", "Use router / DHCP-assigned DNS servers", []),
    ("cloudflare", "Cloudflare (1.1.1.1)", "Fast privacy-focused DNS (1.1.1.1, 1.0.0.1)", ["1.1.1.1", "1.0.0.1"]),
    ("quad9", "Quad9 (9.9.9.9)", "Malware-blocking security DNS (9.9.9.9, 149.112.112.112)", ["9.9.9.9", "149.112.112.112"]),
    ("mullvad", "Mullvad (194.242.2.2)", "No-logging privacy DNS (194.242.2.2, 194.242.2.3)", ["194.242.2.2", "194.242.2.3"]),
]

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _safe_profile_name(raw: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]", "_", raw.strip())
    return clean[:64] or "profile"


def _read_resolv_dns() -> str:
    if not os.path.isfile("/etc/resolv.conf"):
        return "None"
    servers = []
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8", errors="replace") as fp:
            for line in fp:
                stripped = line.strip()
                if stripped.startswith("nameserver"):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
    except OSError:
        return "Unreadable"
    return ", ".join(servers) if servers else "None configured"


def _read_ufw_conf_enabled() -> str:
    conf = "/etc/ufw/ufw.conf"
    if not os.path.isfile(conf):
        return "Not installed" if not shutil.which("ufw") else "Unknown"
    try:
        with open(conf, "r", encoding="utf-8", errors="replace") as fp:
            for line in fp:
                if line.strip().startswith("ENABLED="):
                    val = line.split("=", 1)[1].strip().lower()
                    return "ACTIVE" if val == "yes" else "INACTIVE"
    except OSError:
        pass
    return "Unknown"


def _service_active(name: str) -> str:
    if not shutil.which("systemctl"):
        return "Unknown"
    try:
        res = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=3
        )
        out = res.stdout.strip()
        if out == "active":
            return "ACTIVE"
        if out in ("inactive", "dead"):
            return "INACTIVE"
        return out.upper() or "INACTIVE"
    except Exception:
        return "Unknown"


class StatusRefreshWorker(QThread):
    """Collects VPN, Tor, Privoxy, DNS, and UFW status without triggering polkit."""
    status_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def _active_nm_conn(self) -> tuple:
        if not shutil.which("nmcli"):
            return "", "", ""
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "UUID,NAME,DEVICE,TYPE", "con", "show", "--active"],
                capture_output=True, text=True, timeout=4
            )
            for line in res.stdout.splitlines():
                parts = line.split(":")
                if len(parts) >= 4 and parts[3] not in ("loopback", "tun", "wireguard"):
                    return parts[0], parts[1], parts[2]
        except Exception:
            pass
        return "", "", ""

    def _active_wg_ifaces(self) -> set:
        active = set()
        if os.path.isdir("/sys/class/net"):
            for iface in os.listdir("/sys/class/net"):
                uevent = f"/sys/class/net/{iface}/uevent"
                if os.path.isfile(uevent):
                    try:
                        with open(uevent, "r", encoding="utf-8", errors="replace") as fp:
                            if "DEVTYPE=wireguard" in fp.read():
                                active.add(iface)
                    except OSError:
                        pass
        return active

    def run(self) -> None:
        os.makedirs(OPENVPN_DIR, exist_ok=True)
        os.makedirs(WIREGUARD_DIR, exist_ok=True)

        wg_active = self._active_wg_ifaces()
        profiles = []

        for path in sorted(glob.glob(os.path.join(OPENVPN_DIR, "*.ovpn"))):
            name = os.path.splitext(os.path.basename(path))[0]
            remote = ""
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fp:
                    for line in fp:
                        if line.strip().startswith("remote "):
                            remote = " ".join(line.split()[1:3])
                            break
            except OSError:
                pass
            pid_file = f"/run/vice-ovpn-{_safe_profile_name(name)}.pid"
            pid_alive = False
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r", encoding="utf-8", errors="replace") as fp:
                        pid = fp.read().strip()
                    pid_alive = pid.isdigit() and os.path.isdir(f"/proc/{pid}")
                except OSError:
                    pid_alive = True
            connected = pid_alive or (_service_active(f"openvpn@{name}") == "ACTIVE")
            profiles.append({
                "name": name,
                "kind": "OpenVPN",
                "endpoint": remote or "Configured in .ovpn",
                "status": "Connected" if connected else "Disconnected",
                "path": path,
            })

        for path in sorted(glob.glob(os.path.join(WIREGUARD_DIR, "*.conf"))):
            name = os.path.splitext(os.path.basename(path))[0]
            endpoint = ""
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fp:
                    for line in fp:
                        if line.strip().lower().startswith("endpoint"):
                            endpoint = line.split("=", 1)[1].strip()
                            break
            except OSError:
                pass
            profiles.append({
                "name": name,
                "kind": "WireGuard",
                "endpoint": endpoint or "Configured in .conf",
                "status": "Connected" if name in wg_active else "Disconnected",
                "path": path,
            })

        uuid, nm_name, nm_dev = self._active_nm_conn()
        payload = {
            "profiles": profiles,
            "tor": _service_active("tor"),
            "privoxy": _service_active("privoxy"),
            "ufw": _read_ufw_conf_enabled(),
            "dns": _read_resolv_dns(),
            "nm_uuid": uuid,
            "nm_name": nm_name,
            "nm_dev": nm_dev,
        }
        if not self._stopped:
            self.status_ready.emit(payload)


class IpCheckWorker(QThread):
    """Checks public IP (and optional Tor SOCKS5 exit IP) off the UI thread."""
    ip_ready = pyqtSignal(bool, str, str)

    def __init__(self, via_tor: bool = False):
        super().__init__()
        self._via_tor = via_tor
        self._stopped = False
        self._proc = None

    def stop(self) -> None:
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

    def run(self) -> None:
        if self._via_tor:
            curl_bin = shutil.which("curl")
            if not curl_bin:
                if not self._stopped:
                    self.ip_ready.emit(False, "Tor Check", "curl not installed.")
                return
            try:
                self._proc = subprocess.Popen(
                    [curl_bin, "--socks5-hostname", "127.0.0.1:9050", "-fsSL", "--max-time", "8",
                     "https://check.torproject.org/api/ip"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                stdout, stderr = self._proc.communicate(timeout=10)
                if self._stopped:
                    return
                if self._proc.returncode == 0:
                    data = json.loads(stdout)
                    is_tor = data.get("IsTor", False)
                    ip = data.get("IP", "Unknown")
                    tag = "Tor Verified" if is_tor else "Not Tor"
                    self.ip_ready.emit(True, f"{ip} ({tag})", f"Tor SOCKS5 check: {ip} ({tag})")
                else:
                    self.ip_ready.emit(False, "Tor Offline", (stderr or "").strip() or "Could not reach Tor SOCKS5 (127.0.0.1:9050).")
            except subprocess.TimeoutExpired:
                if self._proc is not None:
                    self._proc.kill()
                    self._proc.communicate()
                if not self._stopped:
                    self.ip_ready.emit(False, "Tor Timeout", "Tor SOCKS5 check timed out.")
            except Exception as exc:
                if not self._stopped:
                    self.ip_ready.emit(False, "Tor Error", str(exc))
            finally:
                self._proc = None
            return

        for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
            if self._stopped:
                return
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ViceNetShield/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    ip = resp.read().decode("utf-8", errors="replace").strip()
                if ip and not self._stopped:
                    self.ip_ready.emit(True, ip, f"Public IP ({url}): {ip}")
                    return
            except Exception:
                continue
        if not self._stopped:
            self.ip_ready.emit(False, "Offline / Unreachable", "Could not query public IP endpoint.")


class CmdWorker(QThread):
    """Runs privileged pkexec or system actions off the UI thread."""
    finished_cmd = pyqtSignal(bool, str)

    def __init__(self, cmd: list, ok_msg: str):
        super().__init__()
        self._cmd = cmd
        self._ok_msg = ok_msg
        self._stopped = False
        self._proc = None

    def stop(self) -> None:
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

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = self._proc.communicate(timeout=45)
            if self._stopped:
                return
            out = (stdout or "").strip()
            err = (stderr or "").strip()
            if self._proc.returncode == 0:
                self.finished_cmd.emit(True, out or self._ok_msg)
            else:
                self.finished_cmd.emit(False, err or out or f"Command exited with code {self._proc.returncode}")
        except subprocess.TimeoutExpired:
            if self._proc is not None:
                self._proc.kill()
                self._proc.communicate()
            if not self._stopped:
                self.finished_cmd.emit(False, "Command timed out after 45s.")
        except Exception as exc:
            if not self._stopped:
                self.finished_cmd.emit(False, str(exc))
        finally:
            self._proc = None


class WGProfileDialog(QDialog):
    """Dialog to create a clean WireGuard configuration profile."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create WireGuard Profile")
        self.resize(500, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        self._name = QLineEdit("wg0")
        form.addRow("Profile Name:", self._name)

        self._private_key = QLineEdit()
        self._private_key.setPlaceholderText("Base64 WireGuard private key")
        form.addRow("Private Key:", self._private_key)

        self._address = QLineEdit("10.0.0.2/24")
        form.addRow("Interface Address:", self._address)

        self._dns = QLineEdit("1.1.1.1")
        form.addRow("DNS Server:", self._dns)

        self._public_key = QLineEdit()
        self._public_key.setPlaceholderText("Peer WireGuard public key")
        form.addRow("Peer Public Key:", self._public_key)

        self._endpoint = QLineEdit("vpn.example.com:51820")
        form.addRow("Peer Endpoint:", self._endpoint)

        self._allowed_ips = QLineEdit("0.0.0.0/0")
        form.addRow("Allowed IPs:", self._allowed_ips)

        self._keepalive = QSpinBox()
        self._keepalive.setRange(0, 3600)
        self._keepalive.setValue(25)
        form.addRow("Keepalive (sec):", self._keepalive)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self) -> dict:
        return {
            "name": _safe_profile_name(self._name.text() or "wg0"),
            "private_key": self._private_key.text().strip(),
            "address": self._address.text().strip(),
            "dns": self._dns.text().strip(),
            "public_key": self._public_key.text().strip(),
            "endpoint": self._endpoint.text().strip(),
            "allowed_ips": self._allowed_ips.text().strip(),
            "keepalive": self._keepalive.value(),
        }


class ViceNetShieldApp(QMainWindow):
    """Main window for Vice Net Shield."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Net Shield — Vice OS")
        self.resize(980, 680)
        self.setMinimumSize(780, 540)
        icon = load_tool_icon("vice-tool-net-shield", "network-vpn")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._refresh_worker = None
        self._cmd_worker = None
        self._ip_worker = None
        self._nm_uuid = ""
        self._nm_name = ""
        self._nm_dev = ""
        self._profiles = []
        self._dns_radios = {}

        self._init_ui()
        self._refresh_all()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice Net Shield",
            subtitle="On-demand VPN tunnels, Tor & Privoxy routing, Secure DNS, UFW firewall, and IP audit",
            icon_name="vice-tool-net-shield",
            badge_text="SHIELD READY",
            badge_variant="neutral",
            parent=root,
        )
        ip_btn = make_button("Check Public IP", variant="primary", parent=self._header)
        ip_btn.clicked.connect(lambda: self._check_ip(via_tor=False))
        self._header.right_layout.insertWidget(0, ip_btn)

        ref_btn = make_button("Refresh", variant="secondary", icon_name="view-refresh", parent=self._header)
        ref_btn.clicked.connect(self._refresh_all)
        self._header.right_layout.insertWidget(1, ref_btn)
        layout.addWidget(self._header)

        # Compact Live Telemetry Summary Strip
        strip_grid = QGridLayout()
        strip_grid.setSpacing(10)
        self._ip_val = self._make_stat_tile("Public IP", "Click Check Public IP", strip_grid, 0)
        self._dns_val = self._make_stat_tile("Active DNS", _read_resolv_dns(), strip_grid, 1)
        self._tor_val = self._make_stat_tile("Tor / Privoxy", "Checking...", strip_grid, 2)
        self._ufw_val = self._make_stat_tile("UFW Firewall", "Checking...", strip_grid, 3)
        layout.addLayout(strip_grid)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_vpn_tab(), "VPN (OpenVPN / WireGuard)")
        tabs.addTab(self._build_tor_tab(), "Tor && Local Proxy")
        tabs.addTab(self._build_dns_tab(), "Secure DNS")
        tabs.addTab(self._build_ufw_tab(), "UFW Firewall")
        layout.addWidget(tabs, 1)

        self._status_lbl = QLabel("All privacy services remain off at boot until you enable them.", root)
        self._status_lbl.setObjectName("MutedLabel")
        layout.addWidget(self._status_lbl)

    def _make_stat_tile(self, title: str, initial: str, grid: QGridLayout, col: int) -> QLabel:
        card = make_card(title=title, margins=(12, 10, 12, 10), spacing=4, parent=self)
        val = QLabel(initial, card)
        val.setWordWrap(True)
        val.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold; font-size: 13px;")
        card.body_layout.addWidget(val)
        grid.addWidget(card, 0, col)
        return val

    def _build_vpn_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        imp_ovpn = make_button("Import .ovpn...", variant="secondary")
        imp_ovpn.clicked.connect(self._import_ovpn)
        top.addWidget(imp_ovpn)

        imp_wg = make_button("Import WireGuard .conf...", variant="secondary")
        imp_wg.clicked.connect(self._import_wg)
        top.addWidget(imp_wg)

        new_wg = make_button("Create WireGuard Profile...", variant="secondary")
        new_wg.clicked.connect(self._create_wg)
        top.addWidget(new_wg)
        top.addStretch(1)
        v.addLayout(top)

        self._vpn_table = QTableWidget(0, 4)
        self._vpn_table.setHorizontalHeaderLabels(["Profile", "Protocol", "Endpoint / Remote", "Status"])
        self._vpn_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._vpn_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._vpn_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._vpn_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._vpn_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._vpn_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._vpn_table.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self._vpn_table, 1)

        act = QHBoxLayout()
        act.setSpacing(8)
        conn_btn = make_button("Connect", variant="primary")
        conn_btn.clicked.connect(self._connect_vpn)
        act.addWidget(conn_btn)

        disc_btn = make_button("Disconnect", variant="secondary")
        disc_btn.clicked.connect(self._disconnect_vpn)
        act.addWidget(disc_btn)

        del_btn = make_button("Delete Profile", variant="danger")
        del_btn.clicked.connect(self._delete_vpn)
        act.addWidget(del_btn)
        act.addStretch(1)
        v.addLayout(act)
        return w

    def _build_tor_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        svc_row = QHBoxLayout()
        svc_row.setSpacing(12)

        tor_card = make_card(
            title="Tor Anonymity Service (tor.service)",
            subtitle="Local SOCKS5 router at 127.0.0.1:9050. Disabled at boot by default.",
            parent=w,
        )
        self._tor_state_lbl = QLabel("Status: checking...", tor_card)
        tor_card.body_layout.addWidget(self._tor_state_lbl)
        tor_btns = QHBoxLayout()
        t_start = make_button("Start Tor", variant="primary", parent=tor_card)
        t_start.clicked.connect(lambda: self._systemctl_toggle("tor", True))
        tor_btns.addWidget(t_start)
        t_stop = make_button("Stop Tor", variant="danger", parent=tor_card)
        t_stop.clicked.connect(lambda: self._systemctl_toggle("tor", False))
        tor_btns.addWidget(t_stop)
        tor_card.body_layout.addLayout(tor_btns)
        svc_row.addWidget(tor_card)

        priv_card = make_card(
            title="Privoxy HTTP Proxy (privoxy.service)",
            subtitle="Local HTTP/HTTPS filtering proxy at 127.0.0.1:8118.",
            parent=w,
        )
        self._priv_state_lbl = QLabel("Status: checking...", priv_card)
        priv_card.body_layout.addWidget(self._priv_state_lbl)
        priv_btns = QHBoxLayout()
        p_start = make_button("Start Privoxy", variant="primary", parent=priv_card)
        p_start.clicked.connect(lambda: self._systemctl_toggle("privoxy", True))
        priv_btns.addWidget(p_start)
        p_stop = make_button("Stop Privoxy", variant="danger", parent=priv_card)
        p_stop.clicked.connect(lambda: self._systemctl_toggle("privoxy", False))
        priv_btns.addWidget(p_stop)
        priv_card.body_layout.addLayout(priv_btns)
        svc_row.addWidget(priv_card)
        v.addLayout(svc_row)

        hints_card = make_card(
            title="Local Proxy Endpoints & CLI Usage",
            subtitle="Copy into Firefox Network Settings or wrap CLI tools via proxychains4",
            parent=w,
        )
        for label, val in (
            ("Tor SOCKS5 Proxy:", "127.0.0.1:9050"),
            ("Privoxy HTTP Proxy:", "127.0.0.1:8118"),
            ("ProxyChains4 Command:", "proxychains4 curl -s https://check.torproject.org/api/ip"),
        ):
            r = QHBoxLayout()
            r.addWidget(QLabel(label))
            edit = QLineEdit(val)
            edit.setReadOnly(True)
            edit.setStyleSheet(f"font-family: {MONO_STACK};")
            r.addWidget(edit, 1)
            cp = make_button("Copy", variant="secondary")
            cp.clicked.connect(lambda _=False, txt=val: QApplication.clipboard().setText(txt))
            r.addWidget(cp)
            hints_card.body_layout.addLayout(r)

        chk_row = QHBoxLayout()
        tor_chk = make_button("Verify Tor Exit IP", variant="primary")
        tor_chk.clicked.connect(lambda: self._check_ip(via_tor=True))
        chk_row.addWidget(tor_chk)
        self._tor_check_lbl = QLabel("Run verification after starting Tor.")
        self._tor_check_lbl.setObjectName("MutedLabel")
        chk_row.addWidget(self._tor_check_lbl, 1)
        hints_card.body_layout.addLayout(chk_row)

        v.addWidget(hints_card)
        v.addStretch(1)
        return w

    def _build_dns_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        card = make_card(
            title="Secure DNS Resolver Presets",
            subtitle="Applies DNS servers cleanly via NetworkManager (nmcli) to your active connection",
            parent=w,
        )
        self._nm_conn_lbl = QLabel("Active NetworkManager connection: detecting...", card)
        self._nm_conn_lbl.setStyleSheet(f"color: {COLORS['accent_gold']}; font-weight: 600;")
        card.body_layout.addWidget(self._nm_conn_lbl)

        for key, label, desc, _ips in DNS_PRESETS:
            rb = QRadioButton(f"{label}  —  {desc}", card)
            if key == "cloudflare":
                rb.setChecked(True)
            self._dns_radios[key] = rb
            card.body_layout.addWidget(rb)

        row = QHBoxLayout()
        apply_btn = make_button("Apply Selected DNS", variant="primary", parent=card)
        apply_btn.clicked.connect(self._apply_dns_preset)
        row.addWidget(apply_btn)
        row.addStretch(1)
        card.body_layout.addLayout(row)
        v.addWidget(card)

        self._resolv_preview = QPlainTextEdit(w)
        self._resolv_preview.setReadOnly(True)
        self._resolv_preview.setMaximumHeight(160)
        v.addWidget(self._resolv_preview)
        v.addStretch(1)
        return w

    def _build_ufw_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        card = make_card(
            title="Uncomplicated Firewall (UFW)",
            subtitle="Inspect status and toggle firewall protection cleanly via pkexec",
            parent=w,
        )
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        en_btn = make_button("Enable UFW", variant="primary", parent=card)
        en_btn.clicked.connect(lambda: self._run_priv(["pkexec", "ufw", "--force", "enable"], "UFW firewall enabled."))
        btn_row.addWidget(en_btn)

        dis_btn = make_button("Disable UFW", variant="danger", parent=card)
        dis_btn.clicked.connect(lambda: self._run_priv(["pkexec", "ufw", "disable"], "UFW firewall disabled."))
        btn_row.addWidget(dis_btn)

        insp_btn = make_button("Inspect Rules (pkexec)", variant="secondary", parent=card)
        insp_btn.clicked.connect(self._inspect_ufw_rules)
        btn_row.addWidget(insp_btn)
        btn_row.addStretch(1)
        card.body_layout.addLayout(btn_row)

        self._ufw_out = QPlainTextEdit(card)
        self._ufw_out.setReadOnly(True)
        self._ufw_out.setPlainText("Click 'Inspect Rules (pkexec)' to read live UFW rules.")
        card.body_layout.addWidget(self._ufw_out, 1)
        v.addWidget(card, 1)
        return w

    def _refresh_all(self) -> None:
        if self._refresh_worker is not None and self._refresh_worker.isRunning():
            return
        self._refresh_worker = StatusRefreshWorker()
        self._refresh_worker.status_ready.connect(self._on_status_ready)
        self._refresh_worker.start()

    def _on_status_ready(self, data: dict) -> None:
        self._profiles = data["profiles"]
        self._nm_uuid = data["nm_uuid"]
        self._nm_name = data["nm_name"]
        self._nm_dev = data["nm_dev"]

        self._dns_val.setText(data["dns"])
        tor_state = data["tor"]
        priv_state = data["privoxy"]
        ufw_state = data["ufw"]

        self._tor_val.setText(f"Tor: {tor_state} · Privoxy: {priv_state}")
        self._tor_state_lbl.setText(f"Status: {tor_state}")
        self._priv_state_lbl.setText(f"Status: {priv_state}")
        self._ufw_val.setText(ufw_state)

        any_vpn = any(p["status"] == "Connected" for p in self._profiles)
        if any_vpn or tor_state == "ACTIVE":
            self._header.set_badge("TUNNEL ACTIVE", "aqua")
        elif ufw_state == "ACTIVE":
            self._header.set_badge("FIREWALL ON", "success")
        else:
            self._header.set_badge("STANDARD NET", "neutral")

        if self._nm_name:
            self._nm_conn_lbl.setText(f"Active connection: {self._nm_name} ({self._nm_dev})")
        else:
            self._nm_conn_lbl.setText("Active NetworkManager connection: none detected")

        if os.path.isfile("/etc/resolv.conf"):
            try:
                with open("/etc/resolv.conf", "r", encoding="utf-8", errors="replace") as fp:
                    self._resolv_preview.setPlainText(fp.read().strip())
            except OSError:
                pass

        self._vpn_table.setRowCount(0)
        for prof in self._profiles:
            row = self._vpn_table.rowCount()
            self._vpn_table.insertRow(row)
            items = [
                QTableWidgetItem(prof["name"]),
                QTableWidgetItem(prof["kind"]),
                QTableWidgetItem(prof["endpoint"]),
                QTableWidgetItem(prof["status"]),
            ]
            items[3].setForeground(
                qcolor("success") if prof["status"] == "Connected" else qcolor("text_secondary")
            )
            for c, it in enumerate(items):
                self._vpn_table.setItem(row, c, it)

    def _selected_vpn(self):
        row = self._vpn_table.currentRow()
        if row < 0 or row >= len(self._profiles):
            QMessageBox.information(self, "Select Profile", "Select a VPN profile from the table first.")
            return None
        return self._profiles[row]

    def _import_ovpn(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import OpenVPN Profile", os.path.expanduser("~"), "OpenVPN (*.ovpn *.conf)"
        )
        if not path:
            return
        os.makedirs(OPENVPN_DIR, exist_ok=True)
        stem = _safe_profile_name(os.path.splitext(os.path.basename(path))[0])
        dst = os.path.join(OPENVPN_DIR, f"{stem}.ovpn")
        shutil.copy2(path, dst)
        os.chmod(dst, 0o600)
        self._status_lbl.setText(f"Imported OpenVPN profile: {stem}")
        self._refresh_all()

    def _import_wg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import WireGuard Config", os.path.expanduser("~"), "WireGuard (*.conf)"
        )
        if not path:
            return
        os.makedirs(WIREGUARD_DIR, exist_ok=True)
        stem = _safe_profile_name(os.path.splitext(os.path.basename(path))[0])
        dst = os.path.join(WIREGUARD_DIR, f"{stem}.conf")
        shutil.copy2(path, dst)
        os.chmod(dst, 0o600)
        self._status_lbl.setText(f"Imported WireGuard profile: {stem}")
        self._refresh_all()

    def _create_wg(self) -> None:
        dlg = WGProfileDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        vals = dlg.get_values()
        if not vals["private_key"] or not vals["public_key"]:
            QMessageBox.warning(self, "Incomplete Profile", "Both Private Key and Peer Public Key are required.")
            return
        os.makedirs(WIREGUARD_DIR, exist_ok=True)
        dst = os.path.join(WIREGUARD_DIR, f"{vals['name']}.conf")
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
        with open(dst, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(content)
        os.chmod(dst, 0o600)
        self._status_lbl.setText(f"Created WireGuard profile: {vals['name']}")
        self._refresh_all()

    def _connect_vpn(self) -> None:
        prof = self._selected_vpn()
        if not prof:
            return
        if prof["kind"] == "WireGuard":
            if not shutil.which("wg-quick"):
                QMessageBox.warning(self, "Missing wg-quick", "Install package 'wireguard-tools'.")
                return
            self._run_priv(["pkexec", "wg-quick", "up", prof["path"]], f"Connected WireGuard: {prof['name']}")
        else:
            if not shutil.which("openvpn"):
                QMessageBox.warning(self, "Missing openvpn", "Install package 'openvpn'.")
                return
            safe = _safe_profile_name(prof["name"])
            pid_file = f"/run/vice-ovpn-{safe}.pid"
            log_file = f"/run/vice-ovpn-{safe}.log"
            self._run_priv(
                ["pkexec", "openvpn", "--config", prof["path"], "--daemon",
                 "--writepid", pid_file, "--log", log_file],
                f"Started OpenVPN tunnel: {prof['name']}"
            )

    def _disconnect_vpn(self) -> None:
        prof = self._selected_vpn()
        if not prof:
            return
        if prof["kind"] == "WireGuard":
            self._run_priv(["pkexec", "wg-quick", "down", prof["path"]], f"Disconnected WireGuard: {prof['name']}")
        else:
            safe = _safe_profile_name(prof["name"])
            pid_file = f"/run/vice-ovpn-{safe}.pid"
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r", encoding="utf-8") as fp:
                        pid = fp.read().strip()
                    if pid.isdigit():
                        self._run_priv(
                            ["pkexec", "bash", "-c", "kill \"$1\" 2>/dev/null || true; rm -f \"$2\"", "vice-ovpn", pid, pid_file],
                            f"Stopped OpenVPN tunnel: {prof['name']}"
                        )
                        return
                except OSError:
                    pass
            self._run_priv(["pkexec", "systemctl", "stop", f"openvpn@{prof['name']}"], f"Stopped OpenVPN: {prof['name']}")

    def _delete_vpn(self) -> None:
        prof = self._selected_vpn()
        if not prof:
            return
        if QMessageBox.question(self, "Delete Profile", f"Delete {prof['kind']} profile '{prof['name']}'?") != QMessageBox.Yes:
            return
        try:
            os.remove(prof["path"])
            self._status_lbl.setText(f"Deleted profile: {prof['name']}")
            self._refresh_all()
        except OSError as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))

    def _systemctl_toggle(self, svc: str, start: bool) -> None:
        action = "start" if start else "stop"
        self._run_priv(["pkexec", "systemctl", action, svc], f"{svc} {action}ed.")

    def _apply_dns_preset(self) -> None:
        chosen = None
        for key, label, _desc, ips in DNS_PRESETS:
            if self._dns_radios[key].isChecked():
                chosen = (key, label, ips)
                break
        if chosen is None:
            return
        key, label, ips = chosen

        if self._nm_uuid and shutil.which("nmcli"):
            if key == "system":
                cmd = [
                    "pkexec", "bash", "-c",
                    "nmcli con modify \"$1\" ipv4.dns '' ipv4.ignore-auto-dns no && nmcli con up \"$1\"",
                    "vice-dns", self._nm_uuid
                ]
            else:
                dns_str = " ".join(ips)
                cmd = [
                    "pkexec", "bash", "-c",
                    "nmcli con modify \"$1\" ipv4.dns \"$2\" ipv4.ignore-auto-dns yes && nmcli con up \"$1\"",
                    "vice-dns", self._nm_uuid, dns_str
                ]
            self._run_priv(cmd, f"Applied {label} to {self._nm_name}")
            return

        if self._nm_dev and shutil.which("resolvectl"):
            cmd = ["pkexec", "resolvectl", "dns", self._nm_dev] + ips
            self._run_priv(cmd, f"Applied {label} via resolvectl")
            return

        QMessageBox.warning(self, "No Active Connection", "Connect to Ethernet or Wi-Fi before changing DNS.")

    def _inspect_ufw_rules(self) -> None:
        if self._cmd_worker is not None and self._cmd_worker.isRunning():
            return
        self._status_lbl.setText("Inspecting UFW rules...")
        self._cmd_worker = CmdWorker(["pkexec", "ufw", "status", "verbose"], "UFW status loaded")
        self._cmd_worker.finished_cmd.connect(self._on_ufw_inspected)
        self._cmd_worker.start()

    def _on_ufw_inspected(self, ok: bool, out: str) -> None:
        self._ufw_out.setPlainText(out)
        self._status_lbl.setText("UFW rules refreshed." if ok else f"UFW inspection error: {out}")

    def _run_priv(self, cmd: list, ok_msg: str) -> None:
        if self._cmd_worker is not None and self._cmd_worker.isRunning():
            self._status_lbl.setText("Another privileged operation is running...")
            return
        self._status_lbl.setText("Running privileged command...")
        self._cmd_worker = CmdWorker(cmd, ok_msg)
        self._cmd_worker.finished_cmd.connect(self._on_cmd_done)
        self._cmd_worker.start()

    def _on_cmd_done(self, ok: bool, out: str) -> None:
        color = COLORS["success"] if ok else COLORS["danger"]
        self._status_lbl.setStyleSheet(f"color: {color}; font-weight: 600;")
        self._status_lbl.setText(out.splitlines()[0] if out else ("Done." if ok else "Failed."))
        log_info(f"Vice Net Shield action ok={ok}: {out}")
        self._refresh_all()

    def _check_ip(self, via_tor: bool) -> None:
        if self._ip_worker is not None and self._ip_worker.isRunning():
            return
        if via_tor:
            self._tor_check_lbl.setText("Checking Tor SOCKS5 exit IP...")
        else:
            self._ip_val.setText("Checking...")
        self._ip_worker = IpCheckWorker(via_tor=via_tor)
        self._ip_worker.ip_ready.connect(lambda ok, val, msg: self._on_ip_ready(via_tor, ok, val, msg))
        self._ip_worker.start()

    def _on_ip_ready(self, via_tor: bool, ok: bool, val: str, msg: str) -> None:
        if via_tor:
            self._tor_check_lbl.setText(msg)
        else:
            self._ip_val.setText(val)
            self._status_lbl.setText(msg)

    def closeEvent(self, event) -> None:
        for w in (self._refresh_worker, self._cmd_worker, self._ip_worker):
            if w is not None:
                if hasattr(w, "stop"):
                    w.stop()
                if w.isRunning():
                    w.wait(2500)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceNetShieldApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
