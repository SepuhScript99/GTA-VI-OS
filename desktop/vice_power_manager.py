#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Power Settings Center
Power profiles, battery health, display brightness, screen dimming, and sleep timeouts.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QGroupBox, QComboBox, QSpinBox, QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 620
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QSlider::groove:horizontal { background: #1a1a1a; height: 6px; border: 1px solid #00ffff; }
QSlider::handle:horizontal { background: #00ffff; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLabel { color: #00ffff; }
"""


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_battery():
    try:
        for path in ["/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"]:
            if os.path.exists(path):
                def rd(f):
                    try:
                        with open(os.path.join(path, f)) as fp:
                            return fp.read().strip()
                    except Exception:
                        return ""
                cap = rd("capacity")
                status = rd("status")
                return {"percent": int(cap) if cap.isdigit() else 0, "status": status}
    except Exception:
        pass
    return None


def get_brightness():
    for path in [
        "/sys/class/backlight/intel_backlight",
        "/sys/class/backlight/acpi_video0",
        "/sys/class/backlight/amdgpu_bl0",
    ]:
        if os.path.exists(path):
            try:
                cur = int(open(os.path.join(path, "brightness")).read().strip())
                max_b = int(open(os.path.join(path, "max_brightness")).read().strip())
                return path, cur, max_b
            except Exception:
                pass
    return None, 100, 100


def set_brightness(path, value):
    try:
        with open(os.path.join(path, "brightness"), "w") as f:
            f.write(str(value))
        return True
    except Exception:
        out, ok = run_cmd(["sudo", "tee", os.path.join(path, "brightness")])
        return ok


class PowerManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Power Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._brightness_path, self._cur_bright, self._max_bright = get_brightness()
        self._shutdown_timer = None
        self._shutdown_remaining = 0
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(10000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Power Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Battery
        bat_box = QGroupBox("Battery")
        bl = QVBoxLayout(bat_box)
        self._bat_bar = QProgressBar()
        self._bat_bar.setRange(0, 100)
        bl.addWidget(self._bat_bar)
        self._bat_label = QLabel("No battery detected")
        self._bat_label.setAlignment(Qt.AlignCenter)
        bl.addWidget(self._bat_label)
        root.addWidget(bat_box)

        # Brightness
        bright_box = QGroupBox("Screen Brightness")
        brl = QHBoxLayout(bright_box)
        brl.addWidget(QLabel("Dim"))
        self._bright_slider = QSlider(Qt.Horizontal)
        self._bright_slider.setRange(1, self._max_bright)
        self._bright_slider.setValue(self._cur_bright)
        self._bright_slider.valueChanged.connect(self._on_brightness)
        brl.addWidget(self._bright_slider)
        brl.addWidget(QLabel("Bright"))
        self._bright_label = QLabel(f"{int(self._cur_bright / self._max_bright * 100)}%")
        self._bright_label.setFixedWidth(40)
        brl.addWidget(self._bright_label)
        root.addWidget(bright_box)

        # Power profile
        profile_box = QGroupBox("Power Profile")
        pl = QHBoxLayout(profile_box)
        pl.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox()
        self._profile_combo.addItems(["balanced", "power-saver", "performance"])
        self._profile_combo.currentTextChanged.connect(self._set_profile)
        pl.addWidget(self._profile_combo)
        self._profile_status = QLabel("")
        self._profile_status.setStyleSheet("color: #888; font-size: 11px;")
        pl.addWidget(self._profile_status)
        root.addWidget(profile_box)
        self._load_profile()

        # Power actions
        actions_box = QGroupBox("Power Actions")
        al = QVBoxLayout(actions_box)

        btn_row = QHBoxLayout()
        for label, cmd, color in [
            ("Suspend",   ["systemctl", "suspend"],   "#00ffff"),
            ("Hibernate", ["systemctl", "hibernate"],  "#ffaa00"),
            ("Reboot",    ["systemctl", "reboot"],     "#ffaa00"),
            ("Shutdown",  ["systemctl", "poweroff"],   "#ff4444"),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(f"QPushButton {{ border-color: {color}; color: {color}; }} QPushButton:hover {{ background: {color}; color: #0a0a0a; }}")
            btn.clicked.connect(lambda _, c=cmd, l=label: self._power_action(c, l))
            btn_row.addWidget(btn)
        al.addLayout(btn_row)

        # Scheduled shutdown
        sched_row = QHBoxLayout()
        sched_row.addWidget(QLabel("Auto shutdown in:"))
        self._sched_spin = QSpinBox()
        self._sched_spin.setRange(1, 480)
        self._sched_spin.setValue(30)
        self._sched_spin.setSuffix(" min")
        sched_row.addWidget(self._sched_spin)
        self._sched_btn = QPushButton("Schedule")
        self._sched_btn.clicked.connect(self._schedule_shutdown)
        sched_row.addWidget(self._sched_btn)
        self._cancel_sched_btn = QPushButton("Cancel")
        self._cancel_sched_btn.setEnabled(False)
        self._cancel_sched_btn.clicked.connect(self._cancel_schedule)
        sched_row.addWidget(self._cancel_sched_btn)
        al.addLayout(sched_row)

        self._sched_label = QLabel("")
        self._sched_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
        al.addWidget(self._sched_label)
        root.addWidget(actions_box)

        root.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        bat = get_battery()
        if bat:
            self._bat_bar.setValue(bat["percent"])
            pct = bat["percent"]
            status = bat["status"]
            color = "#00ff88" if pct > 50 else "#ffaa00" if pct > 20 else "#ff4444"
            self._bat_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {color}; }}"
                "QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #000; }"
            )
            self._bat_label.setText(f"{pct}%  —  {status}")
        else:
            self._bat_bar.setValue(0)
            self._bat_label.setText("No battery / AC power")

    def _on_brightness(self, value):
        pct = int(value / self._max_bright * 100)
        self._bright_label.setText(f"{pct}%")
        if self._brightness_path:
            set_brightness(self._brightness_path, value)

    def _load_profile(self):
        out, ok = run_cmd(["powerprofilesctl", "get"])
        if ok and out:
            idx = self._profile_combo.findText(out.strip())
            if idx >= 0:
                self._profile_combo.blockSignals(True)
                self._profile_combo.setCurrentIndex(idx)
                self._profile_combo.blockSignals(False)
            self._profile_status.setText(f"Current: {out.strip()}")
        else:
            self._profile_status.setText("powerprofilesctl not available")

    def _set_profile(self, profile):
        out, ok = run_cmd(["powerprofilesctl", "set", profile])
        if ok:
            self._profile_status.setText(f"Set to: {profile}")
            log_info(f"Power profile: {profile}")
        else:
            self._profile_status.setText("Failed to set profile")

    def _power_action(self, cmd, label):
        if QMessageBox.question(
            self, label, f"{label} now?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            subprocess.Popen(cmd)

    def _schedule_shutdown(self):
        mins = self._sched_spin.value()
        self._shutdown_remaining = mins * 60
        self._sched_btn.setEnabled(False)
        self._cancel_sched_btn.setEnabled(True)
        self._shutdown_timer = QTimer()
        self._shutdown_timer.setInterval(1000)
        self._shutdown_timer.timeout.connect(self._tick_shutdown)
        self._shutdown_timer.start()
        log_info(f"Shutdown scheduled in {mins} minutes")

    def _tick_shutdown(self):
        self._shutdown_remaining -= 1
        mins = self._shutdown_remaining // 60
        secs = self._shutdown_remaining % 60
        self._sched_label.setText(f"Shutdown in {mins}m {secs:02d}s")
        if self._shutdown_remaining <= 0:
            self._shutdown_timer.stop()
            subprocess.Popen(["systemctl", "poweroff"])

    def _cancel_schedule(self):
        if self._shutdown_timer:
            self._shutdown_timer.stop()
        self._sched_btn.setEnabled(True)
        self._cancel_sched_btn.setEnabled(False)
        self._sched_label.setText("Shutdown cancelled")
        log_info("Scheduled shutdown cancelled")


def main():
    app = QApplication(sys.argv)
    win = PowerManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
