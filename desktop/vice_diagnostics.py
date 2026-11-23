#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Diagnostics Center.
Hardware, network, kernel, and system diagnostic test suite with live logging and report export.
"""

import datetime
import os
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info, log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 680

DIAGNOSTICS = [
    ("Network Ping", "ping -c 4 8.8.8.8 2>&1"),
    ("DNS Lookup", "nslookup google.com 2>&1 || dig google.com 2>&1"),
    ("Network Interfaces", "ip -br addr 2>&1"),
    ("Routing Table", "ip route 2>&1"),
    ("Open Ports", "ss -tulnp 2>&1"),
    ("Disk Health (SMART)", "smartctl -H /dev/sda 2>&1 || echo 'smartctl not available or no /dev/sda'"),
    ("Disk Usage", "df -h 2>&1 | grep -v 'tmpfs\\|loop\\|udev'"),
    ("Memory Info", "free -h 2>&1"),
    ("CPU Stress Test", "timeout 3 sha256sum /dev/zero >/dev/null 2>&1; echo 'CPU stress test complete'"),
    ("Failed Services", "systemctl list-units --state=failed --no-pager 2>&1"),
    ("Kernel Errors", "dmesg --level=err,crit,alert,emerg 2>&1 | tail -20 || journalctl -k -p err -n 20 2>&1"),
    ("Journal Errors", "journalctl -p err -n 30 --no-pager 2>&1"),
    ("GPU Info", "lspci 2>&1 | grep -i 'vga\\|3d\\|display'"),
    ("USB Devices", "lsusb 2>&1"),
    ("PCI Devices", "lspci 2>&1"),
    ("Firewall Status", "ufw status verbose 2>&1 || iptables -L -n 2>&1 | head -20"),
    ("Temperature", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1fC\\n\",$1/1000}' || echo 'N/A'"),
    ("Bluetooth Status", "systemctl status bluetooth 2>&1 | head -10"),
    ("Audio Devices", "pactl list sinks short 2>&1 || aplay -l 2>&1"),
    ("Run All", None),
]


class DiagWorker(QThread):
    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool)

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
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
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


class DiagnosticsGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Diagnostics")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 520)
        apply_app_theme(self)
        self._worker = None
        self._all_queue = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Diagnostics Center",
            subtitle="Run network, disk, kernel, hardware, and systemd health checks",
            icon_name="utilities-system-monitor",
            badge_text="DIAGNOSTICS",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel("Diagnostic Tests")
        list_label.setObjectName("SectionTitle")
        left_layout.addWidget(list_label)

        self._list = QListWidget()
        for name, _ in DIAGNOSTICS:
            item = QListWidgetItem(name)
            if name == "Run All":
                item.setForeground(QColor(COLORS["accent_peach"]))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self._list.addItem(item)
        left_layout.addWidget(self._list)

        self._run_btn = make_button("Run Selected", variant="primary", parent=self)
        self._run_btn.clicked.connect(self._run_selected)
        left_layout.addWidget(self._run_btn)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        out_label = QLabel("Output")
        out_label.setObjectName("SectionTitle")
        right_layout.addWidget(out_label)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        right_layout.addWidget(self._output)

        splitter.addWidget(right)
        splitter.setSizes([260, 680])

        bottom = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        bottom.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        bottom.addWidget(self._status)

        clear_btn = make_button("Clear", variant="secondary", parent=self)
        clear_btn.clicked.connect(self._output.clear)
        bottom.addWidget(clear_btn)

        export_btn = make_button("Export", variant="secondary", parent=self)
        export_btn.clicked.connect(self._export)
        bottom.addWidget(export_btn)

        root.addLayout(bottom)

    def _run_selected(self):
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection", "Select a diagnostic test first.")
            return

        name = item.text()
        if name == "Run All":
            self._run_all()
            return

        cmd = next((c for n, c in DIAGNOSTICS if n == name), None)
        if cmd:
            self._all_queue.clear()
            self._execute(name, cmd)

    def _run_all(self):
        self._output.clear()
        self._all_queue = [(n, c) for n, c in DIAGNOSTICS if c is not None]
        self._run_next_in_queue()

    def _run_next_in_queue(self):
        if not self._all_queue:
            self._status.setText("All tests complete")
            self._progress.setVisible(False)
            self._run_btn.setEnabled(True)
            return
        name, cmd = self._all_queue.pop(0)
        self._output.append(f"\n{'=' * 50}\n>>> {name}\n{'=' * 50}")
        self._execute(name, cmd, chain=True)

    def _execute(self, name, cmd, chain=False):
        if self._worker is not None and self._worker.isRunning():
            return
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText(f"Running: {name}")

        self._worker = DiagWorker(cmd)
        self._worker.output_line.connect(self._output.append)
        self._worker.finished.connect(lambda ok: self._done(ok, name, chain))
        self._worker.start()

    def _done(self, ok, name, chain=False):
        color = COLORS["success"] if ok else COLORS["danger"]
        self._output.append(f'<span style="color:{color};">[{"PASS" if ok else "FAIL"}] {name}</span>')
        log_info(f"Diagnostic {name}: {'pass' if ok else 'fail'}")

        if chain and self._all_queue:
            self._run_next_in_queue()
        else:
            self._progress.setVisible(False)
            self._status.setText("All tests complete" if chain else f"Done: {name}")
            self._run_btn.setEnabled(True)

    def _export(self):
        path = os.path.expanduser(
            f"~/vice_diagnostics_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self._output.toPlainText())
            log_info(f"Diagnostics exported to {path}")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")

    def closeEvent(self, event):
        self._all_queue.clear()
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = DiagnosticsGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
