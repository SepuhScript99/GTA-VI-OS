#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Diagnostics Center
Hardware, network, kernel, and system diagnostic test suite with live logging and report export.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QProgressBar, QTabWidget, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTextEdit { background: #0d0d0d; color: #00e5ff; border: 1px solid #1a4a4a; font-size: 11px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 8px; padding: 6px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QSplitter::handle { background: #00ffff; }
"""

DIAGNOSTICS = [
    ("Network Ping", "ping -c 4 8.8.8.8 2>&1"),
    ("DNS Lookup", "nslookup google.com 2>&1 || dig google.com 2>&1"),
    ("Network Interfaces", "ip -br addr 2>&1"),
    ("Routing Table", "ip route 2>&1"),
    ("Open Ports", "ss -tulnp 2>&1"),
    ("Disk Health (SMART)", "smartctl -H /dev/sda 2>&1 || echo 'smartctl not available or no /dev/sda'"),
    ("Disk Usage", "df -h 2>&1 | grep -v 'tmpfs\\|loop\\|udev'"),
    ("Memory Info", "free -h 2>&1"),
    ("CPU Stress Test", "timeout 3 yes > /dev/null & sleep 3 && kill %1 2>/dev/null; echo 'CPU stress test complete'"),
    ("Failed Services", "systemctl list-units --state=failed --no-pager 2>&1"),
    ("Kernel Errors", "dmesg --level=err,crit,alert,emerg 2>&1 | tail -20 || journalctl -k -p err -n 20 2>&1"),
    ("Journal Errors", "journalctl -p err -n 30 --no-pager 2>&1"),
    ("GPU Info", "lspci 2>&1 | grep -i 'vga\\|3d\\|display'"),
    ("USB Devices", "lsusb 2>&1"),
    ("PCI Devices", "lspci 2>&1"),
    ("Firewall Status", "ufw status verbose 2>&1 || iptables -L -n 2>&1 | head -20"),
    ("Temperature", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1f°C\\n\",$1/1000}' || echo 'N/A'"),
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

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd, shell=True,
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


class DiagnosticsGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Diagnostics")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Diagnostics Center")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 15, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: test list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel("Diagnostic Tests")
        list_label.setStyleSheet("color: #ff00ff; font-weight: bold;")
        left_layout.addWidget(list_label)

        self._list = QListWidget()
        for name, _ in DIAGNOSTICS:
            item = QListWidgetItem(name)
            if name == "Run All":
                item.setForeground(QColor("#ff00ff"))
                item.setFont(QFont("monospace", 10, QFont.Bold))
            self._list.addItem(item)
        left_layout.addWidget(self._list)

        self._run_btn = QPushButton("Run Selected")
        self._run_btn.clicked.connect(self._run_selected)
        left_layout.addWidget(self._run_btn)

        splitter.addWidget(left)

        # Right: output
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        out_label = QLabel("Output")
        out_label.setStyleSheet("color: #ff00ff; font-weight: bold;")
        right_layout.addWidget(out_label)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        right_layout.addWidget(self._output)

        splitter.addWidget(right)
        splitter.setSizes([260, 680])

        # Bottom bar
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

        export_btn = QPushButton("Export")
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
        self._output.append(f"\n{'='*50}\n>>> {name}\n{'='*50}")
        self._execute(name, cmd, chain=True)

    def _execute(self, name, cmd, chain=False):
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText(f"Running: {name}")

        self._worker = DiagWorker(cmd)
        self._worker.output_line.connect(self._output.append)
        self._worker.finished.connect(lambda ok: self._done(ok, name, chain))
        self._worker.start()

    def _done(self, ok, name, chain=False):
        color = "#00ff88" if ok else "#ff4444"
        self._output.append(f'<span style="color:{color};">[{"PASS" if ok else "FAIL"}] {name}</span>')
        log_info(f"Diagnostic {name}: {'pass' if ok else 'fail'}")

        if chain and hasattr(self, '_all_queue'):
            self._run_next_in_queue()
        else:
            self._progress.setVisible(False)
            self._status.setText(f"Done: {name}")
            self._run_btn.setEnabled(True)

    def _export(self):
        import datetime
        path = os.path.expanduser(
            f"~/vice_diagnostics_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        try:
            with open(path, "w") as f:
                f.write(self._output.toPlainText())
            log_info(f"Diagnostics exported to {path}")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")


def main():
    app = QApplication(sys.argv)
    window = DiagnosticsGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
