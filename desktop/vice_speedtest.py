#!/usr/bin/env python3
"""Vice OS — Network Speed Test. speedtest-cli / iperf3 frontend with history."""

import sys
import os
import json
import subprocess
import datetime
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QComboBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QMessageBox, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px 16px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QLabel { color: #00ffff; }
"""

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/speedtest_history.json")
MAX_HISTORY = 100


class SpeedtestWorker(QThread):
    """Runs speedtest-cli and parses the result."""
    line = pyqtSignal(str)
    finished = pyqtSignal(bool, dict)

    def run(self):
        try:
            proc = subprocess.Popen(
                ["speedtest-cli", "--simple"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            lines = []
            for line in proc.stdout:
                lines.append(line.rstrip())
                self.line.emit(line.rstrip())
            proc.wait()
        except FileNotFoundError:
            self.line.emit("speedtest-cli not found. Install: apt install speedtest-cli")
            self.finished.emit(False, {})
            return
        except Exception as e:
            self.line.emit(f"Error: {e}")
            self.finished.emit(False, {})
            return

        if proc.returncode != 0:
            self.finished.emit(False, {})
            return

        result = {"ping": "", "download": "", "upload": ""}
        for line in lines:
            if line.startswith("Ping:"):
                result["ping"] = line.split(":", 1)[1].strip()
            elif line.startswith("Download:"):
                result["download"] = line.split(":", 1)[1].strip()
            elif line.startswith("Upload:"):
                result["upload"] = line.split(":", 1)[1].strip()
        self.finished.emit(bool(result["download"] or result["upload"]), result)


class IperfWorker(QThread):
    """Runs an iperf3 client test against a server."""
    line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, server, port, seconds, reverse):
        super().__init__()
        self._server = server
        self._port = port
        self._seconds = seconds
        self._reverse = reverse

    def run(self):
        cmd = ["iperf3", "-c", self._server, "-p", str(self._port),
               "-t", str(self._seconds)]
        if self._reverse:
            cmd.append("-R")
        self.line.emit("$ " + " ".join(cmd))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                self.line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode == 0, "")
        except FileNotFoundError:
            self.line.emit("iperf3 not found. Install: apt install iperf3")
            self.finished.emit(False, "")
        except Exception as e:
            self.line.emit(f"Error: {e}")
            self.finished.emit(False, "")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(entries):
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump(entries[-MAX_HISTORY:], f, indent=2)
    except Exception as e:
        log_error(f"Speedtest history save failed: {e}")


class SpeedTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Network Speed Test")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()
        self._load_history_table()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Network Speed Test")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Big result display
        res_row = QHBoxLayout()
        self._dl_label = QLabel("↓ --")
        self._dl_label.setFont(QFont("monospace", 28, QFont.Bold))
        self._dl_label.setStyleSheet("color: #00ffff; border: none;")
        self._dl_label.setAlignment(Qt.AlignCenter)
        res_row.addWidget(self._dl_label)

        self._up_label = QLabel("↑ --")
        self._up_label.setFont(QFont("monospace", 28, QFont.Bold))
        self._up_label.setStyleSheet("color: #ff00ff; border: none;")
        self._up_label.setAlignment(Qt.AlignCenter)
        res_row.addWidget(self._up_label)

        self._ping_label = QLabel("ping --")
        self._ping_label.setFont(QFont("monospace", 16))
        self._ping_label.setStyleSheet("color: #888; border: none;")
        self._ping_label.setAlignment(Qt.AlignCenter)
        res_row.addWidget(self._ping_label)
        root.addLayout(res_row)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # --- Internet tab ---
        net_tab = QWidget()
        nl = QVBoxLayout(net_tab)
        self._run_btn = QPushButton("▶ Run Speed Test")
        self._run_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        self._run_btn.clicked.connect(self._run_speedtest)
        nl.addWidget(self._run_btn)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        nl.addWidget(self._progress)
        self._net_log = QTextEdit()
        self._net_log.setReadOnly(True)
        nl.addWidget(self._net_log)
        tabs.addTab(net_tab, "Internet (speedtest)")

        # --- LAN tab ---
        lan_tab = QWidget()
        ll = QVBoxLayout(lan_tab)
        form_row = QHBoxLayout()
        ll.addWidget(QLabel("Server:"))
        self._iperf_host = QLineEdit()
        self._iperf_host.setPlaceholderText("192.168.1.10 (run 'iperf3 -s' there)")
        form_row.addWidget(self._iperf_host)
        ll.addWidget(QLabel("Port:"))
        self._iperf_port = QLineEdit("5201")
        self._iperf_port.setFixedWidth(70)
        form_row.addWidget(self._iperf_port)
        ll.addWidget(QLabel("Seconds:"))
        self._iperf_time = QLineEdit("10")
        self._iperf_time.setFixedWidth(50)
        form_row.addWidget(self._iperf_time)
        self._iperf_reverse_btn = QPushButton("Reverse (download)")
        self._iperf_reverse_btn.setCheckable(True)
        form_row.addWidget(self._iperf_reverse_btn)
        self._iperf_run_btn = QPushButton("▶ Run iperf3")
        self._iperf_run_btn.clicked.connect(self._run_iperf)
        form_row.addWidget(self._iperf_run_btn)
        form_row.addStretch()
        ll.addLayout(form_row)
        self._iperf_log = QTextEdit()
        self._iperf_log.setReadOnly(True)
        ll.addWidget(self._iperf_log)
        tabs.addTab(lan_tab, "LAN (iperf3)")

        # --- History tab ---
        hist_tab = QWidget()
        hl = QVBoxLayout(hist_tab)
        self._hist_table = QTableWidget()
        self._hist_table.setColumnCount(5)
        self._hist_table.setHorizontalHeaderLabels(["Time", "Ping", "Download", "Upload", "Type"])
        self._hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in [1, 2, 3, 4]:
            self._hist_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hl.addWidget(self._hist_table)
        clear_row = QHBoxLayout()
        clear_btn = QPushButton("Clear History")
        clear_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        clear_btn.clicked.connect(self._clear_history)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch()
        hl.addLayout(clear_row)
        tabs.addTab(hist_tab, "History")

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _run_speedtest(self):
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._net_log.clear()
        self._status.setText("Running speedtest...")
        self._dl_label.setText("↓ ...")
        self._up_label.setText("↑ ...")
        self._ping_label.setText("ping ...")
        self._worker = SpeedtestWorker()
        self._worker.line.connect(self._net_log.append)
        self._worker.finished.connect(self._speedtest_done)
        self._worker.start()

    def _speedtest_done(self, ok, result):
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        if not ok:
            self._status.setText("Speedtest failed — check log")
            return
        dl = result.get("download", "--")
        ul = result.get("upload", "--")
        ping = result.get("ping", "--")
        self._dl_label.setText(f"↓ {dl}")
        self._up_label.setText(f"↑ {ul}")
        self._ping_label.setText(f"ping {ping}")
        self._status.setText("Speedtest complete")

        history = load_history()
        history.append({
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "ping": ping, "download": dl, "upload": ul, "type": "internet",
        })
        save_history(history)
        self._load_history_table()
        log_info(f"Speedtest: ↓{dl} ↑{ul} {ping}")

    def _run_iperf(self):
        server = self._iperf_host.text().strip()
        if not server:
            QMessageBox.warning(self, "Missing Server", "Enter an iperf3 server address.")
            return
        try:
            port = int(self._iperf_port.text())
            seconds = int(self._iperf_time.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Port and seconds must be integers.")
            return
        self._iperf_run_btn.setEnabled(False)
        self._iperf_log.clear()
        self._status.setText(f"Running iperf3 against {server}...")
        self._worker = IperfWorker(server, port, seconds, self._iperf_reverse_btn.isChecked())
        self._worker.line.connect(self._iperf_log.append)
        self._worker.finished.connect(self._iperf_done)
        self._worker.start()

    def _iperf_done(self, ok, _bw):
        self._iperf_run_btn.setEnabled(True)
        self._status.setText("iperf3 complete" if ok else "iperf3 failed — check log")
        if ok:
            history = load_history()
            history.append({
                "time": datetime.datetime.now().isoformat(timespec="seconds"),
                "ping": "", "download": "", "upload": "", "type": f"lan:{self._iperf_host.text()}",
            })
            save_history(history)
            self._load_history_table()

    def _load_history_table(self):
        self._hist_table.setRowCount(0)
        for entry in reversed(load_history()):
            row = self._hist_table.rowCount()
            self._hist_table.insertRow(row)
            self._hist_table.setItem(row, 0, QTableWidgetItem(entry.get("time", "")))
            self._hist_table.setItem(row, 1, QTableWidgetItem(entry.get("ping", "")))
            dl_item = QTableWidgetItem(entry.get("download", ""))
            dl_item.setForeground(QBrush(QColor("#00ffff")))
            self._hist_table.setItem(row, 2, dl_item)
            ul_item = QTableWidgetItem(entry.get("upload", ""))
            ul_item.setForeground(QBrush(QColor("#ff00ff")))
            self._hist_table.setItem(row, 3, ul_item)
            self._hist_table.setItem(row, 4, QTableWidgetItem(entry.get("type", "")))

    def _clear_history(self):
        if QMessageBox.question(self, "Clear", "Delete all speedtest history?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        save_history([])
        self._load_history_table()


def main():
    app = QApplication(sys.argv)
    win = SpeedTest()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()