#!/usr/bin/env python3
"""Vice OS — Kernel Manager. List installed kernels, running kernel, purge old."""

import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QProgressBar, QPlainTextEdit
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
WINDOW_HEIGHT = 600


def _priv_cmd(cmd):
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if not is_root and shutil.which("pkexec"):
        return ["pkexec"] + list(cmd)
    return list(cmd)


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
        pkg = parts[1]
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
    """Run privileged kernel actions (purge or GRUB update) off the UI thread."""
    line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cmd):
        super().__init__()
        self._cmd = list(cmd)
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
        self.line.emit("$ " + " ".join(self._cmd))
        try:
            self._proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in self._proc.stdout:
                if self._stopped:
                    break
                self.line.emit(line.rstrip())
            self._proc.wait()
            if not self._stopped:
                self.finished.emit(self._proc.returncode == 0)
        except Exception as e:
            if not self._stopped:
                self.line.emit(f"Error: {e}")
                self.finished.emit(False)
        finally:
            self._proc = None


class KernelManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Kernel Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 480)
        apply_app_theme(self)
        self._worker = None
        self._kernels = []
        self._running = ""
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Kernel Manager",
            subtitle="Inspect installed Linux kernels, GRUB default entry, and safely remove old kernels",
            icon_name="applications-system",
            badge_text="KERNEL",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        self._running_label = QLabel("Running: ...")
        self._running_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        root.addWidget(self._running_label)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Version", "Status", "Packages Size", "Boot Default"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)

        set_default_btn = make_button("Set as Boot Default", variant="primary", parent=self)
        set_default_btn.clicked.connect(self._set_default)
        btn_row.addWidget(set_default_btn)

        remove_btn = make_button("Remove Selected Kernel", variant="danger", parent=self)
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
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _refresh(self):
        self._running = get_running_kernel()
        self._running_label.setText(f"Running: {self._running or 'unknown'}")
        self._kernels = get_installed_kernels()

        default_kernel = ""
        if shutil.which("grub-editenv"):
            out, _ = run_cmd(["grub-editenv", "list"])
            for line in out.splitlines():
                if line.startswith("saved_entry=") or line.startswith("kernel="):
                    default_kernel = line.split("=", 1)[1].strip()

        self._table.setRowCount(0)
        for kern in self._kernels:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(kern))

            if kern == self._running:
                status = "RUNNING"
                color = COLORS["success"]
            else:
                status = "Installed"
                color = COLORS["text_muted"]
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QBrush(QColor(color)))
            self._table.setItem(row, 1, status_item)

            size = kernel_size(kern)
            self._table.setItem(row, 2, QTableWidgetItem(fmt_size(size) if size else "—"))

            is_default = (default_kernel and kern in default_kernel) or (not default_kernel and kern == self._running)
            default_item = QTableWidgetItem("Yes" if is_default else "No")
            if is_default:
                default_item.setForeground(QBrush(QColor(COLORS["accent_peach"])))
            self._table.setItem(row, 3, default_item)

        self._status.setText(f"{len(self._kernels)} kernel(s) installed")

    def _selected_kernel(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._kernels):
            QMessageBox.warning(self, "No Selection", "Select a kernel first.")
            return None
        return self._kernels[row]

    def _run_worker(self, cmd, slot):
        if self._worker is not None and self._worker.isRunning():
            self._status.setText("Another operation is already running...")
            return
        self._progress.setVisible(True)
        self._worker = KernelWorker(cmd)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.finished.connect(slot)
        self._worker.start()

    def _set_default(self):
        kern = self._selected_kernel()
        if not kern:
            return
        if QMessageBox.question(
            self, "Set Default",
            f"Set kernel {kern} as default for next boot?\n(Updates GRUB saved_entry and regenerates config)",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        entry = f"Advanced options for GNU/Linux>GNU/Linux, with Linux {kern}"
        cmd = _priv_cmd(["bash", "-c", 'grub-editenv - set "saved_entry=$1" && update-grub', "vice-kernel", entry])
        self._status.setText(f"Updating GRUB default to {kern}...")
        self._run_worker(cmd, lambda ok: self._default_done(ok, kern))

    def _default_done(self, ok, kern):
        self._progress.setVisible(False)
        if ok:
            self._status.setText(f"Default set to {kern}")
            self._log.appendPlainText("[OK] GRUB updated")
            log_info(f"Kernel default set: {kern}")
        else:
            self._status.setText("Failed to set default")
            self._log.appendPlainText("[FAIL] Check output log")
        self._refresh()

    def _remove_selected(self):
        kern = self._selected_kernel()
        if not kern:
            return
        if kern == self._running:
            QMessageBox.warning(
                self, "Cannot Remove",
                f"Kernel {kern} is currently RUNNING and cannot be removed."
            )
            return
        if len(self._kernels) <= 1:
            QMessageBox.warning(self, "Cannot Remove", "At least one kernel must remain installed.")
            return
        if QMessageBox.question(
            self, "Remove Kernel",
            f"Remove kernel {kern}?\nThis purges linux-image-{kern} and linux-headers-{kern}.\n"
            "This action requires administrator privileges.",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        pkgs = [f"linux-image-{kern}", f"linux-headers-{kern}"]
        cmd = _priv_cmd(["bash", "-c", 'DEBIAN_FRONTEND=noninteractive apt-get purge -y "$@" && update-grub', "vice-kernel"] + pkgs)
        self._status.setText(f"Removing kernel {kern}...")
        self._run_worker(cmd, self._remove_done)

    def _remove_done(self, ok):
        self._progress.setVisible(False)
        if ok:
            self._status.setText("Kernel removed")
            self._log.appendPlainText("[OK] Kernel purged and GRUB updated")
            log_info("Old kernel removed")
        else:
            self._status.setText("Removal failed — check log")
        self._refresh()

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = KernelManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
