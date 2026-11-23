#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) System Report Generator.
Compiles detailed hardware, OS, kernel, package, and environment reports into Markdown/Text.
"""

import datetime
import os
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QProgressBar, QTabWidget, QGroupBox, QGridLayout, QScrollArea,
    QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal

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

WINDOW_WIDTH = 920
WINDOW_HEIGHT = 660


class ReportWorker(QThread):
    section_ready = pyqtSignal(str, str)
    report_done = pyqtSignal()

    def __init__(self):
        super().__init__()
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

    def _run_cmd(self, cmd):
        if self._stopped:
            return "[cancelled]"
        try:
            self._proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, _ = self._proc.communicate(timeout=5)
            return (stdout or "").strip() or "N/A"
        except subprocess.TimeoutExpired:
            if self._proc is not None:
                self._proc.kill()
                self._proc.communicate()
            return "[timed out]"
        except Exception:
            return "N/A"
        finally:
            self._proc = None

    def run(self):
        sections = [
            ("OS", "cat /etc/os-release 2>/dev/null | grep -E '^(PRETTY_NAME|VERSION)=' | sed 's/=/ /;s/\"//g'"),
            ("Kernel", "uname -r; uname -m"),
            ("Uptime", "uptime -p"),
            ("CPU", "lscpu 2>/dev/null | grep -E '^(Model name|CPU\\(s\\)|CPU max MHz)'"),
            ("CPU Usage", "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4\"%\"}'"),
            ("Memory", "free -h 2>/dev/null"),
            ("Swap", "swapon --show 2>/dev/null || echo 'No swap active'"),
            ("Disk", "df -h 2>/dev/null | grep -v 'tmpfs\\|loop\\|udev'"),
            ("GPU", "lspci 2>/dev/null | grep -i 'vga\\|3d\\|display' || echo 'N/A'"),
            ("Network", "ip -br addr 2>/dev/null"),
            ("Temperature", "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1f°C\\n\", $1/1000}' | head -4 || echo 'N/A'"),
            ("Processes", "ps aux --sort=-%cpu 2>/dev/null | head -6"),
            ("Services", "systemctl list-units --state=failed --no-pager 2>/dev/null | head -10 || echo 'No failed services'"),
        ]
        for title, cmd in sections:
            if self._stopped:
                return
            output = self._run_cmd(cmd)
            if not self._stopped:
                self.section_ready.emit(title, output)
        if not self._stopped:
            self.report_done.emit()


class SystemReport(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice System Report")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(720, 500)
        apply_app_theme(self)
        self._sections = {}
        self._detail_count = 0
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="System Report Generator",
            subtitle="OS, kernel, hardware, temperature, and systemd status overview",
            icon_name="utilities-system-monitor",
            badge_text="SYS REPORT",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._overview_text = QTextEdit()
        self._overview_text.setReadOnly(True)
        self.tabs.addTab(self._overview_text, "Overview")

        self._detail_tab = QScrollArea()
        self._detail_tab.setWidgetResizable(True)
        self._detail_inner = QWidget()
        self._detail_layout = QGridLayout(self._detail_inner)
        self._detail_tab.setWidget(self._detail_inner)
        self.tabs.addTab(self._detail_tab, "Details")

        self._processes_text = QTextEdit()
        self._processes_text.setReadOnly(True)
        self.tabs.addTab(self._processes_text, "Processes")

        bottom = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        bottom.addWidget(self._progress)

        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._run_report)
        bottom.addWidget(refresh_btn)

        export_btn = make_button("Export", variant="primary", parent=self)
        export_btn.clicked.connect(self._export_report)
        bottom.addWidget(export_btn)

        root.addLayout(bottom)
        self._run_report()

    def _run_report(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self._sections.clear()
        self._detail_count = 0
        self._overview_text.clear()
        self._processes_text.clear()
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._progress.setVisible(True)

        self._worker = ReportWorker()
        self._worker.section_ready.connect(self._on_section)
        self._worker.report_done.connect(self._on_finished)
        self._worker.start()

    def _on_section(self, title, output):
        self._sections[title] = output

        if title == "Processes":
            self._processes_text.setPlainText(output)
            return

        overview_titles = {"OS", "Kernel", "Uptime", "CPU Usage", "Memory", "Temperature"}
        if title in overview_titles:
            self._overview_text.append(f"=== {title} ===\n{output}\n")

        idx = self._detail_count
        self._detail_count += 1
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        label = QLabel(output)
        label.setWordWrap(True)
        label.setStyleSheet(f"font-size: 11px; color: {COLORS['text_primary']};")
        box_layout.addWidget(label)
        col = idx % 2
        r = idx // 2
        self._detail_layout.addWidget(box, r, col)

    def _on_finished(self):
        self._progress.setVisible(False)
        log_info("System report generated")

    def _export_report(self):
        path = os.path.expanduser(f"~/vice_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                for title, content in self._sections.items():
                    f.write(f"=== {title} ===\n{content}\n\n")
            log_info(f"Report exported to {path}")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = SystemReport()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
