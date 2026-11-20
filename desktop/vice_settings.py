#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Settings Center
Unified system configuration center providing 29 configuration pages for desktop, system, and hardware.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QSlider, QGroupBox,
    QMessageBox, QLineEdit, QComboBox, QCheckBox, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar, QTabWidget,
    QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

STYLE_FILE = '/opt/vice-os/style.qss'
SETTINGS_WIDTH = 900
SETTINGS_HEIGHT = 600

PAGE_NAMES = [
    'Display', 'Sound', 'Network', 'Users', 'Power', 'About',
    'Firewall', 'Printers', 'Date & Time', 'Accessibility',
    'Storage', 'Updates', 'Bluetooth', 'Security', 'Theme',
    'Keyboard', 'Mouse', 'Wallpaper', 'Startup', 'Cleanup',
    'Kernel', 'VPN', 'SSH', 'Network Shares', 'Cron', 'Backup',
    'USB', 'Diagnostics', 'Drivers'
]


STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QStackedWidget { background: #0a0a0a; }
QTextEdit { background: #0d0d0d; color: #00e5ff; border: 1px solid #1a4a4a; font-size: 11px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 8px; padding: 6px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""


def run_cmd(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return "N/A"


from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush


# ---------------------------------------------------------------------------
# Diagnostics page (embedded from vice_diagnostics.py logic)
# ---------------------------------------------------------------------------

DIAG_TESTS = [
    ("Network Ping",       "ping -c 4 8.8.8.8 2>&1"),
    ("DNS Lookup",         "nslookup google.com 2>&1 || dig google.com 2>&1"),
    ("Network Interfaces", "ip -br addr 2>&1"),
    ("Routing Table",      "ip route 2>&1"),
    ("Open Ports",         "ss -tulnp 2>&1"),
    ("Disk Usage",         "df -h 2>&1 | grep -v 'tmpfs\\|loop\\|udev'"),
    ("Memory Info",        "free -h 2>&1"),
    ("Failed Services",    "systemctl list-units --state=failed --no-pager 2>&1"),
    ("Kernel Errors",      "dmesg --level=err,crit 2>&1 | tail -20 || journalctl -k -p err -n 20 2>&1"),
    ("Temperature",        "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1f°C\\n\",$1/1000}' || echo 'N/A'"),
    ("Run All",            None),
]


class _DiagWorker(QThread):
    line_out = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            proc = subprocess.Popen(self.cmd, shell=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                self.line_out.emit(line.rstrip())
            proc.wait()
            self.done.emit(proc.returncode == 0)
        except Exception as e:
            self.line_out.emit(f"Error: {e}")
            self.done.emit(False)


class DiagnosticsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._queue = []

        root = QVBoxLayout(self)
        title = QLabel("Network & System Diagnostics")
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin-bottom: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        for name, _ in DIAG_TESTS:
            item = QListWidgetItem(name)
            if name == "Run All":
                item.setForeground(QColor("#ff00ff"))
            self._list.addItem(item)
        ll.addWidget(self._list)

        self._run_btn = QPushButton("Run Selected")
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
        self._status.setStyleSheet("color: #888;")
        bottom.addWidget(self._status)
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
            self._queue = [(n, c) for n, c in DIAG_TESTS if c]
            self._output.clear()
            self._next()
            return
        cmd = next((c for n, c in DIAG_TESTS if n == name), None)
        if cmd:
            self._execute(name, cmd)

    def _next(self):
        if not self._queue:
            self._status.setText("All tests complete")
            self._progress.setVisible(False)
            self._run_btn.setEnabled(True)
            return
        name, cmd = self._queue.pop(0)
        self._output.append(f"\n{'='*45}\n>>> {name}\n{'='*45}")
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
        c = "#00ff88" if ok else "#ff4444"
        self._output.append(f'<span style="color:{c};">[{"PASS" if ok else "FAIL"}] {name}</span>')
        if chain:
            self._next()
        else:
            self._progress.setVisible(False)
            self._status.setText(f"Done: {name}")
            self._run_btn.setEnabled(True)


# ---------------------------------------------------------------------------
# Drivers page (embedded from vice_driver_manager.py logic)
# ---------------------------------------------------------------------------

class _DetectWorker(QThread):
    found = pyqtSignal(dict)
    done = pyqtSignal()

    def run(self):
        checks = [
            ("GPU", "NVIDIA", "lspci 2>/dev/null | grep -i nvidia", "nvidia-driver-535",
             "dpkg -l nvidia-driver* 2>/dev/null | grep '^ii' | head -1"),
            ("GPU", "AMD",    "lspci 2>/dev/null | grep -i 'amd\\|ati' | grep -i 'vga\\|3d'",
             "firmware-amd-graphics",
             "dpkg -l firmware-amd-graphics 2>/dev/null | grep '^ii' | head -1"),
            ("GPU", "Intel",  "lspci 2>/dev/null | grep -i intel | grep -i 'vga\\|3d'",
             "intel-media-va-driver",
             "dpkg -l intel-media-va-driver* 2>/dev/null | grep '^ii' | head -1"),
        ]
        for dtype, vendor, detect_cmd, rec_pkg, inst_cmd in checks:
            out = run_cmd(detect_cmd)
            if out:
                inst = run_cmd(inst_cmd)
                pkg = inst.split()[1] if inst and inst != "N/A" else ""
                self.found.emit({
                    "type": dtype, "vendor": vendor,
                    "device": out.splitlines()[0].split(":")[-1].strip()[:60],
                    "installed": pkg or "None",
                    "recommended": rec_pkg,
                    "status": "Installed" if pkg else "Not Installed",
                })

        wifi_out = run_cmd("lspci 2>/dev/null | grep -i 'network\\|wireless'")
        if not wifi_out:
            wifi_out = run_cmd("lsusb 2>/dev/null | grep -i 'wireless\\|wifi'")
        if wifi_out:
            for line in wifi_out.splitlines():
                vendor = ("Broadcom" if "broadcom" in line.lower() else
                          "Realtek" if "realtek" in line.lower() else
                          "Intel" if "intel" in line.lower() else "Generic")
                pkg_map = {"Broadcom": "broadcom-sta-dkms",
                           "Realtek": "firmware-realtek",
                           "Intel": "firmware-iwlwifi",
                           "Generic": "firmware-linux-nonfree"}
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
        self.done.emit()


class _InstallWorker(QThread):
    line_out = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, pkg, remove=False):
        super().__init__()
        self.pkg = pkg
        self.remove = remove

    def run(self):
        op = "remove -y" if self.remove else "install -y"
        cmd = f"sudo apt {op} {self.pkg}"
        self.line_out.emit(f"$ {cmd}")
        try:
            proc = subprocess.Popen(cmd, shell=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                self.line_out.emit(line.rstrip())
            proc.wait()
            self.done.emit(proc.returncode == 0)
        except Exception as e:
            self.line_out.emit(f"Error: {e}")
            self.done.emit(False)


class DriversPage(QWidget):
    def __init__(self):
        super().__init__()
        from PyQt5.QtWidgets import QSplitter
        self._drivers = []
        self._workers = []

        root = QVBoxLayout(self)
        title = QLabel("Driver Manager")
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin-bottom: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter)

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
        self._scan_btn.clicked.connect(self._scan)
        btns.addWidget(self._scan_btn)
        self._inst_btn = QPushButton("Install")
        self._inst_btn.clicked.connect(self._install)
        btns.addWidget(self._inst_btn)
        self._rem_btn = QPushButton("Remove")
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
        splitter.setSizes([380, 180])

        status_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        status_row.addWidget(self._progress)
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888;")
        status_row.addWidget(self._status)
        root.addLayout(status_row)

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
                item.setForeground(QBrush(QColor("#00ff88" if info[key] == "Installed" else "#ff4444")))
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
        if QMessageBox.question(self, "Install", f"Install: {pkg}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
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
        if QMessageBox.question(self, "Remove", f"Remove: {pkg}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
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
        c = "#00ff88" if ok else "#ff4444"
        self._log.append(f'<span style="color:{c};">[{op} {"OK" if ok else "FAILED"}] {pkg}</span>')
        self._status.setText(f"{op} {'succeeded' if ok else 'failed'}: {pkg}")
        if ok:
            self._scan()


# ---------------------------------------------------------------------------
# Main Settings window
# ---------------------------------------------------------------------------

# Each non-embedded settings page launches its dedicated Vice OS app.
PAGE_APPS = {
    'Display':       'vice_display_manager.py',
    'Sound':         'vice_audio_manager.py',
    'Network':       'vice_wifi_connect.py',
    'Users':         'vice_user_manager.py',
    'Power':         'vice_power_manager.py',
    'Firewall':      'vice_firewall_manager.py',
    'Printers':      'vice_printer_manager.py',
    'Date & Time':   'vice_calendar.py',
    'Accessibility': 'vice_accessibility.py',
    'Storage':       'vice_disk_manager.py',
    'Updates':       'vice_update_manager.py',
    'Bluetooth':     'vice_bluetooth_manager.py',
    'Security':      'vice_firewall_manager.py',
    'Theme':         'vice_theme_manager.py',
    'Keyboard':      'vice_keyboard_shortcuts.py',
    'Mouse':         'vice_mouse_settings.py',
    'Cleanup':       'vice_cleanup.py',
    'Kernel':        'vice_kernel_manager.py',
    'Startup':       'vice_startup_apps.py',
    'VPN':           'vice_vpn_manager.py',
    'SSH':           'vice_ssh_manager.py',
    'Wallpaper':     'vice_wallpaper_picker.py',
    'Network Shares': 'vice_network_shares.py',
    'Cron':          'vice_cron_manager.py',
    'Backup':        'vice_backup_scheduler.py',
    'USB':           'vice_usb_manager.py',
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))


class AppLauncherPage(QWidget):
    """A settings page that offers to launch the dedicated app for this area."""

    def __init__(self, page_name, app_file):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("▸")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("color: #00ffff; font-size: 42px; border: none; background: transparent;")
        layout.addWidget(icon)

        label = QLabel(f"{page_name} is managed by")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 13px; border: none; background: transparent;")
        layout.addWidget(label)

        app_name = QLabel(f"Vice {app_file.replace('vice_', '').replace('.py', '').replace('_', ' ').title()}")
        app_name.setAlignment(Qt.AlignCenter)
        app_name.setStyleSheet("color: #00ffff; font-size: 17px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(app_name)

        layout.addSpacing(14)

        open_btn = QPushButton(f"Open {page_name} Settings")
        open_btn.setStyleSheet(
            "QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 8px 22px; font-size: 13px; }"
            "QPushButton:hover { background: #00ffff; color: #0a0a0a; }"
        )
        open_btn.clicked.connect(lambda: self._launch(app_file))
        layout.addWidget(open_btn, alignment=Qt.AlignCenter)

        hint = QLabel("The dedicated tool opens in its own window.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #555; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(hint)

    @staticmethod
    def _launch(app_file):
        path = os.path.join(APP_DIR, app_file)
        if os.path.exists(path):
            subprocess.Popen([sys.executable, path])
            log_info(f"Settings launched: {app_file}")
        else:
            log_error(f"Settings app missing: {path}")


class AboutPage(QWidget):
    """Real About page: OS, kernel, desktop suite info."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        logo = QLabel("VICE OS")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "color: #ff00ff; font-size: 42px; font-weight: bold; letter-spacing: 8px;"
            "border: none; background: transparent;"
        )
        layout.addWidget(logo)

        tagline = QLabel("GTA VI Edition — Cyberpunk Linux")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("color: #888; font-size: 13px; border: none; background: transparent;")
        layout.addWidget(tagline)

        layout.addSpacing(18)

        info = QGroupBox("System Information")
        info.setMinimumWidth(520)
        il = QVBoxLayout(info)

        rows = [
            ("OS", "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2"),
            ("Kernel", "uname -r"),
            ("Architecture", "uname -m"),
            ("Hostname", "uname -n"),
            ("Desktop", "echo 'PyQt5 custom suite (64 apps)'"),
            ("Uptime", "uptime -p"),
        ]
        for label, cmd in rows:
            try:
                value = subprocess.run(cmd, shell=True, capture_output=True,
                                      text=True, timeout=3).stdout.strip() or "—"
            except Exception:
                value = "—"
            row = QHBoxLayout()
            name_lbl = QLabel(f"{label}:")
            name_lbl.setFixedWidth(110)
            name_lbl.setStyleSheet("color: #ff00ff; border: none; background: transparent;")
            row.addWidget(name_lbl)
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet("color: #aaffff; border: none; background: transparent;")
            val_lbl.setWordWrap(True)
            row.addWidget(val_lbl, 1)
            il.addLayout(row)

        layout.addWidget(info, alignment=Qt.AlignCenter)

        license_lbl = QLabel("Debian Bookworm base • PyQt5 • MIT License")
        license_lbl.setAlignment(Qt.AlignCenter)
        license_lbl.setStyleSheet("color: #555; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(license_lbl)


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS Settings")
        self.setFixedSize(SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_ui()

    def _init_ui(self):
        root = QHBoxLayout(self)

        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        for name in PAGE_NAMES:
            self._nav.addItem(name)
        self._nav.currentRowChanged.connect(self._switch_page)
        root.addWidget(self._nav)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        for name in PAGE_NAMES:
            if name == 'Diagnostics':
                self._stack.addWidget(DiagnosticsPage())
            elif name == 'Drivers':
                self._stack.addWidget(DriversPage())
            elif name == 'About':
                self._stack.addWidget(AboutPage())
            elif name in PAGE_APPS:
                self._stack.addWidget(AppLauncherPage(name, PAGE_APPS[name]))
            else:
                placeholder = QWidget()
                pl = QVBoxLayout(placeholder)
                lbl = QLabel(f"{name} settings coming soon.")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet("color: #444; font-size: 14px;")
                pl.addWidget(lbl)
                self._stack.addWidget(placeholder)

        self._nav.setCurrentRow(0)

    def _switch_page(self, index):
        self._stack.setCurrentIndex(index)


def main():
    app = QApplication(sys.argv)
    win = SettingsWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
