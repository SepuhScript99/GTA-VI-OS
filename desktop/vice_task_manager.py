#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Task Manager
Process explorer with CPU/memory usage bars, process filtering, priority renice, and signal termination.
"""

import os
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660
REFRESH_MS = 2000


def _read_proc_cpu():
    try:
        with open("/proc/stat", encoding="utf-8") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return sum(parts), idle
    except OSError:
        return 0, 0


def _read_mem_pct():
    info = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    vals = v.split()
                    if vals:
                        info[k.strip()] = int(vals[0])
        total = info.get("MemTotal", 0)
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        if total > 0:
            return int((total - avail) * 100 / total)
    except (OSError, ValueError):
        pass
    return 0


def get_processes(search=""):
    procs = []
    try:
        out = subprocess.check_output(
            ["ps", "aux", "--sort=-%cpu"],
            text=True, timeout=5,
        ).splitlines()[1:]
        low_search = search.lower()
        for line in out:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            user, pid, cpu, mem, _vsz, rss, _tty, stat, _start, _time, cmd = parts
            if low_search and low_search not in cmd.lower() and low_search not in user.lower():
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

    def __init__(self, search="", parent=None):
        super().__init__(parent)
        self.search = search
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        procs = get_processes(self.search)
        if not self._cancelled:
            self.data_ready.emit(procs)


class TaskManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Task Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        vt.apply_app_theme(self)
        self._worker = None
        self._paused = False
        self._prev_cpu = _read_proc_cpu()
        self._init_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Task Manager",
            "Live process explorer with CPU/memory meters, signals and priority renice",
            icon_name="utilities-system-monitor",
            badge_text="PROCS",
            badge_variant="coral",
            parent=self,
        ))

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
        self._proc_count.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        summary.addWidget(self._proc_count)
        root.addLayout(summary)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name or user...")
        self._search.textChanged.connect(self._refresh)
        search_row.addWidget(self._search)

        self._pause_btn = vt.make_button("Pause", "secondary", parent=self)
        self._pause_btn.setCheckable(True)
        self._pause_btn.toggled.connect(self._toggle_pause)
        search_row.addWidget(self._pause_btn)
        root.addLayout(search_row)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(["PID", "User", "CPU%", "MEM%", "RSS(kB)", "Stat", "Command"])
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        for col in range(6):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        root.addWidget(self._table)

        act_row = QHBoxLayout()

        kill_btn = vt.make_button("Kill (SIGKILL)", "danger", parent=self)
        kill_btn.clicked.connect(lambda: self._signal_selected("KILL"))
        act_row.addWidget(kill_btn)

        term_btn = vt.make_button("Terminate (SIGTERM)", "secondary", parent=self)
        term_btn.clicked.connect(lambda: self._signal_selected("TERM"))
        act_row.addWidget(term_btn)

        stop_btn = vt.make_button("Stop (SIGSTOP)", "secondary", parent=self)
        stop_btn.clicked.connect(lambda: self._signal_selected("STOP"))
        act_row.addWidget(stop_btn)

        cont_btn = vt.make_button("Continue (SIGCONT)", "secondary", parent=self)
        cont_btn.clicked.connect(lambda: self._signal_selected("CONT"))
        act_row.addWidget(cont_btn)

        act_row.addStretch()

        act_row.addWidget(QLabel("Nice:"))
        self._nice_spin = QSpinBox()
        self._nice_spin.setRange(-20, 19)
        self._nice_spin.setValue(0)
        act_row.addWidget(self._nice_spin)

        renice_btn = vt.make_button("Renice", "primary", parent=self)
        renice_btn.clicked.connect(self._renice_selected)
        act_row.addWidget(renice_btn)
        root.addLayout(act_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
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
        if self._worker is not None and self._worker.isRunning():
            return
        search = self._search.text().strip()
        w = ProcWorker(search, parent=self)
        w.data_ready.connect(self._populate)
        self._worker = w
        w.start()

    def _update_summary(self):
        total, idle = _read_proc_cpu()
        prev_total, prev_idle = self._prev_cpu
        diff_total = total - prev_total
        diff_idle = idle - prev_idle
        if diff_total > 0:
            cpu_pct = max(0, min(100, int((1.0 - diff_idle / diff_total) * 100)))
            self._cpu_bar.setValue(cpu_pct)
        self._prev_cpu = (total, idle)
        self._mem_bar.setValue(_read_mem_pct())

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

        restore_row = -1
        for p in procs:
            row = self._table.rowCount()
            self._table.insertRow(row)
            vals = (p["pid"], p["user"], p["cpu"], p["mem"], p["rss"], p["stat"], p["cmd"])
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                try:
                    cpu = float(p["cpu"])
                    if cpu > 50:
                        item.setForeground(QBrush(QColor(vt.COLORS["danger"])))
                    elif cpu > 20:
                        item.setForeground(QBrush(QColor(vt.COLORS["warning"])))
                except ValueError:
                    pass
                if p["stat"].startswith("Z"):
                    item.setForeground(QBrush(QColor(vt.COLORS["text_muted"])))
                self._table.setItem(row, col, item)
            if p["pid"] == selected_pid:
                restore_row = row

        self._table.setSortingEnabled(True)
        if restore_row >= 0:
            self._table.selectRow(restore_row)
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
                self, "Kill Process", f"Force kill PID {pid} ({cmd})?",
                QMessageBox.Yes | QMessageBox.No,
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
        is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
        cmd = ["renice", "-n", str(nice), "-p", pid]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode != 0 and not is_root:
                r = subprocess.run(["pkexec"] + cmd, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                self._status.setText(f"Reniced PID {pid} to {nice}")
                log_info(f"renice {nice} PID {pid}")
            else:
                raise RuntimeError((r.stderr or r.stdout or "renice failed").strip())
        except Exception as e:
            self._status.setText(f"Renice failed: {e}")
            log_error(f"Renice failed: {e}")

    def closeEvent(self, event):
        self._timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = TaskManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
