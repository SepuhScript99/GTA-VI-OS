#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Network Monitor.
Monitors active network interfaces, IP addresses, bandwidth traffic, sockets, and routes.
"""

import os
import re
import shutil
import subprocess
import sys
import time

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QTabWidget, QLineEdit, QGroupBox, QAbstractItemView, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QPainter, QPen

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
HISTORY_LEN = 60  # seconds of bandwidth history
_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-\[\]]+$")


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}/s"
        n /= 1024
    return f"{n:.1f} TB/s"


def read_net_stats():
    stats = {}
    try:
        with open("/proc/net/dev") as f:
            for line in f.readlines()[2:]:
                parts = line.split()
                if len(parts) < 10:
                    continue
                iface = parts[0].rstrip(":")
                rx = int(parts[1])
                tx = int(parts[9])
                stats[iface] = (rx, tx)
    except Exception:
        pass
    return stats


class BandwidthGraph(QWidget):
    def __init__(self, color=None, label=""):
        super().__init__()
        self._data = [0] * HISTORY_LEN
        self._color = QColor(color or COLORS["accent_aqua"])
        self._label = label
        self.setMinimumHeight(80)
        self.setStyleSheet(
            f"background-color: {COLORS['bg_canvas']}; border: 1px solid {COLORS['border']}; border-radius: 6px;"
        )

    def update_data(self, value):
        self._data.append(value)
        if len(self._data) > HISTORY_LEN:
            self._data.pop(0)
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        max_val = max(self._data) or 1

        # Grid lines
        pen = QPen(QColor(COLORS["border"]))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(0, y, w, y)

        # Data line
        pen = QPen(self._color)
        pen.setWidth(2)
        painter.setPen(pen)
        step = w / (HISTORY_LEN - 1)
        points = []
        for i, v in enumerate(self._data):
            x = int(i * step)
            y = int(h - (v / max_val) * (h - 4))
            points.append((x, y))
        for i in range(1, len(points)):
            painter.drawLine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])

        # Label
        painter.setPen(QPen(self._color))
        painter.drawText(6, 15, f"{self._label}: {fmt_bytes(self._data[-1])}")
        painter.drawText(6, h - 5, f"max: {fmt_bytes(max_val)}")
        painter.end()


class BandwidthWorker(QThread):
    stats_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        prev = read_net_stats()
        while not self._stopped:
            for _ in range(5):
                if self._stopped:
                    return
                time.sleep(0.2)
            curr = read_net_stats()
            delta = {}
            for iface in curr:
                if iface in prev:
                    rx = curr[iface][0] - prev[iface][0]
                    tx = curr[iface][1] - prev[iface][1]
                    delta[iface] = (max(0, rx), max(0, tx))
            prev = curr
            if not self._stopped:
                self.stats_ready.emit(delta)


class PingWorker(QThread):
    line_out = pyqtSignal(str)
    ping_done = pyqtSignal()

    def __init__(self, host, count):
        super().__init__()
        self.host = host
        self.count = count
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

    def run(self):
        ping_bin = shutil.which("ping")
        if not ping_bin:
            if not self._stopped:
                self.line_out.emit("ping binary not found.")
                self.ping_done.emit()
            return
        try:
            self._proc = subprocess.Popen(
                [ping_bin, "-c", str(self.count), self.host],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in self._proc.stdout:
                if self._stopped:
                    break
                self.line_out.emit(line.rstrip())
            self._proc.wait()
        except Exception as e:
            if not self._stopped:
                self.line_out.emit(f"Error: {e}")
        finally:
            self._proc = None
        if not self._stopped:
            self.ping_done.emit()


class NetworkMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Network Monitor")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 520)
        apply_app_theme(self)
        self._graphs = {}
        self._bw_worker = None
        self._ping_worker = None
        self._init_ui()
        self._start_bandwidth()
        self._refresh_connections()
        self._conn_timer = QTimer(self)
        self._conn_timer.setInterval(5000)
        self._conn_timer.timeout.connect(self._refresh_connections)
        self._conn_timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Network Monitor",
            subtitle="Live bandwidth graphs, socket inspection, ping, and interface addresses",
            icon_name="network-wired",
            badge_text="NET MON",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Bandwidth tab ---
        bw_tab = QWidget()
        bwl = QVBoxLayout(bw_tab)
        self._graphs_container = QVBoxLayout()
        bwl.addLayout(self._graphs_container)
        bwl.addStretch()
        tabs.addTab(bw_tab, "Bandwidth")

        # --- Connections tab ---
        conn_tab = QWidget()
        connl = QVBoxLayout(conn_tab)
        self._conn_table = QTableWidget()
        self._conn_table.setColumnCount(6)
        self._conn_table.setHorizontalHeaderLabels(
            ["Proto", "Local Address", "Local Port", "Remote Address", "Remote Port", "State"]
        )
        self._conn_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._conn_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        for i in [0, 2, 4, 5]:
            self._conn_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._conn_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._conn_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        connl.addWidget(self._conn_table)

        conn_btns = QHBoxLayout()
        refresh_conn_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_conn_btn.clicked.connect(self._refresh_connections)
        conn_btns.addWidget(refresh_conn_btn)
        conn_btns.addStretch()
        self._conn_count = QLabel("")
        self._conn_count.setObjectName("MutedLabel")
        conn_btns.addWidget(self._conn_count)
        connl.addLayout(conn_btns)
        tabs.addTab(conn_tab, "Connections")

        # --- Ping tab ---
        ping_tab = QWidget()
        pingl = QVBoxLayout(ping_tab)
        ping_ctrl = QHBoxLayout()
        ping_ctrl.addWidget(QLabel("Host:"))
        self._ping_host = QLineEdit("8.8.8.8")
        ping_ctrl.addWidget(self._ping_host)
        ping_ctrl.addWidget(QLabel("Count:"))
        self._ping_count = QSpinBox()
        self._ping_count.setRange(1, 100)
        self._ping_count.setValue(4)
        ping_ctrl.addWidget(self._ping_count)
        self._ping_btn = make_button("Ping", variant="primary", parent=self)
        self._ping_btn.clicked.connect(self._run_ping)
        ping_ctrl.addWidget(self._ping_btn)
        pingl.addLayout(ping_ctrl)
        self._ping_output = QTextEdit()
        self._ping_output.setReadOnly(True)
        pingl.addWidget(self._ping_output)
        tabs.addTab(ping_tab, "Ping")

        # --- Interfaces tab ---
        iface_tab = QWidget()
        il = QVBoxLayout(iface_tab)
        self._iface_table = QTableWidget()
        self._iface_table.setColumnCount(4)
        self._iface_table.setHorizontalHeaderLabels(["Interface", "IP Address", "State", "MAC"])
        self._iface_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._iface_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._iface_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._iface_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._iface_table.setEditTriggers(QTableWidget.NoEditTriggers)
        il.addWidget(self._iface_table)
        refresh_iface_btn = make_button("Refresh Interfaces", variant="secondary", parent=self)
        refresh_iface_btn.clicked.connect(self._refresh_interfaces)
        il.addWidget(refresh_iface_btn)
        tabs.addTab(iface_tab, "Interfaces")
        self._refresh_interfaces()

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _start_bandwidth(self):
        self._bw_worker = BandwidthWorker()
        self._bw_worker.stats_ready.connect(self._on_bw_stats)
        self._bw_worker.start()

    def _on_bw_stats(self, delta):
        for iface, (rx, tx) in delta.items():
            if iface == "lo":
                continue
            if iface not in self._graphs:
                box = QGroupBox(iface)
                bl = QVBoxLayout(box)
                rx_graph = BandwidthGraph(COLORS["accent_aqua"], "RX")
                tx_graph = BandwidthGraph(COLORS["accent_peach"], "TX")
                bl.addWidget(rx_graph)
                bl.addWidget(tx_graph)
                self._graphs[iface] = (rx_graph, tx_graph)
                self._graphs_container.addWidget(box)
            rx_g, tx_g = self._graphs[iface]
            rx_g.update_data(rx)
            tx_g.update_data(tx)

        total_rx = sum(v[0] for v in delta.values() if v)
        total_tx = sum(v[1] for v in delta.values() if v)
        self._status.setText(f"RX {fmt_bytes(total_rx)}  |  TX {fmt_bytes(total_tx)}")

    def _refresh_connections(self):
        self._conn_table.setRowCount(0)
        if not shutil.which("ss"):
            return
        try:
            out = subprocess.check_output(
                ["ss", "-tunp", "--no-header"], text=True, timeout=5
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                proto = parts[0]
                state = parts[1] if len(parts) > 5 else ""
                local = parts[4] if len(parts) > 4 else ""
                remote = parts[5] if len(parts) > 5 else ""

                local_addr, _, local_port = local.rpartition(":")
                remote_addr, _, remote_port = remote.rpartition(":")

                row = self._conn_table.rowCount()
                self._conn_table.insertRow(row)
                self._conn_table.setItem(row, 0, QTableWidgetItem(proto))
                self._conn_table.setItem(row, 1, QTableWidgetItem(local_addr))
                self._conn_table.setItem(row, 2, QTableWidgetItem(local_port))
                self._conn_table.setItem(row, 3, QTableWidgetItem(remote_addr))
                self._conn_table.setItem(row, 4, QTableWidgetItem(remote_port))
                state_item = QTableWidgetItem(state)
                if "ESTAB" in state:
                    state_item.setForeground(QBrush(QColor(COLORS["success"])))
                elif "LISTEN" in state:
                    state_item.setForeground(QBrush(QColor(COLORS["accent_aqua"])))
                elif "TIME-WAIT" in state or "CLOSE" in state:
                    state_item.setForeground(QBrush(QColor(COLORS["text_muted"])))
                self._conn_table.setItem(row, 5, state_item)
        except Exception as e:
            log_error(f"Connection refresh failed: {e}")
        self._conn_count.setText(f"{self._conn_table.rowCount()} connection(s)")

    def _run_ping(self):
        host = self._ping_host.text().strip()
        if not host or host.startswith("-") or not _HOST_RE.match(host):
            self._ping_output.setPlainText("Enter a valid hostname or IP address.")
            return
        if self._ping_worker is not None and self._ping_worker.isRunning():
            return
        self._ping_btn.setEnabled(False)
        self._ping_output.clear()
        w = PingWorker(host, self._ping_count.value())
        w.line_out.connect(self._ping_output.append)
        w.ping_done.connect(lambda: self._ping_btn.setEnabled(True))
        w.start()
        self._ping_worker = w

    def _refresh_interfaces(self):
        self._iface_table.setRowCount(0)
        if not shutil.which("ip"):
            return
        try:
            out = subprocess.check_output(["ip", "-br", "addr"], text=True, timeout=5)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 2:
                    continue
                iface = parts[0]
                state = parts[1]
                ips = parts[2:] if len(parts) > 2 else ["—"]
                mac = ""
                try:
                    with open(f"/sys/class/net/{iface}/address", encoding="utf-8") as fp:
                        mac = fp.read().strip()
                except Exception:
                    pass

                row = self._iface_table.rowCount()
                self._iface_table.insertRow(row)
                self._iface_table.setItem(row, 0, QTableWidgetItem(iface))
                self._iface_table.setItem(row, 1, QTableWidgetItem(", ".join(ips)))
                state_item = QTableWidgetItem(state)
                col = COLORS["success"] if state == "UP" else COLORS["text_muted"]
                state_item.setForeground(QBrush(QColor(col)))
                self._iface_table.setItem(row, 2, state_item)
                self._iface_table.setItem(row, 3, QTableWidgetItem(mac))
        except Exception as e:
            log_error(f"Interface refresh failed: {e}")

    def closeEvent(self, event):
        self._conn_timer.stop()
        for w in (self._bw_worker, self._ping_worker):
            if w is not None:
                w.stop()
        for w in (self._bw_worker, self._ping_worker):
            if w is not None and w.isRunning():
                w.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = NetworkMonitor()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
