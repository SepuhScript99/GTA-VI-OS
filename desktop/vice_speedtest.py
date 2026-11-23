#!/usr/bin/env python3
"""Vice OS — Network Speed Test. speedtest-cli / iperf3 frontend with history."""

import datetime
import json
import os
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/speedtest_history.json")
MAX_HISTORY = 100


class SpeedtestWorker(QThread):
    """Runs speedtest-cli and parses the result."""

    line = pyqtSignal(str)
    finished = pyqtSignal(bool, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        try:
            self._proc = subprocess.Popen(
                ["speedtest-cli", "--simple"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            lines = []
            if self._proc.stdout:
                for line in self._proc.stdout:
                    if self._cancelled:
                        break
                    text = line.rstrip()
                    lines.append(text)
                    self.line.emit(text)
            rc = self._proc.wait()
        except FileNotFoundError:
            if not self._cancelled:
                self.line.emit("speedtest-cli not found. Install: apt install speedtest-cli")
                self.finished.emit(False, {})
            return
        except Exception as e:
            if not self._cancelled:
                self.line.emit(f"Error: {e}")
                self.finished.emit(False, {})
            return

        if self._cancelled:
            return
        if rc != 0:
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

    def __init__(self, server, port, seconds, reverse, parent=None):
        super().__init__(parent)
        self._server = server
        self._port = port
        self._seconds = seconds
        self._reverse = reverse
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        cmd = ["iperf3", "-c", self._server, "-p", str(self._port), "-t", str(self._seconds)]
        if self._reverse:
            cmd.append("-R")
        self.line.emit("$ " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            if self._proc.stdout:
                for line in self._proc.stdout:
                    if self._cancelled:
                        break
                    self.line.emit(line.rstrip())
            rc = self._proc.wait()
            if not self._cancelled:
                self.finished.emit(rc == 0, "")
        except FileNotFoundError:
            if not self._cancelled:
                self.line.emit("iperf3 not found. Install: apt install iperf3")
                self.finished.emit(False, "")
        except Exception as e:
            if not self._cancelled:
                self.line.emit(f"Error: {e}")
                self.finished.emit(False, "")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def save_history(entries):
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(entries[-MAX_HISTORY:], f, indent=2)
    except Exception as e:
        log_error(f"Speedtest history save failed: {e}")


class SpeedTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Network Speed Test")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 480)
        vt.apply_app_theme(self)
        self._worker = None
        self._init_ui()
        self._load_history_table()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Network Speed Test",
            "Measure WAN throughput (speedtest-cli), LAN bandwidth (iperf3) & history",
            icon_name="network-workgroup",
            badge_text="BANDWIDTH",
            badge_variant="aqua",
            parent=self,
        ))

        res_row = QHBoxLayout()
        self._dl_label = QLabel("DL: --")
        self._dl_label.setFont(QFont("monospace", 24, QFont.Bold))
        self._dl_label.setStyleSheet(f"color: {vt.COLORS['accent_aqua']}; border: none;")
        self._dl_label.setAlignment(Qt.AlignCenter)
        res_row.addWidget(self._dl_label)

        self._up_label = QLabel("UL: --")
        self._up_label.setFont(QFont("monospace", 24, QFont.Bold))
        self._up_label.setStyleSheet(f"color: {vt.COLORS['accent_coral']}; border: none;")
        self._up_label.setAlignment(Qt.AlignCenter)
        res_row.addWidget(self._up_label)

        self._ping_label = QLabel("Ping: --")
        self._ping_label.setFont(QFont("monospace", 15))
        self._ping_label.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; border: none;")
        self._ping_label.setAlignment(Qt.AlignCenter)
        res_row.addWidget(self._ping_label)
        root.addLayout(res_row)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        net_tab = QWidget()
        nl = QVBoxLayout(net_tab)
        self._run_btn = vt.make_button("Run Speed Test", "primary", parent=net_tab)
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

        lan_tab = QWidget()
        ll = QVBoxLayout(lan_tab)
        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Server:"))
        self._iperf_host = QLineEdit()
        self._iperf_host.setPlaceholderText("192.168.1.10 (run 'iperf3 -s' there)")
        form_row.addWidget(self._iperf_host, 1)
        form_row.addWidget(QLabel("Port:"))
        self._iperf_port = QLineEdit("5201")
        self._iperf_port.setFixedWidth(70)
        form_row.addWidget(self._iperf_port)
        form_row.addWidget(QLabel("Seconds:"))
        self._iperf_time = QLineEdit("10")
        self._iperf_time.setFixedWidth(50)
        form_row.addWidget(self._iperf_time)
        self._iperf_reverse_btn = QPushButton("Reverse (download)")
        self._iperf_reverse_btn.setCheckable(True)
        form_row.addWidget(self._iperf_reverse_btn)
        self._iperf_run_btn = vt.make_button("Run iperf3", "primary", parent=lan_tab)
        self._iperf_run_btn.clicked.connect(self._run_iperf)
        form_row.addWidget(self._iperf_run_btn)
        ll.addLayout(form_row)

        self._iperf_log = QTextEdit()
        self._iperf_log.setReadOnly(True)
        ll.addWidget(self._iperf_log)
        tabs.addTab(lan_tab, "LAN (iperf3)")

        hist_tab = QWidget()
        hl = QVBoxLayout(hist_tab)
        self._hist_table = QTableWidget()
        self._hist_table.setColumnCount(5)
        self._hist_table.setHorizontalHeaderLabels(["Time", "Ping", "Download", "Upload", "Type"])
        self._hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            self._hist_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hl.addWidget(self._hist_table)
        clear_row = QHBoxLayout()
        clear_btn = vt.make_button("Clear History", "danger", parent=hist_tab)
        clear_btn.clicked.connect(self._clear_history)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch()
        hl.addLayout(clear_row)
        tabs.addTab(hist_tab, "History")

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _run_speedtest(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._net_log.clear()
        self._status.setText("Running speedtest...")
        self._dl_label.setText("DL: ...")
        self._up_label.setText("UL: ...")
        self._ping_label.setText("Ping: ...")
        self._worker = SpeedtestWorker(parent=self)
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
        self._dl_label.setText(f"DL: {dl}")
        self._up_label.setText(f"UL: {ul}")
        self._ping_label.setText(f"Ping: {ping}")
        self._status.setText("Speedtest complete")

        history = load_history()
        history.append({
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "ping": ping, "download": dl, "upload": ul, "type": "internet",
        })
        save_history(history)
        self._load_history_table()
        log_info(f"Speedtest: DL={dl} UL={ul} {ping}")

    def _run_iperf(self):
        if self._worker is not None and self._worker.isRunning():
            return
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
        self._worker = IperfWorker(server, port, seconds, self._iperf_reverse_btn.isChecked(), parent=self)
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
                "ping": "", "download": "", "upload": "", "type": f"lan:{self._iperf_host.text().strip()}",
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
            dl_item.setForeground(QBrush(QColor(vt.COLORS["accent_aqua"])))
            self._hist_table.setItem(row, 2, dl_item)
            ul_item = QTableWidgetItem(entry.get("upload", ""))
            ul_item.setForeground(QBrush(QColor(vt.COLORS["accent_coral"])))
            self._hist_table.setItem(row, 3, ul_item)
            self._hist_table.setItem(row, 4, QTableWidgetItem(entry.get("type", "")))

    def _clear_history(self):
        if QMessageBox.question(
            self, "Clear", "Delete all speedtest history?", QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        save_history([])
        self._load_history_table()

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = SpeedTest()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
