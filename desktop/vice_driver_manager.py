#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Hardware Driver Manager
Detects GPU (NVIDIA/AMD/Intel) and wireless chipsets with one-click driver installation.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar,
    QGroupBox, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTextEdit { background: #0d0d0d; color: #00e5ff; border: 1px solid #1a4a4a; font-size: 11px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 8px; padding: 6px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QSplitter::handle { background: #00ffff; width: 1px; }
QLabel { color: #00ffff; }
"""


def run_cmd(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), 1


class DetectWorker(QThread):
    driver_found = pyqtSignal(dict)
    finished = pyqtSignal()

    def run(self):
        # NVIDIA
        out, _ = run_cmd("lspci 2>/dev/null | grep -i nvidia")
        if out:
            installed, _ = run_cmd("dpkg -l nvidia-driver* 2>/dev/null | grep '^ii' | head -1")
            pkg = installed.split()[1] if installed else ""
            rec, _ = run_cmd("ubuntu-drivers devices 2>/dev/null | grep nvidia | grep recommended | awk '{print $3}'")
            self.driver_found.emit({
                "type": "GPU", "vendor": "NVIDIA",
                "device": out.split(":")[-1].strip()[:60],
                "installed": pkg or "None",
                "recommended": rec or "nvidia-driver-535",
                "status": "Installed" if pkg else "Not Installed",
            })

        # AMD GPU
        out, _ = run_cmd("lspci 2>/dev/null | grep -i 'amd\\|ati' | grep -i 'vga\\|3d\\|display'")
        if out:
            installed, _ = run_cmd("dpkg -l firmware-amd-graphics 2>/dev/null | grep '^ii' | head -1")
            pkg = installed.split()[1] if installed else ""
            self.driver_found.emit({
                "type": "GPU", "vendor": "AMD",
                "device": out.split(":")[-1].strip()[:60],
                "installed": pkg or "None",
                "recommended": "firmware-amd-graphics",
                "status": "Installed" if pkg else "Not Installed",
            })

        # Intel GPU
        out, _ = run_cmd("lspci 2>/dev/null | grep -i intel | grep -i 'vga\\|3d\\|display'")
        if out:
            installed, _ = run_cmd("dpkg -l intel-media-va-driver* 2>/dev/null | grep '^ii' | head -1")
            pkg = installed.split()[1] if installed else ""
            self.driver_found.emit({
                "type": "GPU", "vendor": "Intel",
                "device": out.split(":")[-1].strip()[:60],
                "installed": pkg or "None",
                "recommended": "intel-media-va-driver",
                "status": "Installed" if pkg else "Not Installed",
            })

        # WiFi
        out, _ = run_cmd("lspci 2>/dev/null | grep -i 'network\\|wireless\\|wifi'")
        if not out:
            out, _ = run_cmd("lsusb 2>/dev/null | grep -i 'wireless\\|wifi\\|802.11'")
        if out:
            for line in out.splitlines():
                vendor = "Broadcom" if "broadcom" in line.lower() else \
                         "Realtek" if "realtek" in line.lower() else \
                         "Intel" if "intel" in line.lower() else "WiFi"
                pkg_map = {
                    "Broadcom": "broadcom-sta-dkms",
                    "Realtek": "firmware-realtek",
                    "Intel": "firmware-iwlwifi",
                }
                pkg = pkg_map.get(vendor, "firmware-linux-nonfree")
                installed, _ = run_cmd(f"dpkg -l {pkg} 2>/dev/null | grep '^ii' | head -1")
                inst = installed.split()[1] if installed else ""
                self.driver_found.emit({
                    "type": "WiFi", "vendor": vendor,
                    "device": line.split(":")[-1].strip()[:60],
                    "installed": inst or "None",
                    "recommended": pkg,
                    "status": "Installed" if inst else "Not Installed",
                })

        # Bluetooth
        out, _ = run_cmd("lsusb 2>/dev/null | grep -i bluetooth")
        if out:
            installed, _ = run_cmd("dpkg -l bluez 2>/dev/null | grep '^ii' | head -1")
            pkg = installed.split()[1] if installed else ""
            self.driver_found.emit({
                "type": "Bluetooth", "vendor": "Generic",
                "device": out.split(":")[-1].strip()[:60],
                "installed": pkg or "None",
                "recommended": "bluez",
                "status": "Installed" if pkg else "Not Installed",
            })

        self.finished.emit()


class InstallWorker(QThread):
    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, pkg):
        super().__init__()
        self.pkg = pkg

    def run(self):
        self.output_line.emit(f"Running: sudo apt install -y {self.pkg}\n")
        try:
            proc = subprocess.Popen(
                f"sudo apt install -y {self.pkg}",
                shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True
            )
            for line in proc.stdout:
                self.output_line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode == 0)
        except Exception as e:
            self.output_line.emit(f"Error: {e}")
            self.finished.emit(False)


class DriverManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Driver Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._drivers = []
        self._workers = []
        self._init_ui()
        self._scan()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Driver Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 15, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter)

        # Top: driver table
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
        self._scan_btn = QPushButton("Scan Devices")
        self._scan_btn.clicked.connect(self._scan)
        btn_row.addWidget(self._scan_btn)

        self._install_btn = QPushButton("Install Driver")
        self._install_btn.clicked.connect(self._install_selected)
        btn_row.addWidget(self._install_btn)

        self._remove_btn = QPushButton("Remove Driver")
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._remove_btn)

        btn_row.addStretch()
        top_layout.addLayout(btn_row)
        splitter.addWidget(top)

        # Bottom: output log
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        log_label = QLabel("Output Log")
        log_label.setStyleSheet("color: #ff00ff; font-weight: bold;")
        bottom_layout.addWidget(log_label)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        bottom_layout.addWidget(self._log)
        splitter.addWidget(bottom)
        splitter.setSizes([420, 220])

        # Status bar
        status_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        status_row.addWidget(self._progress)
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888;")
        status_row.addWidget(self._status)
        clear_btn = QPushButton("Clear Log")
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

        cols = [info["type"], info["vendor"], info["device"],
                info["installed"], info["recommended"], info["status"]]
        for col, val in enumerate(cols):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if col == 5:
                if val == "Installed":
                    item.setForeground(QBrush(QColor("#00ff88")))
                else:
                    item.setForeground(QBrush(QColor("#ff4444")))
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
            f"Install package: {pkg}\n\nThis requires sudo privileges.",
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
            f"Remove package: {pkg}\n\nThis requires sudo privileges.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        self._run_pkg_op(pkg, "remove")

    def _run_pkg_op(self, pkg, op):
        self._install_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._progress.setVisible(True)
        cmd = f"sudo apt {'install -y' if op == 'install' else 'remove -y'} {pkg}"
        self._status.setText(f"{'Installing' if op == 'install' else 'Removing'}: {pkg}")

        w = InstallWorker(pkg if op == "install" else f"--remove {pkg}")
        w.output_line.connect(self._log.append)
        w.finished.connect(lambda ok: self._op_done(ok, pkg, op))
        self._workers.append(w)
        w.start()

    def _op_done(self, ok, pkg, op):
        self._progress.setVisible(False)
        self._install_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)
        color = "#00ff88" if ok else "#ff4444"
        result = "succeeded" if ok else "failed"
        self._log.append(f'<span style="color:{color};">[{op.upper()} {result.upper()}] {pkg}</span>')
        self._status.setText(f"{op.capitalize()} {result}: {pkg}")
        log_info(f"Driver {op} {result}: {pkg}")
        if ok:
            self._scan()


def main():
    app = QApplication(sys.argv)
    window = DriverManager()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
