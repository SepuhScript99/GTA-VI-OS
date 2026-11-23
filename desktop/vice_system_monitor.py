#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) System Monitor
Real-time graphical monitoring of CPU, RAM, swap, network throughput, and disk I/O.
"""

import collections
import os
import subprocess
import sys

from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QPolygon
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QProgressBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
REFRESH_MS = 1500
HISTORY = 60


def read_cpu():
    try:
        with open("/proc/stat", encoding="utf-8") as f:
            line = f.readline()
        vals = list(map(int, line.split()[1:]))
        idle = vals[3] + (vals[4] if len(parts := vals) > 4 else 0)
        _ = parts
        total = sum(vals)
        return total, idle
    except Exception:
        return 0, 0


def read_net():
    try:
        with open("/proc/net/dev", encoding="utf-8") as f:
            lines = f.readlines()[2:]
        rx = tx = 0
        for line in lines:
            parts = line.split()
            if not parts or parts[0].startswith("lo"):
                continue
            rx += int(parts[1])
            tx += int(parts[9])
        return rx, tx
    except Exception:
        return 0, 0


def read_mem():
    info = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    vals = v.split()
                    if vals:
                        info[k.strip()] = int(vals[0])
    except Exception:
        pass
    total = info.get("MemTotal", 1)
    free = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - free)
    return used, total


def read_disk_io():
    try:
        with open("/proc/diskstats", encoding="utf-8") as f:
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
    def __init__(self, color="#36D6C3", label="", unit="%", max_val=100):
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

        painter.fillRect(0, 0, w, h, QColor(vt.COLORS["bg_surface"]))
        painter.setPen(QPen(QColor(vt.COLORS["border"]), 1))
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(0, y, w, y)

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
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

        fill_color = QColor(self._color)
        fill_color.setAlpha(35)
        painter.setBrush(fill_color)
        painter.setPen(Qt.NoPen)
        poly_pts = [QPoint(0, h)] + points + [QPoint(w, h)]
        painter.drawPolygon(QPolygon(poly_pts))

        painter.setPen(self._color)
        cur = data[-1] if data else 0
        painter.drawText(6, 15, f"{self._label}: {cur:.1f}{self._unit}")


class SystemMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — System Monitor")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        vt.apply_app_theme(self)
        self._prev_cpu = read_cpu()
        self._prev_net = read_net()
        self._prev_disk = read_disk_io()
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "System Monitor",
            "Live CPU, memory, network throughput, disk I/O and top processes",
            icon_name="utilities-system-monitor",
            badge_text="TELEMETRY",
            badge_variant="aqua",
            parent=self,
        ))

        tabs = QTabWidget()
        root.addWidget(tabs)

        overview = QWidget()
        ol = QVBoxLayout(overview)

        bars_row = QHBoxLayout()

        cpu_box = QGroupBox("CPU")
        cl = QVBoxLayout(cpu_box)
        self._cpu_graph = GraphWidget(vt.COLORS["accent_aqua"], "CPU", "%", 100)
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
        self._mem_graph = GraphWidget(vt.COLORS["accent_coral"], "MEM", "%", 100)
        ml.addWidget(self._mem_graph)
        self._mem_bar = QProgressBar()
        self._mem_bar.setFormat("%p%")
        ml.addWidget(self._mem_bar)
        self._mem_label = QLabel("0 / 0 MB")
        self._mem_label.setAlignment(Qt.AlignCenter)
        ml.addWidget(self._mem_label)
        bars_row.addWidget(mem_box)

        net_box = QGroupBox("Network")
        nl = QVBoxLayout(net_box)
        self._net_graph = GraphWidget(vt.COLORS["success"], "NET", " KB/s", 1000)
        nl.addWidget(self._net_graph)
        self._net_label = QLabel("RX: 0 KB/s  TX: 0 KB/s")
        self._net_label.setAlignment(Qt.AlignCenter)
        self._net_label.setStyleSheet(f"color: {vt.COLORS['success']};")
        nl.addWidget(self._net_label)
        bars_row.addWidget(net_box)

        disk_box = QGroupBox("Disk I/O")
        dl = QVBoxLayout(disk_box)
        self._disk_graph = GraphWidget(vt.COLORS["accent_gold"], "DISK", " KB/s", 1000)
        dl.addWidget(self._disk_graph)
        self._disk_label = QLabel("R: 0  W: 0 KB/s")
        self._disk_label.setAlignment(Qt.AlignCenter)
        self._disk_label.setStyleSheet(f"color: {vt.COLORS['accent_gold']};")
        dl.addWidget(self._disk_label)
        bars_row.addWidget(disk_box)

        ol.addLayout(bars_row)

        temp_box = QGroupBox("Temperatures")
        tl = QHBoxLayout(temp_box)
        self._temp_label = QLabel("Loading...")
        self._temp_label.setAlignment(Qt.AlignCenter)
        tl.addWidget(self._temp_label)
        ol.addWidget(temp_box)

        tabs.addTab(overview, "Overview")

        proc_tab = QWidget()
        pl = QVBoxLayout(proc_tab)
        self._proc_table = QTableWidget()
        self._proc_table.setColumnCount(6)
        self._proc_table.setHorizontalHeaderLabels(["PID", "User", "CPU%", "MEM%", "RSS", "Command"])
        self._proc_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for col in range(5):
            self._proc_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._proc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._proc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        pl.addWidget(self._proc_table)
        tabs.addTab(proc_tab, "Processes")

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        total, idle = read_cpu()
        prev_total, prev_idle = self._prev_cpu
        diff_total = total - prev_total
        diff_idle = idle - prev_idle
        cpu_pct = 0.0 if diff_total <= 0 else max(0.0, (1 - diff_idle / diff_total) * 100)
        self._prev_cpu = (total, idle)
        self._cpu_graph.push(cpu_pct)
        self._cpu_bar.setValue(int(cpu_pct))
        self._cpu_label.setText(f"{cpu_pct:.1f}%")

        used, total_mem = read_mem()
        mem_pct = (used / total_mem * 100) if total_mem else 0
        self._mem_graph.push(mem_pct)
        self._mem_bar.setValue(int(mem_pct))
        self._mem_label.setText(f"{used // 1024} / {total_mem // 1024} MB")

        rx, tx = read_net()
        prev_rx, prev_tx = self._prev_net
        d_rx = max(0, rx - prev_rx) * 1000 // (REFRESH_MS * 1024)
        d_tx = max(0, tx - prev_tx) * 1000 // (REFRESH_MS * 1024)
        self._prev_net = (rx, tx)
        self._net_graph.push(d_rx + d_tx)
        self._net_label.setText(f"RX: {d_rx} KB/s  TX: {d_tx} KB/s")

        dr, dw = read_disk_io()
        prev_dr, prev_dw = self._prev_disk
        d_dr = max(0, dr - prev_dr) * 1000 // (REFRESH_MS * 2)
        d_dw = max(0, dw - prev_dw) * 1000 // (REFRESH_MS * 2)
        self._prev_disk = (dr, dw)
        self._disk_graph.push(d_dr + d_dw)
        self._disk_label.setText(f"R: {d_dr}  W: {d_dw} KB/s")

        temps = []
        for i in range(8):
            p = f"/sys/class/thermal/thermal_zone{i}/temp"
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        t = int(f.read().strip()) / 1000
                    temps.append(f"Zone{i}: {t:.0f}C")
                except (OSError, ValueError):
                    pass
        self._temp_label.setText("  |  ".join(temps) if temps else "N/A")

        self._refresh_procs()

    def _refresh_procs(self):
        try:
            out = subprocess.check_output(
                ["ps", "aux", "--sort=-%cpu"], text=True, timeout=3
            ).splitlines()[1:26]
        except Exception:
            return

        self._proc_table.setRowCount(0)
        for line in out:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            user, pid, cpu, mem, _vsz, rss = parts[:6]
            cmd = parts[10][:60]
            row = self._proc_table.rowCount()
            self._proc_table.insertRow(row)
            for col, val in enumerate((pid, user, cpu, mem, rss, cmd)):
                item = QTableWidgetItem(val)
                try:
                    if float(cpu) > 20:
                        item.setForeground(QBrush(QColor(vt.COLORS["danger"])))
                except ValueError:
                    pass
                self._proc_table.setItem(row, col, item)

        self._status.setText(f"Updated  |  CPU: {self._cpu_bar.value()}%  MEM: {self._mem_bar.value()}%")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = SystemMonitor()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
