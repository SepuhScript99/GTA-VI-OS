#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Hardware Driver Manager.
Detects GPU (NVIDIA/AMD/Intel) and wireless chipsets with one-click driver installation.
"""

import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar,
    QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 680


def run_cmd(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), 1


class DetectWorker(QThread):
    driver_found = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _dpkg_installed(self, pattern):
        out, _ = run_cmd("dpkg -l 2>/dev/null | awk '$1==\"ii\"{print $2}'")
        for line in out.splitlines():
            if re.match(pattern, line.strip()):
                return line.strip()
        return ""

    def run(self):
        pci_out, _ = run_cmd(["lspci"] if shutil.which("lspci") else "lspci 2>/dev/null")
        usb_out, _ = run_cmd(["lsusb"] if shutil.which("lsusb") else "lsusb 2>/dev/null")

        # NVIDIA
        for line in pci_out.splitlines():
            if self._stopped:
                return
            if "nvidia" in line.lower():
                pkg = self._dpkg_installed(r"^nvidia-driver")
                self.driver_found.emit({
                    "type": "GPU",
                    "vendor": "NVIDIA",
                    "device": line.split(":")[-1].strip()[:60],
                    "installed": pkg or "None",
                    "recommended": "nvidia-driver",
                    "status": "Installed" if pkg else "Not Installed",
                })
                break

        # AMD GPU
        for line in pci_out.splitlines():
            if self._stopped:
                return
            low = line.lower()
            if ("amd" in low or "ati" in low) and any(k in low for k in ("vga", "3d", "display")):
                pkg = self._dpkg_installed(r"^firmware-amd-graphics$")
                self.driver_found.emit({
                    "type": "GPU",
                    "vendor": "AMD",
                    "device": line.split(":")[-1].strip()[:60],
                    "installed": pkg or "None",
                    "recommended": "firmware-amd-graphics",
                    "status": "Installed" if pkg else "Not Installed",
                })
                break

        # Intel GPU
        for line in pci_out.splitlines():
            if self._stopped:
                return
            low = line.lower()
            if "intel" in low and any(k in low for k in ("vga", "3d", "display")):
                pkg = self._dpkg_installed(r"^intel-media-va-driver")
                self.driver_found.emit({
                    "type": "GPU",
                    "vendor": "Intel",
                    "device": line.split(":")[-1].strip()[:60],
                    "installed": pkg or "None",
                    "recommended": "intel-media-va-driver",
                    "status": "Installed" if pkg else "Not Installed",
                })
                break

        # WiFi
        wifi_lines = [ln for ln in pci_out.splitlines() if any(k in ln.lower() for k in ("network", "wireless", "wifi"))]
        if not wifi_lines:
            wifi_lines = [ln for ln in usb_out.splitlines() if any(k in ln.lower() for k in ("wireless", "wifi", "802.11"))]
        for line in wifi_lines:
            if self._stopped:
                return
            low = line.lower()
            vendor = (
                "Broadcom" if "broadcom" in low else
                "Realtek" if "realtek" in low else
                "Intel" if "intel" in low else "WiFi"
            )
            pkg_map = {
                "Broadcom": "broadcom-sta-dkms",
                "Realtek": "firmware-realtek",
                "Intel": "firmware-iwlwifi",
            }
            pkg = pkg_map.get(vendor, "firmware-linux-nonfree")
            inst = self._dpkg_installed(f"^{re.escape(pkg)}$")
            self.driver_found.emit({
                "type": "WiFi",
                "vendor": vendor,
                "device": line.split(":")[-1].strip()[:60],
                "installed": inst or "None",
                "recommended": pkg,
                "status": "Installed" if inst else "Not Installed",
            })

        # Bluetooth
        for line in usb_out.splitlines():
            if self._stopped:
                return
            if "bluetooth" in line.lower():
                pkg = self._dpkg_installed(r"^bluez$")
                self.driver_found.emit({
                    "type": "Bluetooth",
                    "vendor": "Generic",
                    "device": line.split(":")[-1].strip()[:60],
                    "installed": pkg or "None",
                    "recommended": "bluez",
                    "status": "Installed" if pkg else "Not Installed",
                })
                break

        if not self._stopped:
            self.finished.emit()


class InstallWorker(QThread):
    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, pkg, op="install"):
        super().__init__()
        self.pkg = pkg
        self.op = op if op in ("install", "remove") else "install"
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
        if not re.match(r"^[a-zA-Z0-9.+_:-]+$", self.pkg):
            self.output_line.emit(f"Invalid package name: {self.pkg}")
            self.finished.emit(False)
            return
        cmd = ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", self.op, "-y", self.pkg]
        if (os.geteuid() != 0 if hasattr(os, "geteuid") else True) and shutil.which("pkexec"):
            cmd = ["pkexec"] + cmd
        self.output_line.emit(f"Running: {' '.join(cmd)}\n")
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in self._proc.stdout:
                if self._stopped:
                    break
                self.output_line.emit(line.rstrip())
            self._proc.wait()
            if not self._stopped:
                self.finished.emit(self._proc.returncode == 0)
        except Exception as e:
            if not self._stopped:
                self.output_line.emit(f"Error: {e}")
                self.finished.emit(False)
        finally:
            self._proc = None


class DriverManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Driver Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 520)
        apply_app_theme(self)
        self._drivers = []
        self._workers = []
        self._init_ui()
        self._scan()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Hardware Driver Manager",
            subtitle="Detect GPU, wireless, and Bluetooth hardware and manage Debian drivers",
            icon_name="preferences-desktop-display",
            badge_text="DRIVERS",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter, 1)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Type", "Vendor", "Device", "Installed", "Recommended", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        top_layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._scan_btn = make_button("Scan Devices", variant="secondary", parent=self)
        self._scan_btn.clicked.connect(self._scan)
        btn_row.addWidget(self._scan_btn)

        self._install_btn = make_button("Install Driver", variant="primary", parent=self)
        self._install_btn.clicked.connect(self._install_selected)
        btn_row.addWidget(self._install_btn)

        self._remove_btn = make_button("Remove Driver", variant="danger", parent=self)
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._remove_btn)

        btn_row.addStretch()
        top_layout.addLayout(btn_row)
        splitter.addWidget(top)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        log_label = QLabel("Output Log")
        log_label.setObjectName("SectionTitle")
        bottom_layout.addWidget(log_label)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        bottom_layout.addWidget(self._log)
        splitter.addWidget(bottom)
        splitter.setSizes([400, 220])

        status_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        status_row.addWidget(self._progress)
        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        status_row.addWidget(self._status)
        clear_btn = make_button("Clear Log", variant="secondary", parent=self)
        clear_btn.clicked.connect(self._log.clear)
        status_row.addWidget(clear_btn)
        root.addLayout(status_row)

    def _scan(self):
        self._table.setRowCount(0)
        self._drivers.clear()
        self._scan_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Scanning hardware...")
        self._log.append("Scanning for hardware devices...")

        w = DetectWorker()
        w.driver_found.connect(self._add_driver)
        w.finished.connect(self._scan_done)
        self._workers.append(w)
        w.start()

    def _add_driver(self, info):
        self._drivers.append(info)
        row = self._table.rowCount()
        self._table.insertRow(row)

        cols = [
            info["type"], info["vendor"], info["device"],
            info["installed"], info["recommended"], info["status"],
        ]
        for col, val in enumerate(cols):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if col == 5:
                col_hex = COLORS["success"] if val == "Installed" else COLORS["danger"]
                item.setForeground(QBrush(QColor(col_hex)))
            self._table.setItem(row, col, item)

    def _scan_done(self):
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)
        count = self._table.rowCount()
        self._status.setText(f"Scan complete — {count} device(s) found")
        self._log.append(f"Scan complete. {count} device(s) detected.\n")
        log_info(f"Driver scan complete: {count} devices")

    def _get_selected_driver(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._drivers):
            QMessageBox.warning(self, "No Selection", "Select a device from the list first.")
            return None
        return self._drivers[row]

    def _install_selected(self):
        info = self._get_selected_driver()
        if not info:
            return
        pkg = info["recommended"]
        confirm = QMessageBox.question(
            self, "Install Driver",
            f"Install package: {pkg}\n\nThis requires administrator privileges.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        self._run_pkg_op(pkg, "install")

    def _remove_selected(self):
        info = self._get_selected_driver()
        if not info:
            return
        pkg = info["installed"]
        if pkg == "None":
            QMessageBox.information(self, "Not Installed", "No driver installed for this device.")
            return
        confirm = QMessageBox.question(
            self, "Remove Driver",
            f"Remove package: {pkg}\n\nThis requires administrator privileges.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        self._run_pkg_op(pkg, "remove")

    def _run_pkg_op(self, pkg, op):
        self._install_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText(f"{'Installing' if op == 'install' else 'Removing'}: {pkg}")

        w = InstallWorker(pkg, op=op)
        w.output_line.connect(self._log.append)
        w.finished.connect(lambda ok: self._op_done(ok, pkg, op))
        self._workers.append(w)
        w.start()

    def _op_done(self, ok, pkg, op):
        self._progress.setVisible(False)
        self._install_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)
        color = COLORS["success"] if ok else COLORS["danger"]
        result = "succeeded" if ok else "failed"
        self._log.append(f'<span style="color:{color};">[{op.upper()} {result.upper()}] {pkg}</span>')
        self._status.setText(f"{op.capitalize()} {result}: {pkg}")
        log_info(f"Driver {op} {result}: {pkg}")
        if ok:
            self._scan()

    def closeEvent(self, event):
        for w in self._workers:
            w.stop()
        for w in self._workers:
            if w.isRunning():
                w.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = DriverManager()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
