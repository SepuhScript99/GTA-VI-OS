#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Audio Manager
PulseAudio/PipeWire volume control, audio sink/source switching, and stream management.
"""

import sys
import os
import subprocess
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QGroupBox,
    QComboBox, QAbstractItemView, QTabWidget, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QSlider::groove:horizontal { background: #1a1a1a; height: 6px; border: 1px solid #00ffff; }
QSlider::handle:horizontal { background: #00ffff; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #00ffff; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QLabel { color: #00ffff; }
"""


def pactl(*args):
    try:
        r = subprocess.run(["pactl"] + list(args), capture_output=True, text=True, timeout=5)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_sinks():
    out, _ = pactl("list", "sinks")
    sinks = []
    current = {}
    for line in out.splitlines():
        m = re.match(r'^Sink #(\d+)', line)
        if m:
            if current:
                sinks.append(current)
            current = {"index": m.group(1), "name": "", "desc": "", "volume": 0, "muted": False}
        elif current:
            if "Name:" in line:
                current["name"] = line.split("Name:")[1].strip()
            elif "Description:" in line:
                current["desc"] = line.split("Description:")[1].strip()
            elif "Volume:" in line and "%" in line:
                m2 = re.search(r'(\d+)%', line)
                if m2:
                    current["volume"] = int(m2.group(1))
            elif "Mute:" in line:
                current["muted"] = "yes" in line.lower()
    if current:
        sinks.append(current)
    return sinks


def get_sources():
    out, _ = pactl("list", "sources")
    sources = []
    current = {}
    for line in out.splitlines():
        m = re.match(r'^Source #(\d+)', line)
        if m:
            if current:
                sources.append(current)
            current = {"index": m.group(1), "name": "", "desc": "", "volume": 0, "muted": False}
        elif current:
            if "Name:" in line:
                current["name"] = line.split("Name:")[1].strip()
            elif "Description:" in line:
                current["desc"] = line.split("Description:")[1].strip()
            elif "Volume:" in line and "%" in line:
                m2 = re.search(r'(\d+)%', line)
                if m2:
                    current["volume"] = int(m2.group(1))
            elif "Mute:" in line:
                current["muted"] = "yes" in line.lower()
    if current:
        sources.append(current)
    return sources


def get_sink_inputs():
    out, _ = pactl("list", "sink-inputs")
    inputs = []
    current = {}
    for line in out.splitlines():
        m = re.match(r'^Sink Input #(\d+)', line)
        if m:
            if current:
                inputs.append(current)
            current = {"index": m.group(1), "app": "", "volume": 0, "muted": False, "sink": ""}
        elif current:
            if "application.name" in line:
                current["app"] = line.split("=")[1].strip().strip('"')
            elif "Volume:" in line and "%" in line:
                m2 = re.search(r'(\d+)%', line)
                if m2:
                    current["volume"] = int(m2.group(1))
            elif "Mute:" in line:
                current["muted"] = "yes" in line.lower()
            elif "Sink:" in line:
                current["sink"] = line.split("Sink:")[1].strip()
    if current:
        inputs.append(current)
    return inputs


def build_device_row(device, device_type, layout, on_vol_change, on_mute, on_default):
    box = QGroupBox(device["desc"] or device["name"])
    bl = QVBoxLayout(box)

    row1 = QHBoxLayout()
    mute_btn = QPushButton("Unmute" if device["muted"] else "Mute")
    mute_btn.setStyleSheet("color: #ffaa00; border-color: #ffaa00;" if device["muted"] else "")
    mute_btn.clicked.connect(lambda: on_mute(device["index"], device_type))
    row1.addWidget(mute_btn)

    default_btn = QPushButton("Set Default")
    default_btn.clicked.connect(lambda: on_default(device["name"], device_type))
    row1.addWidget(default_btn)
    row1.addStretch()

    vol_label = QLabel(f"{device['volume']}%")
    vol_label.setFixedWidth(40)
    row1.addWidget(vol_label)
    bl.addLayout(row1)

    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 150)
    slider.setValue(device["volume"])
    slider.valueChanged.connect(lambda v: (vol_label.setText(f"{v}%"), on_vol_change(device["index"], v, device_type)))
    bl.addWidget(slider)
    layout.addWidget(box)


class AudioManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Audio Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh_apps)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Audio Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # Output tab
        self._out_tab = QWidget()
        self._out_layout = QVBoxLayout(self._out_tab)
        self._out_layout.addStretch()
        tabs.addTab(self._out_tab, "Output (Sinks)")

        # Input tab
        self._in_tab = QWidget()
        self._in_layout = QVBoxLayout(self._in_tab)
        self._in_layout.addStretch()
        tabs.addTab(self._in_tab, "Input (Sources)")

        # Per-app tab
        self._app_tab = QWidget()
        self._app_layout = QVBoxLayout(self._app_tab)
        self._app_table = QTableWidget()
        self._app_table.setColumnCount(4)
        self._app_table.setHorizontalHeaderLabels(["App", "Volume", "Muted", "Sink"])
        self._app_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._app_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._app_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._app_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._app_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._app_layout.addWidget(self._app_table)
        tabs.addTab(self._app_tab, "Per-App Volume")

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh(self):
        self._clear_layout(self._out_layout)
        for sink in get_sinks():
            build_device_row(sink, "sink", self._out_layout,
                             self._set_volume, self._toggle_mute, self._set_default)
        self._out_layout.addStretch()

        self._clear_layout(self._in_layout)
        for source in get_sources():
            if "monitor" not in source["name"].lower():
                build_device_row(source, "source", self._in_layout,
                                 self._set_volume, self._toggle_mute, self._set_default)
        self._in_layout.addStretch()

        self._refresh_apps()

    def _refresh_apps(self):
        self._app_table.setRowCount(0)
        for inp in get_sink_inputs():
            row = self._app_table.rowCount()
            self._app_table.insertRow(row)
            self._app_table.setItem(row, 0, QTableWidgetItem(inp["app"] or f"Input #{inp['index']}"))
            self._app_table.setItem(row, 1, QTableWidgetItem(f"{inp['volume']}%"))
            muted = QTableWidgetItem("Yes" if inp["muted"] else "No")
            muted.setForeground(QBrush(QColor("#ffaa00" if inp["muted"] else "#00ff88")))
            self._app_table.setItem(row, 2, muted)
            self._app_table.setItem(row, 3, QTableWidgetItem(inp["sink"]))
        self._status.setText(f"{self._app_table.rowCount()} app stream(s)")

    def _set_volume(self, index, volume, device_type):
        cmd = "set-sink-volume" if device_type == "sink" else "set-source-volume"
        pactl(cmd, index, f"{volume}%")

    def _toggle_mute(self, index, device_type):
        cmd = "set-sink-mute" if device_type == "sink" else "set-source-mute"
        pactl(cmd, index, "toggle")
        self._refresh()

    def _set_default(self, name, device_type):
        cmd = "set-default-sink" if device_type == "sink" else "set-default-source"
        pactl(cmd, name)
        log_info(f"Default {device_type} set to {name}")
        self._status.setText(f"Default {device_type}: {name}")


def main():
    app = QApplication(sys.argv)
    win = AudioManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
