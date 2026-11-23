#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Power Settings Center.
Power profiles, battery health, display brightness, screen dimming, and sleep timeouts.
"""

import os
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QSlider, QGroupBox, QComboBox, QSpinBox, QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 610


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_battery():
    try:
        for path in ("/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"):
            if os.path.exists(path):
                def rd(f):
                    try:
                        with open(os.path.join(path, f), encoding="utf-8") as fp:
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
    for path in (
        "/sys/class/backlight/intel_backlight",
        "/sys/class/backlight/acpi_video0",
        "/sys/class/backlight/amdgpu_bl0",
    ):
        if os.path.exists(path):
            try:
                with open(os.path.join(path, "brightness"), encoding="utf-8") as fp:
                    cur = int(fp.read().strip())
                with open(os.path.join(path, "max_brightness"), encoding="utf-8") as fp:
                    max_b = max(1, int(fp.read().strip()))
                return path, cur, max_b
            except Exception:
                pass
    return None, 100, 100


def set_brightness(path, value, max_b=100, allow_pkexec=False):
    if path:
        b_file = os.path.join(path, "brightness")
        try:
            with open(b_file, "w", encoding="utf-8") as f:
                f.write(str(value))
            return True
        except OSError:
            if allow_pkexec and shutil.which("pkexec"):
                try:
                    r = subprocess.run(
                        ["pkexec", "tee", b_file],
                        input=f"{value}\n", capture_output=True, text=True, timeout=10,
                    )
                    return r.returncode == 0
                except Exception:
                    return False
        return False

    # Software X11 output brightness fallback (for VirtualBox/VM displays)
    if shutil.which("xrandr"):
        try:
            res = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=3)
            ratio = max(0.3, min(1.0, float(value) / max(1, max_b)))
            for line in res.stdout.splitlines():
                if " connected" in line:
                    out_name = line.split()[0]
                    subprocess.run(
                        ["xrandr", "--output", out_name, "--brightness", f"{ratio:.2f}"],
                        capture_output=True, text=True, timeout=3,
                    )
                    return True
        except Exception:
            pass
    return False


class PowerManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Power Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(540, 520)
        apply_app_theme(self)
        self._brightness_path, self._cur_bright, self._max_bright = get_brightness()
        self._shutdown_timer = None
        self._shutdown_remaining = 0
        self._init_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(10000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Power Manager",
            subtitle="Battery telemetry, display brightness, power profiles, and scheduled sleep",
            icon_name="battery-full",
            badge_text="POWER",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

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
        min_b = max(1, int(self._max_bright * 0.2)) if not self._brightness_path else 1
        self._bright_slider.setRange(min_b, self._max_bright)
        self._bright_slider.setValue(max(min_b, self._cur_bright))
        self._bright_slider.valueChanged.connect(self._on_brightness)
        self._bright_slider.sliderReleased.connect(self._on_brightness_release)
        brl.addWidget(self._bright_slider)
        brl.addWidget(QLabel("Bright"))
        self._bright_label = QLabel(f"{int(self._cur_bright / self._max_bright * 100)}%")
        self._bright_label.setFixedWidth(44)
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
        self._profile_status.setObjectName("MutedLabel")
        pl.addWidget(self._profile_status)
        root.addWidget(profile_box)
        self._load_profile()

        # Power actions
        actions_box = QGroupBox("Power Actions")
        al = QVBoxLayout(actions_box)

        btn_row = QHBoxLayout()
        for label, cmd, variant in (
            ("Suspend", ["systemctl", "suspend"], "secondary"),
            ("Hibernate", ["systemctl", "hibernate"], "secondary"),
            ("Reboot", ["systemctl", "reboot"], "secondary"),
            ("Shutdown", ["systemctl", "poweroff"], "danger"),
        ):
            btn = make_button(label, variant=variant, parent=self)
            btn.clicked.connect(lambda _=False, c=cmd, lbl=label: self._power_action(c, lbl))
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
        self._sched_btn = make_button("Schedule", variant="primary", parent=self)
        self._sched_btn.clicked.connect(self._schedule_shutdown)
        sched_row.addWidget(self._sched_btn)
        self._cancel_sched_btn = make_button("Cancel", variant="secondary", parent=self)
        self._cancel_sched_btn.setEnabled(False)
        self._cancel_sched_btn.clicked.connect(self._cancel_schedule)
        sched_row.addWidget(self._cancel_sched_btn)
        al.addLayout(sched_row)

        self._sched_label = QLabel("")
        self._sched_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px;")
        al.addWidget(self._sched_label)
        root.addWidget(actions_box)

        root.addStretch()
        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _refresh(self):
        bat = get_battery()
        if bat:
            self._bat_bar.setValue(bat["percent"])
            pct = bat["percent"]
            status = bat["status"]
            color = COLORS["success"] if pct > 50 else COLORS["warning"] if pct > 20 else COLORS["danger"]
            self._bat_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
                f"QProgressBar {{ border: 1px solid {COLORS['border']}; background: {COLORS['bg_canvas']}; "
                f"text-align: center; color: {COLORS['text_primary']}; font-weight: 600; }}"
            )
            self._bat_label.setText(f"{pct}%  —  {status}")
        else:
            self._bat_bar.setValue(0)
            self._bat_bar.setStyleSheet("")
            self._bat_label.setText("No battery / AC power")

    def _on_brightness(self, value):
        pct = int(value / self._max_bright * 100)
        self._bright_label.setText(f"{pct}%")
        set_brightness(self._brightness_path, value, self._max_bright, allow_pkexec=False)

    def _on_brightness_release(self):
        value = self._bright_slider.value()
        set_brightness(self._brightness_path, value, self._max_bright, allow_pkexec=True)

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
        _out, ok = run_cmd(["powerprofilesctl", "set", profile])
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
        if self._shutdown_timer is not None:
            self._shutdown_timer.stop()
        self._shutdown_timer = QTimer(self)
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

    def closeEvent(self, event):
        self._timer.stop()
        if self._shutdown_timer is not None:
            self._shutdown_timer.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = PowerManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
