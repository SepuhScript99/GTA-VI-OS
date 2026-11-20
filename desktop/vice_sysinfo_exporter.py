#!/usr/bin/env python3
"""Vice OS — System Info Exporter. Full system inventory export to JSON/CSV/HTML."""

import sys
import os
import subprocess
import json
import csv
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QCheckBox, QFileDialog, QMessageBox, QProgressBar,
    QGroupBox, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QCheckBox { color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QLabel { color: #00ffff; }
"""

SECTIONS = [
    ("OS", "cat /etc/os-release 2>/dev/null"),
    ("Kernel", "uname -r; uname -m; uname -n"),
    ("Uptime", "uptime -p"),
    ("CPU", "lscpu 2>/dev/null | grep -E '^(Model name|CPU\\(s\\)|Thread|Core|Socket|CPU max MHz|Virtualization)'"),
    ("CPU Usage", "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4\"%\"}'"),
    ("Memory", "free -h 2>/dev/null"),
    ("Swap", "swapon --show 2>/dev/null || echo 'No swap'"),
    ("Disk", "df -h 2>/dev/null | grep -v 'tmpfs\\|loop\\|udev'"),
    ("Disk IO", "iostat -d 1 1 2>/dev/null | tail -n +4 || echo 'iostat not available'"),
    ("GPU", "lspci 2>/dev/null | grep -i 'vga\\|3d\\|display'"),
    ("Audio", "pactl info 2>/dev/null | grep -E 'Server Name|Default Sink|Default Source' || echo 'PulseAudio not running'"),
    ("Network Interfaces", "ip -br addr 2>/dev/null"),
    ("Routing", "ip route 2>/dev/null"),
    ("Open Ports", "ss -tulnp 2>/dev/null | head -30"),
    ("Temperature", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1f°C\\n\", $1/1000}' | head -6 || echo 'N/A'"),
    ("Processes", "ps aux --sort=-%cpu 2>/dev/null | head -10"),
    ("Failed Services", "systemctl list-units --state=failed --no-pager 2>/dev/null | head -10 || echo 'None'"),
    ("Packages", "dpkg -l 2>/dev/null | wc -l && echo ' packages installed'"),
    ("Loaded Modules", "lsmod 2>/dev/null | wc -l && echo ' modules loaded'"),
    ("USB Devices", "lsusb 2>/dev/null"),
    ("PCI Devices", "lspci 2>/dev/null | head -20"),
    ("Mounts", "mount | grep -E '^/dev'"),
    ("Environment", "env 2>/dev/null | sort"),
    ("Crontab", "crontab -l 2>/dev/null || echo 'No crontab'"),
    ("User Accounts", "getent passwd | awk -F: '$3 >= 1000 {print $1}' 2>/dev/null"),
    ("Groups", "getent group | awk -F: '$3 >= 1000 {print $1}' 2>/dev/null"),
    ("Ulimit", "ulimit -a 2>/dev/null"),
    ("SELinux/AppArmor", "sestatus 2>/dev/null || aa-status 2>/dev/null || echo 'Not available'"),
]


def run_cmd(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return "N/A"


class ExportWorker(QThread):
    progress = pyqtSignal(int)
    line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, output_path, fmt, sections):
        super().__init__()
        self.output_path = output_path
        self.fmt = fmt
        self.sections = sections

    def run(self):
        data = {}
        total = len(self.sections)
        for i, (name, cmd) in enumerate(self.sections):
            self.line.emit("Collecting: " + name)
            output = run_cmd(cmd)
            data[name] = output
            self.progress.emit(int((i + 1) / total * 100))

        try:
            if self.fmt == "JSON":
                with open(self.output_path, "w") as f:
                    json.dump(data, f, indent=2)
            elif self.fmt == "CSV":
                with open(self.output_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Section", "Data"])
                    for k, v in data.items():
                        writer.writerow([k, v])
            elif self.fmt == "HTML":
                with open(self.output_path, "w") as f:
                    f.write("<!DOCTYPE html><html><head><title>Vice OS System Report</title>")
                    f.write("<style>body{font-family:monospace;background:#0a0a0a;color:#00ffff;padding:20px}h1{color:#ff00ff}.section{border:1px solid #00ffff;margin:20px 0;padding:10px}h2{color:#00ffff}pre{background:#0d0d0d;padding:10px;overflow:auto}</style>")
                    f.write("</head><body>")
                    f.write("<h1>Vice OS System Report</h1>")
                    f.write("<p>Generated: " + datetime.datetime.now().isoformat() + "</p>")
                    for k, v in data.items():
                        f.write('<div class="section"><h2>' + k + '</h2><pre>' + v.replace("&", "&").replace("<", "<").replace(">", ">") + '</pre></div>')
                    f.write("</body></html>")
            self.finished.emit(True, "Export complete: " + self.output_path)
        except Exception as e:
            self.finished.emit(False, "Export failed: " + str(e))


class SystemInfoExporter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — System Info Exporter")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — System Info Exporter")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Format selection
        fmt_box = QGroupBox("Export Format")
        fl = QHBoxLayout(fmt_box)
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["JSON", "CSV", "HTML"])
        fl.addWidget(QLabel("Format:"))
        fl.addWidget(self._fmt_combo)
        root.addWidget(fmt_box)

        # Sections selection
        sec_box = QGroupBox("Sections to Export")
        sl = QVBoxLayout(sec_box)
        self._checks = {}
        for name, _ in SECTIONS:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._checks[name] = cb
            sl.addWidget(cb)
        root.addWidget(sec_box)

        # Select all / none
        sel_row = QHBoxLayout()
        all_btn = QPushButton("Select All")
        all_btn.clicked.connect(lambda: [c.setChecked(True) for c in self._checks.values()])
        sel_row.addWidget(all_btn)
        none_btn = QPushButton("Select None")
        none_btn.clicked.connect(lambda: [c.setChecked(False) for c in self._checks.values()])
        sel_row.addWidget(none_btn)
        sel_row.addStretch()
        root.addLayout(sel_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Buttons
        btn_row = QHBoxLayout()
        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._export)
        btn_row.addWidget(self._export_btn)

        btn_row.addStretch()

        preview_btn = QPushButton("Preview JSON")
        preview_btn.clicked.connect(self._preview)
        btn_row.addWidget(preview_btn)
        root.addLayout(btn_row)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        root.addWidget(self._log)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _export(self):
        selected = [s for s in SECTIONS if self._checks[s[0]].isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Sections", "Select at least one section.")
            return

        fmt = self._fmt_combo.currentText()
        ext = fmt.lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", os.path.expanduser("~/vice_system_report." + ext),
            f"{fmt} (*.{ext});;All files (*)"
        )
        if not path:
            return

        self._export_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._log.clear()

        self._worker = ExportWorker(path, fmt, selected)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.line.connect(self._log.append)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok, msg):
        self._export_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._log.append(msg)
        self._status.setText(msg)
        if ok:
            log_info(msg)
            QMessageBox.information(self, "Export Complete", msg)
        else:
            log_error(msg)

    def _preview(self):
        selected = [s for s in SECTIONS if self._checks[s[0]].isChecked()]
        self._log.clear()
        for name, cmd in selected:
            self._log.append("=== " + name + " ===")
            self._log.append(run_cmd(cmd))
            self._log.append("")


def main():
    app = QApplication(sys.argv)
    win = SystemInfoExporter()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()