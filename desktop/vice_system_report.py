#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) System Report Generator
Compiles detailed hardware, OS, kernel, package, and environment reports into Markdown/HTML.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QProgressBar, QTabWidget, QGroupBox, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception:
        return "N/A"


class ReportWorker(QThread):
    section_ready = pyqtSignal(str, str)
    finished = pyqtSignal()

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
            output = run_cmd(cmd)
            self.section_ready.emit(title, output)
        self.finished.emit()


class SystemReport(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice System Report")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet("""
            QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
            QGroupBox { border: 1px solid #00ffff; margin-top: 8px; padding: 6px; }
            QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
            QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 12px; }
            QPushButton:hover { background: #00ffff; color: #0a0a0a; }
            QTextEdit { background: #0d0d0d; color: #00ffff; border: 1px solid #333; font-size: 11px; }
            QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; }
            QProgressBar::chunk { background: #00ffff; }
            QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
            QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
            QTabWidget::pane { border: 1px solid #00ffff; }
            QLabel { color: #00ffff; }
            QScrollArea { border: none; }
        """)
        self._sections = {}
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — System Report")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 16, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 8px;")
        root.addWidget(title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

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

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._run_report)
        bottom.addWidget(refresh_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export_report)
        bottom.addWidget(export_btn)

        root.addLayout(bottom)
        self._run_report()

    def _run_report(self):
        self._sections.clear()
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
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_section(self, title, output):
        self._sections[title] = output

        if title == "Processes":
            self._processes_text.setPlainText(output)
            return

        overview_titles = {"OS", "Kernel", "Uptime", "CPU Usage", "Memory", "Temperature"}
        if title in overview_titles:
            self._overview_text.append(f"=== {title} ===\n{output}\n")

        row = len(self._sections) - 1
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        label = QLabel(output)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 11px; color: #aaffff;")
        box_layout.addWidget(label)
        col = row % 2
        r = row // 2
        self._detail_layout.addWidget(box, r, col)

    def _on_finished(self):
        self._progress.setVisible(False)
        log_info("System report generated")

    def _export_report(self):
        import datetime
        path = os.path.expanduser(f"~/vice_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(path, "w") as f:
                for title, content in self._sections.items():
                    f.write(f"=== {title} ===\n{content}\n\n")
            log_info(f"Report exported to {path}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")


def main():
    app = QApplication(sys.argv)
    window = SystemReport()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
