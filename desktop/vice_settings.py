#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Settings Center.
Unified system configuration center providing 29 configuration pages for desktop,
system, security, and hardware, styled with the Leonida Coastal Dusk design system.
"""

import os
import platform
import shutil
import subprocess
import sys

from PyQt5.QtCore import QProcess, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_error, log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    build_app_qss,
    configure_cjk_fonts,
    configure_icon_theme,
    make_badge,
    resolve_icon,
)

STYLE_FILE = "/opt/vice-os/style.qss"
SETTINGS_WIDTH = 940
SETTINGS_HEIGHT = 640

PAGE_NAMES = [
    "Display", "Sound", "Network", "Users", "Power", "About",
    "Firewall", "Printers", "Date & Time", "Accessibility",
    "Storage", "Updates", "Bluetooth", "Security", "Theme",
    "Keyboard", "Mouse", "Wallpaper", "Startup", "Cleanup",
    "Kernel", "VPN", "SSH", "Network Shares", "Cron", "Backup",
    "USB", "Diagnostics", "Drivers",
]

_c = COLORS
STYLE = build_app_qss(
    f"""
QListWidget#SettingsNav {{
    background-color: {_c['bg_surface']};
    border: 1px solid {_c['border']};
    border-radius: 10px;
    padding: 6px;
}}
QListWidget#SettingsNav::item {{
    padding: 6px 10px;
    border-radius: 6px;
    color: {_c['text_secondary']};
}}
QListWidget#SettingsNav::item:hover {{
    background-color: {_c['bg_elevated']};
    color: {_c['text_primary']};
}}
QListWidget#SettingsNav::item:selected {{
    background-color: {_c['bg_active']};
    color: {_c['accent_peach']};
    border-left: 3px solid {_c['accent_coral']};
    font-weight: bold;
}}
QStackedWidget#SettingsStack {{
    background-color: {_c['bg_surface']};
    border: 1px solid {_c['border']};
    border-radius: 10px;
    padding: 10px;
}}
QScrollBar:vertical {{
    width: 8px;
}}
"""
)


def _configure_icon_theme():
    """Ensure PyQt5 resolves Papirus-Dark / Adwaita icons properly."""
    configure_icon_theme()


def _theme_icon(*names) -> QIcon:
    """Return the first valid Freedesktop theme or pixmap icon from *names*."""
    return resolve_icon(*names)


def run_cmd(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return "N/A"


DIAG_TESTS = [
    ("Network Ping", "ping -c 4 8.8.8.8 2>&1"),
    ("DNS Lookup", "nslookup google.com 2>&1 || dig google.com 2>&1"),
    ("Network Interfaces", "ip -br addr 2>&1"),
    ("Routing Table", "ip route 2>&1"),
    ("Open Ports", "ss -tulnp 2>&1"),
    ("Disk Usage", "df -h 2>&1 | grep -v 'tmpfs\\|loop\\|udev'"),
    ("Memory Info", "free -h 2>&1"),
    ("Failed Services", "systemctl list-units --state=failed --no-pager 2>&1"),
    ("Kernel Errors", "journalctl -k -p err -n 20 --no-pager 2>&1 || sudo dmesg --level=err,crit 2>/dev/null | tail -20"),
    ("Temperature", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1f°C\\n\",$1/1000}' || echo 'N/A'"),
    ("Run All", None),
]


class _DiagWorker(QThread):
    line_out = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
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
        try:
            self._proc = subprocess.Popen(
                self.cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            for line in self._proc.stdout:
                if self._stopped:
                    break
                self.line_out.emit(line.rstrip())
            self._proc.wait()
            if not self._stopped:
                self.done.emit(self._proc.returncode == 0)
        except Exception as e:
            if not self._stopped:
                self.line_out.emit(f"Error: {e}")
                self.done.emit(False)
        finally:
            self._proc = None


class DiagnosticsPage(QWidget):
    def __init__(self):
        super().__init__()
        c = COLORS
        self._worker = None
        self._queue = []

        root = QVBoxLayout(self)
        root.setSpacing(10)
        title = QLabel("Network & System Diagnostics")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        self._list = QListWidget()
        for name, _ in DIAG_TESTS:
            item = QListWidgetItem(name)
            if name == "Run All":
                item.setForeground(QColor(c["accent_peach"]))
            self._list.addItem(item)
        ll.addWidget(self._list)

        self._run_btn = QPushButton("Run Selected")
        self._run_btn.setObjectName("PrimaryButton")
        self._run_btn.clicked.connect(self._run_selected)
        ll.addWidget(self._run_btn)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        rl.addWidget(self._output)
        splitter.addWidget(right)
        splitter.setSizes([220, 620])

        bottom = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        bottom.addWidget(self._progress)
        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {c['text_secondary']};")
        bottom.addWidget(self._status)
        bottom.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._output.clear)
        bottom.addWidget(clear_btn)
        root.addLayout(bottom)

    def _run_selected(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.text()
        if name == "Run All":
            self._queue = [(n, cmd) for n, cmd in DIAG_TESTS if cmd]
            self._output.clear()
            self._next()
            return
        cmd = next((cmd for n, cmd in DIAG_TESTS if n == name), None)
        if cmd:
            self._execute(name, cmd)

    def _next(self):
        if not self._queue:
            self._status.setText("All tests complete")
            self._progress.setVisible(False)
            self._run_btn.setEnabled(True)
            return
        name, cmd = self._queue.pop(0)
        self._output.append(f"\n--- {name} ---")
        self._execute(name, cmd, chain=True)

    def _execute(self, name, cmd, chain=False):
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText(f"Running: {name}")
        self._worker = _DiagWorker(cmd)
        self._worker.line_out.connect(self._output.append)
        self._worker.done.connect(lambda ok: self._finished(ok, name, chain))
        self._worker.start()

    def _finished(self, ok, name, chain):
        c = COLORS["success"] if ok else COLORS["danger"]
        self._output.append(f'<span style="color:{c};">[{"PASS" if ok else "FAIL"}] {name}</span>')
        if chain:
            self._next()
        else:
            self._progress.setVisible(False)
            self._status.setText(f"Done: {name}")
            self._run_btn.setEnabled(True)


class _DetectWorker(QThread):
    found = pyqtSignal(dict)
    done = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        checks = [
            ("GPU", "NVIDIA", "lspci 2>/dev/null | grep -i nvidia", "nvidia-driver",
             "dpkg -l nvidia-driver* 2>/dev/null | grep '^ii' | head -1"),
            ("GPU", "AMD", "lspci 2>/dev/null | grep -i 'amd\\|ati' | grep -i 'vga\\|3d'",
             "firmware-amd-graphics",
             "dpkg -l firmware-amd-graphics 2>/dev/null | grep '^ii' | head -1"),
            ("GPU", "Intel", "lspci 2>/dev/null | grep -i intel | grep -i 'vga\\|3d'",
             "intel-media-va-driver",
             "dpkg -l intel-media-va-driver* 2>/dev/null | grep '^ii' | head -1"),
        ]
        for dtype, vendor, detect_cmd, rec_pkg, inst_cmd in checks:
            if self._stopped:
                return
            out = run_cmd(detect_cmd)
            if out and not self._stopped:
                inst = run_cmd(inst_cmd)
                pkg = inst.split()[1] if inst and inst != "N/A" else ""
                self.found.emit({
                    "type": dtype, "vendor": vendor,
                    "device": out.splitlines()[0].split(":")[-1].strip()[:60],
                    "installed": pkg or "None",
                    "recommended": rec_pkg,
                    "status": "Installed" if pkg else "Not Installed",
                })

        if self._stopped:
            return
        wifi_out = run_cmd("lspci 2>/dev/null | grep -i 'network\\|wireless'")
        if not wifi_out and not self._stopped:
            wifi_out = run_cmd("lsusb 2>/dev/null | grep -i 'wireless\\|wifi'")
        if wifi_out and not self._stopped:
            for line in wifi_out.splitlines():
                if self._stopped:
                    return
                vendor = (
                    "Broadcom" if "broadcom" in line.lower() else
                    "Realtek" if "realtek" in line.lower() else
                    "Intel" if "intel" in line.lower() else "Generic"
                )
                pkg_map = {
                    "Broadcom": "broadcom-sta-dkms",
                    "Realtek": "firmware-realtek",
                    "Intel": "firmware-iwlwifi",
                    "Generic": "firmware-linux-nonfree",
                }
                pkg = pkg_map[vendor]
                inst = run_cmd(f"dpkg -l {pkg} 2>/dev/null | grep '^ii' | head -1")
                installed = inst.split()[1] if inst and inst != "N/A" else ""
                self.found.emit({
                    "type": "WiFi", "vendor": vendor,
                    "device": line.split(":")[-1].strip()[:60],
                    "installed": installed or "None",
                    "recommended": pkg,
                    "status": "Installed" if installed else "Not Installed",
                })
        if not self._stopped:
            self.done.emit()


class _InstallWorker(QThread):
    line_out = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, pkg, remove=False):
        super().__init__()
        self.pkg = pkg
        self.remove = remove
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
        op = "remove" if self.remove else "install"
        cmd = ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", op, "-y", self.pkg]
        if (os.geteuid() != 0 if hasattr(os, "geteuid") else True) and shutil.which("pkexec"):
            cmd = ["pkexec"] + cmd
        elif shutil.which("sudo") and (os.geteuid() != 0 if hasattr(os, "geteuid") else False):
            cmd = ["sudo"] + cmd
        self.line_out.emit("$ " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            for line in self._proc.stdout:
                if self._stopped:
                    break
                self.line_out.emit(line.rstrip())
            self._proc.wait()
            if not self._stopped:
                self.done.emit(self._proc.returncode == 0)
        except Exception as e:
            if not self._stopped:
                self.line_out.emit(f"Error: {e}")
                self.done.emit(False)
        finally:
            self._proc = None


class DriversPage(QWidget):
    def __init__(self):
        super().__init__()
        c = COLORS
        self._drivers = []
        self._workers = []

        root = QVBoxLayout(self)
        root.setSpacing(10)
        title = QLabel("Driver Manager")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter, 1)

        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Type", "Vendor", "Device", "Installed", "Recommended", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        tl.addWidget(self._table)

        btns = QHBoxLayout()
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setObjectName("PrimaryButton")
        self._scan_btn.clicked.connect(self._scan)
        btns.addWidget(self._scan_btn)
        self._inst_btn = QPushButton("Install")
        self._inst_btn.clicked.connect(self._install)
        btns.addWidget(self._inst_btn)
        self._rem_btn = QPushButton("Remove")
        self._rem_btn.setObjectName("DangerButton")
        self._rem_btn.clicked.connect(self._remove)
        btns.addWidget(self._rem_btn)
        btns.addStretch()
        tl.addLayout(btns)
        splitter.addWidget(top)

        bot = QWidget()
        bl = QVBoxLayout(bot)
        bl.setContentsMargins(0, 0, 0, 0)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        bl.addWidget(self._log)
        splitter.addWidget(bot)
        splitter.setSizes([360, 180])

        status_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        status_row.addWidget(self._progress)
        self._status = QLabel("Click Scan or open this page to detect hardware.")
        self._status.setStyleSheet(f"color: {c['text_secondary']};")
        status_row.addWidget(self._status)
        status_row.addStretch()
        root.addLayout(status_row)

        self._initial_scan_done = False

    def on_activated(self):
        if not self._initial_scan_done:
            self._initial_scan_done = True
            self._scan()

    def _scan(self):
        self._table.setRowCount(0)
        self._drivers.clear()
        self._scan_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Scanning...")
        w = _DetectWorker()
        w.found.connect(self._add_row)
        w.done.connect(self._scan_done)
        self._workers.append(w)
        w.start()

    def _add_row(self, info):
        self._drivers.append(info)
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, key in enumerate(["type", "vendor", "device", "installed", "recommended", "status"]):
            item = QTableWidgetItem(info[key])
            if key == "status":
                col_hex = COLORS["success"] if info[key] == "Installed" else COLORS["danger"]
                item.setForeground(QBrush(QColor(col_hex)))
            self._table.setItem(row, col, item)

    def _scan_done(self):
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._status.setText(f"Found {self._table.rowCount()} device(s)")

    def _selected(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._drivers):
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return None
        return self._drivers[row]

    def _install(self):
        info = self._selected()
        if not info:
            return
        pkg = info["recommended"]
        if QMessageBox.question(
            self, "Install", f"Install: {pkg}?", QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_op(pkg, False)

    def _remove(self):
        info = self._selected()
        if not info:
            return
        pkg = info["installed"]
        if pkg == "None":
            QMessageBox.information(self, "Not Installed", "No driver installed for this device.")
            return
        if QMessageBox.question(
            self, "Remove", f"Remove: {pkg}?", QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_op(pkg, True)

    def _run_op(self, pkg, remove):
        self._inst_btn.setEnabled(False)
        self._rem_btn.setEnabled(False)
        self._progress.setVisible(True)
        w = _InstallWorker(pkg, remove)
        w.line_out.connect(self._log.append)
        w.done.connect(lambda ok: self._op_done(ok, pkg, remove))
        self._workers.append(w)
        w.start()

    def _op_done(self, ok, pkg, remove):
        self._progress.setVisible(False)
        self._inst_btn.setEnabled(True)
        self._rem_btn.setEnabled(True)
        op = "Remove" if remove else "Install"
        c = COLORS["success"] if ok else COLORS["danger"]
        self._log.append(f'<span style="color:{c};">[{op} {"OK" if ok else "FAILED"}] {pkg}</span>')
        self._status.setText(f"{op} {'succeeded' if ok else 'failed'}: {pkg}")
        if ok:
            self._scan()


PAGE_APPS = {
    "Display": "vice_display_manager.py",
    "Sound": "vice_audio_manager.py",
    "Network": "vice_wifi_connect.py",
    "Users": "vice_user_manager.py",
    "Power": "vice_power_manager.py",
    "Firewall": "vice_firewall_manager.py",
    "Printers": "vice_printer_manager.py",
    "Date & Time": "vice_tool_clock_sync.py",
    "Accessibility": "vice_accessibility.py",
    "Storage": "vice_disk_manager.py",
    "Updates": "vice_update_manager.py",
    "Bluetooth": "vice_bluetooth_manager.py",
    "Security": "vice_tool_cyber_deck.py",
    "Theme": "vice_theme_manager.py",
    "Keyboard": "vice_keyboard_shortcuts.py",
    "Mouse": "vice_mouse_settings.py",
    "Cleanup": "vice_cleanup.py",
    "Kernel": "vice_kernel_manager.py",
    "Startup": "vice_startup_apps.py",
    "VPN": "vice_tool_net_shield.py",
    "SSH": "vice_ssh_manager.py",
    "Wallpaper": "vice_wallpaper_picker.py",
    "Network Shares": "vice_network_shares.py",
    "Cron": "vice_cron_manager.py",
    "Backup": "vice_backup_scheduler.py",
    "USB": "vice_usb_manager.py",
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))

_PAGE_ICONS = {
    "Display": ("preferences-desktop-display", "video-display"),
    "Sound": ("audio-volume-high", "multimedia-volume-control"),
    "Network": ("network-wireless", "network-wired"),
    "Users": ("system-users", "user-info"),
    "Power": ("battery", "battery-full"),
    "Firewall": ("security-high", "network-firewall"),
    "Printers": ("printer", "preferences-desktop-printer"),
    "Date & Time": ("vice-tool-clock-sync", "preferences-system-time", "x-office-calendar"),
    "Accessibility": ("preferences-desktop-accessibility", "accessibility"),
    "Storage": ("drive-harddisk", "gparted"),
    "Updates": ("system-software-update", "software-update-available"),
    "Bluetooth": ("bluetooth", "preferences-system-bluetooth"),
    "Security": ("vice-tool-cyber-deck", "security-high", "changes-prevent"),
    "Theme": ("preferences-desktop-theme", "applications-graphics"),
    "Keyboard": ("input-keyboard", "preferences-desktop-keyboard"),
    "Mouse": ("input-mouse", "preferences-desktop-mouse"),
    "Cleanup": ("edit-clear", "user-trash"),
    "Kernel": ("applications-system", "utilities-system-monitor"),
    "Startup": ("preferences-system", "system-run"),
    "VPN": ("vice-tool-net-shield", "network-vpn", "network-server"),
    "SSH": ("network-server", "utilities-terminal"),
    "Wallpaper": ("preferences-desktop-wallpaper", "image-x-generic"),
    "Network Shares": ("folder-remote", "network-workgroup"),
    "Cron": ("appointment-new", "x-office-calendar"),
    "Backup": ("document-save", "drive-harddisk"),
    "USB": ("drive-removable-media", "media-removable"),
}


_PAGE_SUMMARIES = {
    "Display": ("Monitors, resolution, scaling & refresh rate", ["Multi-head layout & DPI adjustment", "Live xrandr preview and persistence"]),
    "Sound": ("PipeWire output devices, sink levels & mixer", ["Adjust volume & default playback devices", "Inspect AC97/PipeWire audio streams"]),
    "Network": ("Wi-Fi profiles, Ethernet & wireless scan", ["Connect to secured wireless networks", "Inspect link state and DNS settings"]),
    "Users": ("Local user accounts, groups & passwords", ["Manage sudo privileges and accounts", "Configure session user profiles"]),
    "Power": ("Battery telemetry, suspend & power profile", ["Inspect AC/battery charge status", "Configure sleep and lock policies"]),
    "Firewall": ("UFW / nftables packet rules & ports", ["Enable/disable host firewall safely", "Allow or deny incoming service ports"]),
    "Printers": ("CUPS print queues & local printer setup", ["Discover USB and network printers", "Manage active print jobs"]),
    "Date & Time": ("World clock, IANA timezone & host sync", ["Sync clock with host & geolocation timezone", "Inspect Chrony NTP synchronization"]),
    "Accessibility": ("Visual contrast, font scaling & assist tools", ["Configure screen readability preferences", "Adjust keyboard & pointer accessibility"]),
    "Storage": ("Disk partitions, SMART health & mounts", ["Inspect drives, partitions and filesystems", "Mount and check removable storage"]),
    "Updates": ("Debian Bookworm APT updates & security fixes", ["Check available system package updates", "Apply security patches cleanly"]),
    "Bluetooth": ("Bluetooth adapter power & device pairing", ["Scan and pair nearby audio/HID devices", "Manage trusted Bluetooth peripherals"]),
    "Security": ("Vice Cyber Audit Deck & system hardening", ["Run ethical security & port audits", "Inspect listening services and file integrity"]),
    "Theme": ("Leonida Dusk visual profile & icon theme", ["Preview GTK3, Qt5 and Openbox styles", "Customize desktop theme presets"]),
    "Keyboard": ("Keymap layouts, shortcuts & repeat rate", ["Switch international keyboard layouts", "Review desktop & Openbox bindings"]),
    "Mouse": ("Pointer speed, acceleration & touchpad", ["Tune cursor sensitivity and scrolling", "Configure left/right button layout"]),
    "Cleanup": ("APT cache, temp files & disk reclaim", ["Safely clear package caches and logs", "Reclaim free workspace storage"]),
    "Kernel": ("Linux kernel modules, sysctl & parameters", ["Inspect loaded modules and kernel version", "Review live sysctl tuning"]),
    "Startup": ("Session autostart apps & background services", ["Control applications launched at login", "Keep boot fast and uncluttered"]),
    "VPN": ("OpenVPN, WireGuard, Tor & Secure DNS", ["Import .ovpn / .conf profiles safely", "Toggle Tor, Privoxy & encrypted DNS"]),
    "SSH": ("OpenSSH client/server keys & connections", ["Manage SSH keys and known hosts", "Toggle and audit SSH service access"]),
    "Wallpaper": ("Leonida coastal dusk backgrounds", ["Select or preview desktop wallpapers", "Sync wallpaper across PCManFM & nitrogen"]),
    "Network Shares": ("SMB/CIFS & SSHFS remote mounts", ["Browse and mount shared folders", "Manage persistent remote shares"]),
    "Cron": ("Scheduled user & system cron jobs", ["Inspect and edit recurring timers", "Review Vice TimeSync & maintenance jobs"]),
    "Backup": ("Timeshift snapshots & archive jobs", ["Create and schedule system backups", "Protect key user config directories"]),
    "USB": ("Attached USB devices & auto-mount rules", ["Inspect connected USB hubs and drives", "Configure safe removable media mounting"]),
}


class AppLauncherPage(QWidget):
    """A settings page presenting a structured card to launch its dedicated tool."""

    def __init__(self, page_name, app_file):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(28, 24, 28, 24)

        card = QFrame(self)
        card.setObjectName("Card")
        card.setMaximumWidth(540)
        card.setMinimumWidth(440)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 26, 28, 26)
        cl.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        icon_badge = QLabel(card)
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setFixedSize(64, 64)
        icon_badge.setStyleSheet(
            f"background: {c['bg_elevated']}; border: 1px solid {c['border']}; border-radius: 14px;"
        )
        icon_names = _PAGE_ICONS.get(page_name, ("preferences-system", "applications-other"))
        ic = _theme_icon(*icon_names, "preferences-system")
        if not ic.isNull():
            icon_badge.setPixmap(ic.pixmap(42, 42))
        else:
            icon_badge.setText(page_name[:2].upper())
        top_row.addWidget(icon_badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        pretty = app_file.replace("vice_tool_", "").replace("vice_", "").replace(".py", "").replace("_", " ").title()
        app_name = QLabel(f"Vice {pretty}", card)
        app_name.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")
        title_col.addWidget(app_name)

        summary_text, bullets = _PAGE_SUMMARIES.get(
            page_name,
            (f"Configure {page_name.lower()} preferences", [f"Dedicated {page_name} configuration module"]),
        )
        sub_lbl = QLabel(summary_text, card)
        sub_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")
        sub_lbl.setWordWrap(True)
        title_col.addWidget(sub_lbl)
        top_row.addLayout(title_col, 1)

        badge = make_badge(page_name.upper(), "coral", card)
        top_row.addWidget(badge, alignment=Qt.AlignTop)
        cl.addLayout(top_row)

        sep = QFrame(card)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {c['border']}; border: none;")
        cl.addWidget(sep)

        for bullet in bullets:
            b_lbl = QLabel(f"•  {bullet}", card)
            b_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")
            b_lbl.setWordWrap(True)
            cl.addWidget(b_lbl)

        cl.addSpacing(4)
        btn_row = QHBoxLayout()
        open_btn = QPushButton(f"Open {page_name} Settings".replace("&", "&&"), card)
        open_btn.setObjectName("PrimaryButton")
        open_btn.clicked.connect(lambda: self._launch(app_file))
        btn_row.addWidget(open_btn)
        btn_row.addStretch(1)
        hint = QLabel(f"Module: {app_file}", card)
        hint.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        btn_row.addWidget(hint)
        cl.addLayout(btn_row)

        layout.addWidget(card, alignment=Qt.AlignCenter)

    @staticmethod
    def _launch(app_file):
        path = os.path.join(APP_DIR, app_file)
        if not os.path.exists(path) and app_file == "vice_tool_clock_sync.py":
            path = os.path.join(APP_DIR, "vice_calendar.py")
        if os.path.exists(path):
            QProcess.startDetached(sys.executable, [path])
            log_info(f"Settings launched: {os.path.basename(path)}")
        else:
            log_error(f"Settings app missing: {path}")


class AboutPage(QWidget):
    """Real About page: OS, kernel, desktop suite info."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        logo = QLabel("VICE OS")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            f"color: {c['text_primary']}; font-size: 36px; font-weight: bold; letter-spacing: 8px;"
        )
        layout.addWidget(logo)

        tagline = QLabel("GTA VI Leonida Edition — Debian 12 Bookworm")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet(f"color: {c['accent_peach']}; font-size: 13px; font-weight: 600;")
        layout.addWidget(tagline)

        layout.addSpacing(10)

        info = QGroupBox("System Information")
        info.setMinimumWidth(520)
        il = QVBoxLayout(info)
        il.setSpacing(6)

        os_name = "Vice OS (Debian GNU/Linux 12)"
        if os.path.isfile("/etc/os-release"):
            try:
                with open("/etc/os-release", "r", encoding="utf-8", errors="replace") as fp:
                    for line in fp:
                        if line.startswith("PRETTY_NAME="):
                            os_name = line.split("=", 1)[1].strip().strip('"')
                            break
            except OSError:
                pass
        uptime_val = "—"
        if shutil.which("uptime"):
            try:
                uptime_val = subprocess.run(
                    ["uptime", "-p"], capture_output=True, text=True, timeout=3
                ).stdout.strip() or "—"
            except Exception:
                pass

        rows = [
            ("OS", os_name),
            ("Kernel", platform.release() or "—"),
            ("Architecture", platform.machine() or "—"),
            ("Hostname", platform.node() or "—"),
            ("Desktop", "Vice OS Leonida Desktop (Openbox + PyQt5)"),
            ("Uptime", uptime_val),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            name_lbl = QLabel(f"{label}:")
            name_lbl.setFixedWidth(110)
            name_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-weight: 600;")
            row.addWidget(name_lbl)
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(f"color: {c['accent_aqua']};")
            val_lbl.setWordWrap(True)
            row.addWidget(val_lbl, 1)
            il.addLayout(row)

        layout.addWidget(info, alignment=Qt.AlignCenter)

        license_lbl = QLabel("Debian Bookworm Base  •  PipeWire Audio  •  PyQt5 Suite")
        license_lbl.setAlignment(Qt.AlignCenter)
        license_lbl.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        layout.addWidget(license_lbl)


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS Settings")
        win_icon = _theme_icon("preferences-system", "vice-debian-gta6", "vice-app")
        if not win_icon.isNull():
            self.setWindowIcon(win_icon)
        self.setFixedSize(SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_ui()

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._nav = QListWidget()
        self._nav.setObjectName("SettingsNav")
        self._nav.setFixedWidth(186)
        for name in PAGE_NAMES:
            self._nav.addItem(name)
        self._nav.currentRowChanged.connect(self._switch_page)
        root.addWidget(self._nav)

        self._stack = QStackedWidget()
        self._stack.setObjectName("SettingsStack")
        root.addWidget(self._stack, 1)

        for name in PAGE_NAMES:
            if name == "Diagnostics":
                self._stack.addWidget(DiagnosticsPage())
            elif name == "Drivers":
                self._stack.addWidget(DriversPage())
            elif name == "About":
                self._stack.addWidget(AboutPage())
            elif name in PAGE_APPS:
                self._stack.addWidget(AppLauncherPage(name, PAGE_APPS[name]))
            else:
                placeholder = QWidget()
                pl = QVBoxLayout(placeholder)
                lbl = QLabel(f"{name} settings coming soon.")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
                pl.addWidget(lbl)
                self._stack.addWidget(placeholder)

        self._nav.setCurrentRow(0)

    def _switch_page(self, index):
        self._stack.setCurrentIndex(index)
        page = self._stack.widget(index)
        if page is not None and hasattr(page, "on_activated"):
            page.on_activated()

    def closeEvent(self, event):
        for idx in range(self._stack.count()):
            page = self._stack.widget(idx)
            worker = getattr(page, "_worker", None)
            if worker is not None:
                if hasattr(worker, "stop"):
                    worker.stop()
                if worker.isRunning():
                    worker.wait(2500)
            for w in getattr(page, "_workers", ()):
                if w is not None:
                    if hasattr(w, "stop"):
                        w.stop()
                    if w.isRunning():
                        w.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    configure_icon_theme()
    configure_cjk_fonts(app)
    win = SettingsWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
