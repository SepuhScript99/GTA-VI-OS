#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Task Manager
Process explorer with CPU/memory usage bars, process filtering, priority renice, and signal termination.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QSpinBox, QGroupBox, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660
REFRESH_MS = 2000

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #333; margin-top: 8px; padding: 4px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLabel { color: #00ffff; }
"""


def get_processes(search=""):
    procs = []
    try:
        out = subprocess.check_output(
            ["ps", "aux", "--sort=-%cpu"],
            text=True, timeout=5
        ).splitlines()[1:]
        for line in out:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            user, pid, cpu, mem, vsz, rss, tty, stat, start, time_, cmd = parts
            if search and search.lower() not in cmd.lower() and search.lower() not in user.lower():
                continue
            procs.append({
                "user": user, "pid": pid, "cpu": cpu,
                "mem": mem, "rss": rss, "stat": stat,
                "cmd": cmd[:80],
            })
    except Exception:
        pass
    return procs


class ProcWorker(QThread):
    data_ready = pyqtSignal(list)

    def __init__(self, search=""):
        super().__init__()
        self.search = search

    def run(self):
        self.data_ready.emit(get_processes(self.search))


class TaskManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Task Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._paused = False
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Task Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 4px;")
        root.addWidget(title)

        # Summary bars
        summary = QHBoxLayout()
        cpu_box = QGroupBox("CPU")
        cl = QVBoxLayout(cpu_box)
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setRange(0, 100)
        cl.addWidget(self._cpu_bar)
        summary.addWidget(cpu_box)

        mem_box = QGroupBox("Memory")
        ml = QVBoxLayout(mem_box)
        self._mem_bar = QProgressBar()
        self._mem_bar.setRange(0, 100)
        ml.addWidget(self._mem_bar)
        summary.addWidget(mem_box)

        self._proc_count = QLabel("Processes: 0")
        self._proc_count.setStyleSheet("color: #888; font-size: 11px;")
        summary.addWidget(self._proc_count)
        root.addLayout(summary)

        # Search
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name or user...")
        self._search.textChanged.connect(self._refresh)
        search_row.addWidget(self._search)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setCheckable(True)
        self._pause_btn.toggled.connect(self._toggle_pause)
        search_row.addWidget(self._pause_btn)
        root.addLayout(search_row)

        # Process table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(["PID", "User", "CPU%", "MEM%", "RSS(kB)", "Stat", "Command"])
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        root.addWidget(self._table)

        # Actions
        act_row = QHBoxLayout()

        kill_btn = QPushButton("Kill (SIGKILL)")
        kill_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        kill_btn.clicked.connect(lambda: self._signal_selected("KILL"))
        act_row.addWidget(kill_btn)

        term_btn = QPushButton("Terminate (SIGTERM)")
        term_btn.clicked.connect(lambda: self._signal_selected("TERM"))
        act_row.addWidget(term_btn)

        stop_btn = QPushButton("Stop (SIGSTOP)")
        stop_btn.clicked.connect(lambda: self._signal_selected("STOP"))
        act_row.addWidget(stop_btn)

        cont_btn = QPushButton("Continue (SIGCONT)")
        cont_btn.clicked.connect(lambda: self._signal_selected("CONT"))
        act_row.addWidget(cont_btn)

        act_row.addStretch()

        act_row.addWidget(QLabel("Nice:"))
        self._nice_spin = QSpinBox()
        self._nice_spin.setRange(-20, 19)
        self._nice_spin.setValue(0)
        act_row.addWidget(self._nice_spin)

        renice_btn = QPushButton("Renice")
        renice_btn.clicked.connect(self._renice_selected)
        act_row.addWidget(renice_btn)

        root.addLayout(act_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _toggle_pause(self, paused):
        self._paused = paused
        self._pause_btn.setText("Resume" if paused else "Pause")
        if not paused:
            self._refresh()

    def _refresh(self):
        if self._paused:
            return
        self._update_summary()
        search = self._search.text().strip()
        w = ProcWorker(search)
        w.data_ready.connect(self._populate)
        w.start()
        self._worker = w

    def _update_summary(self):
        try:
            cpu_out = subprocess.check_output(
                "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'",
                shell=True, text=True, timeout=3
            ).strip()
            self._cpu_bar.setValue(int(float(cpu_out or 0)))
        except Exception:
            pass

        try:
            mem_out = subprocess.check_output(
                "free | awk '/^Mem:/{printf \"%.0f\", $3/$2*100}'",
                shell=True, text=True, timeout=3
            ).strip()
            self._mem_bar.setValue(int(mem_out or 0))
        except Exception:
            pass

    def _populate(self, procs):
        selected_pid = None
        sel = self._table.selectedItems()
        if sel:
            row = sel[0].row()
            item = self._table.item(row, 0)
            if item:
                selected_pid = item.text()

        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for p in procs:
            row = self._table.rowCount()
            self._table.insertRow(row)
            vals = [p["pid"], p["user"], p["cpu"], p["mem"], p["rss"], p["stat"], p["cmd"]]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                try:
                    cpu = float(p["cpu"])
                    if cpu > 50:
                        item.setForeground(QBrush(QColor("#ff4444")))
                    elif cpu > 20:
                        item.setForeground(QBrush(QColor("#ffaa00")))
                except Exception:
                    pass
                if p["stat"].startswith("Z"):
                    item.setForeground(QBrush(QColor("#888888")))
                self._table.setItem(row, col, item)
                if col == 0 and val == selected_pid:
                    self._table.selectRow(row)

        self._table.setSortingEnabled(True)
        self._proc_count.setText(f"Processes: {len(procs)}")

    def _selected_pid(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a process first.")
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _signal_selected(self, sig):
        pid = self._selected_pid()
        if not pid:
            return
        cmd_item = self._table.item(self._table.currentRow(), 6)
        cmd = cmd_item.text() if cmd_item else pid
        if sig == "KILL":
            if QMessageBox.question(
                self, "Kill Process",
                f"Force kill PID {pid} ({cmd})?",
                QMessageBox.Yes | QMessageBox.No
            ) != QMessageBox.Yes:
                return
        try:
            subprocess.run(["kill", f"-{sig}", pid], check=True)
            self._status.setText(f"Sent SIG{sig} to PID {pid}")
            log_info(f"SIG{sig} -> PID {pid}")
            self._refresh()
        except Exception as e:
            self._status.setText(f"Failed: {e}")
            log_error(f"Signal failed: {e}")

    def _renice_selected(self):
        pid = self._selected_pid()
        if not pid:
            return
        nice = self._nice_spin.value()
        try:
            subprocess.run(["sudo", "renice", str(nice), "-p", pid], check=True)
            self._status.setText(f"Reniced PID {pid} to {nice}")
            log_info(f"renice {nice} PID {pid}")
        except Exception as e:
            self._status.setText(f"Renice failed: {e}")
            log_error(f"Renice failed: {e}")


def main():
    app = QApplication(sys.argv)
    win = TaskManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
