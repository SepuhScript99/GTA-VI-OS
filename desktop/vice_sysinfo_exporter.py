#!/usr/bin/env python3
"""Vice OS — System Info Exporter. Full system inventory export to JSON/CSV/HTML."""

import csv
import datetime
import html
import json
import os
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 920
WINDOW_HEIGHT = 640

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
    ("Audio", "pactl info 2>/dev/null | grep -E 'Server Name|Default Sink|Default Source' || echo 'Audio unavailable'"),
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

    def __init__(self, output_path, fmt, sections, parent=None):
        super().__init__(parent)
        self.output_path = output_path
        self.fmt = fmt
        self.sections = list(sections)
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        data = {}
        total = max(1, len(self.sections))
        for i, (name, cmd) in enumerate(self.sections):
            if self._cancelled:
                return
            self.line.emit("Collecting: " + name)
            output = run_cmd(cmd)
            data[name] = output
            self.progress.emit(int((i + 1) / total * 100))

        if self._cancelled:
            return
        if not self.output_path:
            preview = []
            for k, v in data.items():
                preview.append(f"=== {k} ===\n{v}\n")
            self.finished.emit(True, "\n".join(preview))
            return

        try:
            if self.fmt == "JSON":
                with open(self.output_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            elif self.fmt == "CSV":
                with open(self.output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Section", "Data"])
                    for k, v in data.items():
                        writer.writerow([k, v])
            elif self.fmt == "HTML":
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Vice OS System Report</title>")
                    f.write(
                        "<style>body{font-family:monospace;background:#0D0E15;color:#F5F6FA;padding:24px}"
                        "h1{color:#FF5E7E}.section{border:1px solid #262A3D;border-radius:8px;"
                        "background:#141621;margin:16px 0;padding:12px}h2{color:#36D6C3;margin-top:0}"
                        "pre{background:#10121B;padding:10px;overflow:auto;border-radius:6px}</style>"
                    )
                    f.write("</head><body>")
                    f.write("<h1>Vice OS System Report</h1>")
                    f.write("<p>Generated: " + html.escape(datetime.datetime.now().isoformat()) + "</p>")
                    for k, v in data.items():
                        f.write(
                            f'<div class="section"><h2>{html.escape(k)}</h2>'
                            f'<pre>{html.escape(v)}</pre></div>'
                        )
                    f.write("</body></html>")
            self.finished.emit(True, "Export complete: " + self.output_path)
        except Exception as e:
            self.finished.emit(False, "Export failed: " + str(e))


class SystemInfoExporter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — System Info Exporter")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 560)
        vt.apply_app_theme(self)
        self._worker = None
        self._preview_mode = False
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "System Info Exporter",
            "Collect system inventory and export reports in JSON, CSV or HTML",
            icon_name="document-save",
            badge_text="EXPORT",
            badge_variant="gold",
            parent=self,
        ))

        fmt_box = QGroupBox("Export Format")
        fl = QHBoxLayout(fmt_box)
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["JSON", "CSV", "HTML"])
        fl.addWidget(QLabel("Format:"))
        fl.addWidget(self._fmt_combo)
        fl.addStretch()
        root.addWidget(fmt_box)

        sec_box = QGroupBox("Sections to Export")
        grid = QGridLayout(sec_box)
        self._checks = {}
        for idx, (name, _) in enumerate(SECTIONS):
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._checks[name] = cb
            row, col = divmod(idx, 4)
            grid.addWidget(cb, row, col)
        root.addWidget(sec_box)

        sel_row = QHBoxLayout()
        all_btn = vt.make_button("Select All", "secondary", parent=self)
        all_btn.clicked.connect(lambda: [c.setChecked(True) for c in self._checks.values()])
        sel_row.addWidget(all_btn)
        none_btn = vt.make_button("Select None", "secondary", parent=self)
        none_btn.clicked.connect(lambda: [c.setChecked(False) for c in self._checks.values()])
        sel_row.addWidget(none_btn)
        sel_row.addStretch()
        root.addLayout(sel_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._export_btn = vt.make_button("Export", "primary", parent=self)
        self._export_btn.clicked.connect(self._export)
        btn_row.addWidget(self._export_btn)

        btn_row.addStretch()

        self._preview_btn = vt.make_button("Preview", "secondary", parent=self)
        self._preview_btn.clicked.connect(self._preview)
        btn_row.addWidget(self._preview_btn)
        root.addLayout(btn_row)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log, 1)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _start_worker(self, path, fmt, selected, preview=False):
        if self._worker is not None and self._worker.isRunning():
            return
        self._preview_mode = preview
        self._export_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._log.clear()

        self._worker = ExportWorker(path, fmt, selected, parent=self)
        self._worker.progress.connect(self._progress.setValue)
        if not preview:
            self._worker.line.connect(self._log.append)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _export(self):
        selected = [s for s in SECTIONS if self._checks[s[0]].isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Sections", "Select at least one section.")
            return

        fmt = self._fmt_combo.currentText()
        ext = fmt.lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", os.path.expanduser("~/vice_system_report." + ext),
            f"{fmt} (*.{ext});;All files (*)",
        )
        if not path:
            return
        self._start_worker(path, fmt, selected, preview=False)

    def _preview(self):
        selected = [s for s in SECTIONS if self._checks[s[0]].isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Sections", "Select at least one section.")
            return
        self._status.setText("Collecting preview...")
        self._start_worker("", "TEXT", selected, preview=True)

    def _on_done(self, ok, msg):
        self._export_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)
        self._progress.setVisible(False)
        if self._preview_mode:
            self._log.setPlainText(msg)
            self._status.setText("Preview ready")
            return
        self._log.append(msg)
        self._status.setText(msg)
        if ok:
            log_info(msg)
            QMessageBox.information(self, "Export Complete", msg)
        else:
            log_error(msg)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = SystemInfoExporter()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
