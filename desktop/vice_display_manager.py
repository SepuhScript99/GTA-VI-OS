#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Display Manager
Screen resolution, refresh rate, orientation, and multi-monitor layout configuration.
"""

import re
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 580


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

    def __init__(self, cmds, parent=None):
        super().__init__(parent)
        self.cmds = list(cmds)
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        for cmd in self.cmds:
            if self._cancelled:
                return
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    if not self._cancelled:
                        self.done.emit(False, (r.stderr or "").strip() or "xrandr error")
                    return
            except Exception as e:
                if not self._cancelled:
                    self.done.emit(False, str(e))
                return
        if not self._cancelled:
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
        hdr.setStyleSheet(f"color: {vt.COLORS['accent_coral']};")
        root.addWidget(hdr)

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

        if self._info.get("current_rate"):
            try:
                cur_label = f"{float(self._info['current_rate']):.2f} Hz"
                ridx = self._rate_combo.findText(cur_label)
                if ridx >= 0:
                    self._rate_combo.setCurrentIndex(ridx)
            except ValueError:
                pass

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
        pl.addStretch()
        root.addWidget(pos_box)

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
                for rate in mode["rates"]:
                    self._rate_combo.addItem(f"{rate:.2f} Hz")
                break

    def build_xrandr_args(self):
        if self._off_cb.isChecked():
            return ["--output", self._name, "--off"]
        res = self._res_combo.currentText().strip()
        args = ["--output", self._name]
        if res:
            args += ["--mode", res]
        else:
            args += ["--auto"]
        args += [
            "--pos", f"{self._x_spin.value()}x{self._y_spin.value()}",
            "--rotate", self._rotate_combo.currentText(),
        ]
        rate_text = self._rate_combo.currentText().replace(" Hz", "").strip()
        if rate_text:
            args += ["--rate", rate_text]
        if self._primary_cb.isChecked():
            args += ["--primary"]
        return args


class DisplayManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Display Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(720, 460)
        vt.apply_app_theme(self)
        self._display_pages = {}
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Display Manager",
            "Resolution, refresh rate, rotation and multi-monitor layout",
            icon_name="video-display",
            badge_text="XRANDR",
            badge_variant="coral",
            parent=self,
        ))

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        btn_row = QHBoxLayout()
        self._apply_btn = vt.make_button("Apply", "primary", parent=self)
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)

        self._revert_btn = vt.make_button("Revert / Re-scan", "secondary", parent=self)
        self._revert_btn.clicked.connect(self._scan)
        btn_row.addWidget(self._revert_btn)

        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']};")
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
            placeholder.setStyleSheet(f"color: {vt.COLORS['text_muted']}; font-size: 14px;")
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
        if self._worker is not None and self._worker.isRunning():
            return
        self._apply_btn.setEnabled(False)
        xrandr_cmd = ["xrandr"]
        for page in self._display_pages.values():
            xrandr_cmd += page.build_xrandr_args()

        self._worker = ApplyWorker([xrandr_cmd], parent=self)
        self._worker.done.connect(self._on_apply_done)
        self._worker.start()
        self._status.setText("Applying...")

    def _on_apply_done(self, ok, msg):
        self._apply_btn.setEnabled(True)
        self._status.setText(msg)
        if ok:
            log_info("Display settings applied")
        else:
            log_error(f"Display apply failed: {msg}")
            QMessageBox.warning(self, "Apply Failed", msg)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = DisplayManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
