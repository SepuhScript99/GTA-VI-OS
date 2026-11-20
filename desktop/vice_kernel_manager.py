#!/usr/bin/env python3
"""Vice OS — Kernel Manager. List installed kernels, running kernel, purge old."""

import sys
import os
import subprocess
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QProgressBar, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QPlainTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QLabel { color: #00ffff; }
"""


def run_cmd(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_running_kernel():
    out, _ = run_cmd(["uname", "-r"])
    return out.strip()


def get_installed_kernels():
    """Return list of kernel version strings from dpkg."""
    out, _ = run_cmd(["dpkg", "-l"])
    kernels = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] != "ii":
            continue
        pkg, version = parts[1], parts[2]
        m = re.match(r"linux-(image|headers)-(\d+\.\d+\.\d+[\w.-]*)", pkg)
        if m:
            kernels.add(m.group(2))
    return sorted(kernels, reverse=True)


def kernel_size(version):
    out, _ = run_cmd(["dpkg", "-l"])
    total = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] == "ii" and version in parts[1]:
            m = re.search(r"(\d+),?(\d*)\s*kB", line)
            if m:
                kb = int(m.group(1) + (m.group(2) if m.group(2) else ""))
                total += kb
    return total


def fmt_size(kb):
    if kb >= 1024 * 1024:
        return f"{kb / 1024 / 1024:.1f} GB"
    if kb >= 1024:
        return f"{kb / 1024:.0f} MB"
    return f"{kb} kB"


class KernelWorker(QThread):
    """Remove old kernel packages (image + headers)."""
    line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, version):
        super().__init__()
        self._version = version

    def run(self):
        pkgs = [f"linux-image-{self._version}", f"linux-headers-{self._version}"]
        cmd = ["sudo", "apt", "purge", "-y"] + pkgs
        self.line.emit("$ " + " ".join(cmd))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                self.line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode == 0)
        except Exception as e:
            self.line.emit(f"Error: {e}")
            self.finished.emit(False)


class KernelManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Kernel Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._kernels = []
        self._running = ""
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Kernel Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Running kernel banner
        self._running_label = QLabel("Running: ...")
        self._running_label.setFont(QFont("monospace", 11, QFont.Bold))
        self._running_label.setStyleSheet("color: #00ff88; margin: 4px;")
        root.addWidget(self._running_label)

        # Kernel table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Version", "Status", "Packages Size", "Boot Default"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in [1, 2, 3]:
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)

        set_default_btn = QPushButton("Set as Boot Default")
        set_default_btn.clicked.connect(self._set_default)
        btn_row.addWidget(set_default_btn)

        remove_btn = QPushButton("Remove Selected Kernel")
        remove_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(130)
        root.addWidget(self._log)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._running = get_running_kernel()
        self._running_label.setText(f"Running: {self._running or 'unknown'}")
        self._kernels = get_installed_kernels()

        # Boot default from GRUB
        default_kernel = ""
        out, _ = run_cmd(["grub-editenv", "list"])
        for line in out.splitlines():
            if line.startswith("kernel="):
                default_kernel = line.split("=", 1)[1].split()[0].replace("/boot/vmlinuz-", "")

        self._table.setRowCount(0)
        for kern in self._kernels:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(kern))

            if kern == self._running:
                status = "● RUNNING"
                color = "#00ff88"
            else:
                status = "Installed"
                color = "#888888"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QBrush(QColor(color)))
            self._table.setItem(row, 1, status_item)

            size = kernel_size(kern)
            self._table.setItem(row, 2, QTableWidgetItem(fmt_size(size) if size else "—"))

            is_default = (default_kernel and kern in default_kernel) or kern == self._running
            default_item = QTableWidgetItem("Yes" if is_default else "No")
            if is_default:
                default_item.setForeground(QBrush(QColor("#ff00ff")))
            self._table.setItem(row, 3, default_item)

        self._status.setText(f"{len(self._kernels)} kernel(s) installed")

    def _selected_kernel(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._kernels):
            QMessageBox.warning(self, "No Selection", "Select a kernel first.")
            return None
        return self._kernels[row]

    def _set_default(self):
        kern = self._selected_kernel()
        if not kern:
            return
        if QMessageBox.question(
            self, "Set Default",
            f"Set kernel {kern} as default for next boot?\n"
            f"(Updates GRUB and regenerates config)",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._progress.setVisible(True)
        self._log.appendPlainText(f"$ grub-set-default 0 (with GRUB_DEFAULT=standard index for {kern})")
        # Pin specific kernel via grub-editenv saved_entry
        out, ok = run_cmd(["sudo", "grub-editenv", "set", "saved_entry=Advanced options for GNU/Linux>GNU/Linux, with Linux " + kern])
        # Also update GRUB config default
        out2, ok2 = run_cmd(["sudo", "update-grub"], timeout=60)
        self._progress.setVisible(False)
        if ok and ok2:
            self._status.setText(f"Default set to {kern}")
            self._log.appendPlainText("[OK] GRUB updated")
            log_info(f"Kernel default set: {kern}")
        else:
            self._status.setText("Failed to set default")
            self._log.appendPlainText(f"[FAIL] {out2[:200] or out[:200]}")
        self._refresh()

    def _remove_selected(self):
        kern = self._selected_kernel()
        if not kern:
            return
        if kern == self._running:
            QMessageBox.warning(self, "Cannot Remove",
                                f"Kernel {kern} is currently RUNNING and cannot be removed.")
            return
        if len(self._kernels) <= 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one kernel must remain installed.")
            return
        if QMessageBox.question(
            self, "Remove Kernel",
            f"Remove kernel {kern}?\nThis purges linux-image-{kern} and linux-headers-{kern}.\n"
            "This action requires sudo and cannot be undone easily.",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._progress.setVisible(True)
        self._worker = KernelWorker(kern)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.finished.connect(self._remove_done)
        self._worker.start()

    def _remove_done(self, ok):
        self._progress.setVisible(False)
        if ok:
            self._status.setText("Kernel removed")
            self._log.appendPlainText("[OK] Kernel purged — updating GRUB")
            run_cmd(["sudo", "update-grub"], timeout=60)
            log_info("Old kernel removed")
        else:
            self._status.setText("Removal failed — check log")
        self._refresh()


def main():
    app = QApplication(sys.argv)
    win = KernelManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()