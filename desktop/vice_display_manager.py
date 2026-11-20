#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Display Manager
Screen resolution, refresh rate, orientation, and multi-monitor layout configuration.
"""

import sys
import os
import subprocess
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGroupBox, QMessageBox, QSpinBox, QCheckBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 13px; height: 13px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QSlider::groove:horizontal { background: #1a1a1a; height: 4px; border: 1px solid #00ffff; }
QSlider::handle:horizontal { background: #00ffff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QLabel { color: #00ffff; }
"""


def run_xrandr():
    try:
        return subprocess.check_output(["xrandr"], text=True, timeout=5)
    except Exception:
        return ""


def parse_displays(xrandr_out):
    displays = {}
    current = None
    for line in xrandr_out.splitlines():
        m = re.match(r'^(\S+)\s+(connected|disconnected)', line)
        if m:
            current = m.group(1)
            connected = m.group(2) == "connected"
            geo = re.search(r'(\d+x\d+)\+(\d+)\+(\d+)', line)
            displays[current] = {
                "connected": connected,
                "active": geo is not None,
                "current_res": geo.group(1) if geo else "",
                "offset_x": geo.group(2) if geo else "0",
                "offset_y": geo.group(3) if geo else "0",
                "modes": [],
                "current_rate": "",
            }
        elif current and re.match(r'^\s+\d+x\d+', line):
            parts = line.split()
            if parts:
                res = parts[0]
                rates = []
                for p in parts[1:]:
                    rate = p.replace("*", "").replace("+", "")
                    try:
                        rates.append(float(rate))
                    except ValueError:
                        pass
                is_current = "*" in line
                if is_current:
                    rate_match = re.search(r'(\d+\.\d+)\*', line)
                    if rate_match:
                        displays[current]["current_rate"] = rate_match.group(1)
                displays[current]["modes"].append({"res": res, "rates": rates, "current": is_current})
    return displays


class ApplyWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmds):
        super().__init__()
        self.cmds = cmds

    def run(self):
        for cmd in self.cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    self.done.emit(False, r.stderr.strip() or "xrandr error")
                    return
            except Exception as e:
                self.done.emit(False, str(e))
                return
        self.done.emit(True, "Settings applied")


class DisplayPage(QWidget):
    def __init__(self, name, info):
        super().__init__()
        self._name = name
        self._info = info
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        status = "Connected" if self._info["connected"] else "Disconnected"
        active = "Active" if self._info["active"] else "Inactive"
        hdr = QLabel(f"{self._name}  —  {status}  |  {active}")
        hdr.setFont(QFont("monospace", 12, QFont.Bold))
        hdr.setStyleSheet("color: #ff00ff;")
        root.addWidget(hdr)

        # Resolution
        res_box = QGroupBox("Resolution")
        rl = QHBoxLayout(res_box)
        rl.addWidget(QLabel("Resolution:"))
        self._res_combo = QComboBox()
        seen = set()
        for mode in self._info["modes"]:
            if mode["res"] not in seen:
                self._res_combo.addItem(mode["res"])
                seen.add(mode["res"])
        if self._info["current_res"]:
            idx = self._res_combo.findText(self._info["current_res"])
            if idx >= 0:
                self._res_combo.setCurrentIndex(idx)
        self._res_combo.currentTextChanged.connect(self._update_rates)
        rl.addWidget(self._res_combo)

        rl.addWidget(QLabel("Refresh Rate:"))
        self._rate_combo = QComboBox()
        rl.addWidget(self._rate_combo)
        root.addWidget(res_box)
        self._update_rates(self._res_combo.currentText())

        # Position / offset
        pos_box = QGroupBox("Position (offset)")
        pl = QHBoxLayout(pos_box)
        pl.addWidget(QLabel("X:"))
        self._x_spin = QSpinBox()
        self._x_spin.setRange(0, 7680)
        self._x_spin.setValue(int(self._info["offset_x"] or 0))
        pl.addWidget(self._x_spin)
        pl.addWidget(QLabel("Y:"))
        self._y_spin = QSpinBox()
        self._y_spin.setRange(0, 4320)
        self._y_spin.setValue(int(self._info["offset_y"] or 0))
        pl.addWidget(self._y_spin)
        root.addWidget(pos_box)

        # Options
        opt_box = QGroupBox("Options")
        ol = QHBoxLayout(opt_box)
        self._primary_cb = QCheckBox("Set as primary")
        ol.addWidget(self._primary_cb)
        self._rotate_combo = QComboBox()
        self._rotate_combo.addItems(["normal", "left", "right", "inverted"])
        ol.addWidget(QLabel("Rotation:"))
        ol.addWidget(self._rotate_combo)
        self._off_cb = QCheckBox("Turn off this display")
        ol.addWidget(self._off_cb)
        root.addWidget(opt_box)

        root.addStretch()

    def _update_rates(self, res):
        self._rate_combo.clear()
        for mode in self._info["modes"]:
            if mode["res"] == res:
                for r in mode["rates"]:
                    self._rate_combo.addItem(f"{r:.2f} Hz")
                break

    def build_xrandr_args(self):
        if self._off_cb.isChecked():
            return ["--output", self._name, "--off"]
        args = ["--output", self._name,
                "--mode", self._res_combo.currentText(),
                "--pos", f"{self._x_spin.value()}x{self._y_spin.value()}",
                "--rotate", self._rotate_combo.currentText()]
        rate_text = self._rate_combo.currentText().replace(" Hz", "")
        if rate_text:
            args += ["--rate", rate_text]
        if self._primary_cb.isChecked():
            args += ["--primary"]
        return args


class DisplayManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Display Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._display_pages = {}
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Display Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)

        self._revert_btn = QPushButton("Revert / Re-scan")
        self._revert_btn.clicked.connect(self._scan)
        btn_row.addWidget(self._revert_btn)

        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

        self._scan()

    def _scan(self):
        self._tabs.clear()
        self._display_pages.clear()
        out = run_xrandr()
        if not out:
            self._status.setText("xrandr not available or no display server")
            placeholder = QLabel("No display information available.\n(xrandr required)")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #444; font-size: 14px;")
            self._tabs.addTab(placeholder, "No displays")
            return

        displays = parse_displays(out)
        for name, info in displays.items():
            if not info["connected"]:
                continue
            page = DisplayPage(name, info)
            self._display_pages[name] = page
            self._tabs.addTab(page, name)

        if not self._display_pages:
            self._status.setText("No connected displays found")
        else:
            self._status.setText(f"Found {len(self._display_pages)} display(s)")

    def _apply(self):
        if not self._display_pages:
            return
        self._apply_btn.setEnabled(False)
        xrandr_cmd = ["xrandr"]
        for page in self._display_pages.values():
            xrandr_cmd += page.build_xrandr_args()

        self._worker = ApplyWorker([xrandr_cmd])
        self._worker.done.connect(self._on_apply_done)
        self._worker.start()
        self._status.setText("Applying...")

    def _on_apply_done(self, ok, msg):
        self._apply_btn.setEnabled(True)
        self._status.setText(msg)
        if ok:
            log_info(f"Display settings applied")
        else:
            log_error(f"Display apply failed: {msg}")
            QMessageBox.warning(self, "Apply Failed", msg)


def main():
    app = QApplication(sys.argv)
    win = DisplayManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
