#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) System Monitor
Real-time graphical monitoring of CPU, RAM, swap, network throughput, and disk I/O.
"""

import sys
import os
import subprocess
import collections

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGroupBox, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QPainter, QPen, QPolygon
from PyQt5.QtCore import QPoint

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
REFRESH_MS = 1500
HISTORY = 60  # data points to keep

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #fff; font-size: 10px; }
QProgressBar::chunk { background: #00ffff; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLabel { color: #00ffff; }
"""


def read_cpu():
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        vals = list(map(int, line.split()[1:]))
        idle = vals[3]
        total = sum(vals)
        return total, idle
    except Exception:
        return 0, 0


def read_net():
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]
        rx = tx = 0
        for line in lines:
            parts = line.split()
            if parts[0].startswith("lo"):
                continue
            rx += int(parts[1])
            tx += int(parts[9])
        return rx, tx
    except Exception:
        return 0, 0


def read_mem():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.split()[0])
    except Exception:
        pass
    total = info.get("MemTotal", 1)
    free = info.get("MemAvailable", 0)
    used = total - free
    return used, total


def read_disk_io():
    try:
        with open("/proc/diskstats") as f:
            lines = f.readlines()
        r = w = 0
        for line in lines:
            parts = line.split()
            if len(parts) >= 14 and parts[2].startswith(("sd", "nvme", "vd", "hd")):
                r += int(parts[5])
                w += int(parts[9])
        return r, w
    except Exception:
        return 0, 0


class GraphWidget(QWidget):
    def __init__(self, color="#00ffff", label="", unit="%", max_val=100):
        super().__init__()
        self._color = QColor(color)
        self._label = label
        self._unit = unit
        self._max_val = max_val
        self._data = collections.deque([0] * HISTORY, maxlen=HISTORY)
        self.setMinimumHeight(80)
        self.setMinimumWidth(200)

    def push(self, value):
        self._data.append(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#0d0d0d"))
        painter.setPen(QPen(QColor("#1a1a1a"), 1))
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(0, y, w, y)

        # Draw graph
        pen = QPen(self._color, 2)
        painter.setPen(pen)
        data = list(self._data)
        n = len(data)
        max_v = max(self._max_val, max(data) or 1)
        points = []
        for i, v in enumerate(data):
            x = int(i * w / (n - 1)) if n > 1 else w // 2
            y = int(h - (v / max_v) * (h - 4)) - 2
            points.append(QPoint(x, y))
        if len(points) >= 2:
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])

        # Fill under
        fill_color = QColor(self._color)
        fill_color.setAlpha(30)
        painter.setBrush(fill_color)
        painter.setPen(Qt.NoPen)
        poly_pts = [QPoint(0, h)] + points + [QPoint(w, h)]
        painter.drawPolygon(QPolygon(poly_pts))

        # Label + current value
        painter.setPen(self._color)
        cur = data[-1] if data else 0
        painter.drawText(4, 14, f"{self._label}: {cur:.1f}{self._unit}")


class SystemMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — System Monitor")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._prev_cpu = (0, 0)
        self._prev_net = (0, 0)
        self._prev_disk = (0, 0)
        self._init_ui()
        self._timer = QTimer()
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — System Monitor")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 4px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Overview tab ---
        overview = QWidget()
        ol = QVBoxLayout(overview)

        bars_row = QHBoxLayout()

        cpu_box = QGroupBox("CPU")
        cl = QVBoxLayout(cpu_box)
        self._cpu_graph = GraphWidget("#00ffff", "CPU", "%", 100)
        cl.addWidget(self._cpu_graph)
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setFormat("%p%")
        cl.addWidget(self._cpu_bar)
        self._cpu_label = QLabel("0%")
        self._cpu_label.setAlignment(Qt.AlignCenter)
        cl.addWidget(self._cpu_label)
        bars_row.addWidget(cpu_box)

        mem_box = QGroupBox("Memory")
        ml = QVBoxLayout(mem_box)
        self._mem_graph = GraphWidget("#ff00ff", "MEM", "%", 100)
        ml.addWidget(self._mem_graph)
        self._mem_bar = QProgressBar()
        self._mem_bar.setStyleSheet("QProgressBar::chunk { background: #ff00ff; }")
        self._mem_bar.setFormat("%p%")
        ml.addWidget(self._mem_bar)
        self._mem_label = QLabel("0 / 0 MB")
        self._mem_label.setAlignment(Qt.AlignCenter)
        ml.addWidget(self._mem_label)
        bars_row.addWidget(mem_box)

        net_box = QGroupBox("Network")
        nl = QVBoxLayout(net_box)
        self._net_graph = GraphWidget("#00ff88", "NET", " KB/s", 1000)
        nl.addWidget(self._net_graph)
        self._net_label = QLabel("↓ 0 KB/s  ↑ 0 KB/s")
        self._net_label.setAlignment(Qt.AlignCenter)
        self._net_label.setStyleSheet("color: #00ff88;")
        nl.addWidget(self._net_label)
        bars_row.addWidget(net_box)

        disk_box = QGroupBox("Disk I/O")
        dl = QVBoxLayout(disk_box)
        self._disk_graph = GraphWidget("#ffaa00", "DISK", " KB/s", 1000)
        dl.addWidget(self._disk_graph)
        self._disk_label = QLabel("R: 0  W: 0 KB/s")
        self._disk_label.setAlignment(Qt.AlignCenter)
        self._disk_label.setStyleSheet("color: #ffaa00;")
        dl.addWidget(self._disk_label)
        bars_row.addWidget(disk_box)

        ol.addLayout(bars_row)

        # Temperature
        temp_box = QGroupBox("Temperatures")
        tl = QHBoxLayout(temp_box)
        self._temp_label = QLabel("Loading...")
        self._temp_label.setAlignment(Qt.AlignCenter)
        tl.addWidget(self._temp_label)
        ol.addWidget(temp_box)

        tabs.addTab(overview, "Overview")

        # --- Processes tab ---
        proc_tab = QWidget()
        pl = QVBoxLayout(proc_tab)
        self._proc_table = QTableWidget()
        self._proc_table.setColumnCount(6)
        self._proc_table.setHorizontalHeaderLabels(["PID", "User", "CPU%", "MEM%", "RSS", "Command"])
        self._proc_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for i in range(5):
            self._proc_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._proc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._proc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        pl.addWidget(self._proc_table)
        tabs.addTab(proc_tab, "Processes")

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        # CPU
        total, idle = read_cpu()
        prev_total, prev_idle = self._prev_cpu
        diff_total = total - prev_total
        diff_idle = idle - prev_idle
        cpu_pct = 0.0 if diff_total == 0 else (1 - diff_idle / diff_total) * 100
        self._prev_cpu = (total, idle)
        self._cpu_graph.push(cpu_pct)
        self._cpu_bar.setValue(int(cpu_pct))
        self._cpu_label.setText(f"{cpu_pct:.1f}%")

        # Memory
        used, total_mem = read_mem()
        mem_pct = (used / total_mem * 100) if total_mem else 0
        self._mem_graph.push(mem_pct)
        self._mem_bar.setValue(int(mem_pct))
        self._mem_label.setText(f"{used // 1024} / {total_mem // 1024} MB")

        # Network
        rx, tx = read_net()
        prev_rx, prev_tx = self._prev_net
        d_rx = max(0, (rx - prev_rx)) * 1000 // (REFRESH_MS * 1024)
        d_tx = max(0, (tx - prev_tx)) * 1000 // (REFRESH_MS * 1024)
        self._prev_net = (rx, tx)
        self._net_graph.push(d_rx + d_tx)
        self._net_label.setText(f"↓ {d_rx} KB/s  ↑ {d_tx} KB/s")

        # Disk
        dr, dw = read_disk_io()
        prev_dr, prev_dw = self._prev_disk
        d_dr = max(0, (dr - prev_dr)) * 1000 // (REFRESH_MS * 2)
        d_dw = max(0, (dw - prev_dw)) * 1000 // (REFRESH_MS * 2)
        self._prev_disk = (dr, dw)
        self._disk_graph.push(d_dr + d_dw)
        self._disk_label.setText(f"R: {d_dr}  W: {d_dw} KB/s")

        # Temperature
        temps = []
        for i in range(8):
            p = f"/sys/class/thermal/thermal_zone{i}/temp"
            if os.path.exists(p):
                try:
                    t = int(open(p).read().strip()) / 1000
                    temps.append(f"Zone{i}: {t:.0f}°C")
                except Exception:
                    pass
        self._temp_label.setText("  |  ".join(temps) if temps else "N/A")

        # Processes
        self._refresh_procs()

    def _refresh_procs(self):
        try:
            out = subprocess.check_output(
                ["ps", "aux", "--sort=-%cpu"],
                text=True, timeout=3
            ).splitlines()[1:26]
        except Exception:
            return

        self._proc_table.setRowCount(0)
        for line in out:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            user, pid, cpu, mem, vsz, rss = parts[:6]
            cmd = parts[10][:60]
            row = self._proc_table.rowCount()
            self._proc_table.insertRow(row)
            for col, val in enumerate([pid, user, cpu, mem, rss, cmd]):
                item = QTableWidgetItem(val)
                try:
                    if float(cpu) > 20:
                        item.setForeground(QBrush(QColor("#ff4444")))
                except Exception:
                    pass
                self._proc_table.setItem(row, col, item)

        self._status.setText(f"Updated  |  CPU: {self._cpu_bar.value()}%  MEM: {self._mem_bar.value()}%")


def main():
    app = QApplication(sys.argv)
    win = SystemMonitor()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
