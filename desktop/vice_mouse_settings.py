#!/usr/bin/env python3
"""Vice OS — Mouse & Touchpad Settings. Speed, tap-to-click, scrolling, disable while typing."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QGroupBox, QCheckBox, QSpinBox, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 560
WINDOW_HEIGHT = 540

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QSlider::groove:horizontal { background: #1a1a1a; height: 6px; border: 1px solid #00ffff; }
QSlider::handle:horizontal { background: #00ffff; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 10px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 16px; height: 16px; background: #1a1a1a; border: 1px solid #00ffff; border-radius: 3px; }
QCheckBox::indicator:checked { background: #00ffff; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLabel { color: #00ffff; }
"""

TOUCHPAD_CONF = "/etc/X11/xorg.conf.d/90-touchpad.conf"
USER_TOUCHPAD = os.path.expanduser("~/.config/touchpad.conf")
XINPUT_DEV = "/usr/bin/xinput"


def run_cmd(cmd):
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_touchpad_devices():
    out, _ = run_cmd("xinput list --name-only")
    return [l.strip() for l in out.splitlines() if "touchpad" in l.lower() or "trackpad" in l.lower()]


def get_mouse_props(device):
    props = {}
    out, _ = run_cmd(f"xinput list-props '{device}'")
    for line in out.splitlines():
        if ":" in line:
            parts = line.split(":", 1)
            prop = parts[0].strip()
            val = parts[1].strip().strip("()")
            props[prop] = val
    return props


def set_xinput(device, prop_name, value):
    run_cmd(f"xinput set-prop '{device}' '{prop_name}' {value}")


def read_libinput_settings():
    settings = {}
    out, _ = run_cmd("gsettings get org.gnome.desktop.peripherals.touchpad tap-to-click 2>/dev/null || echo not_found")
    for key in ["tap-to-click", "disable-while-typing", "edge-scrolling-enabled", "natural-scroll"]:
        out, ok = run_cmd(f"gsettings get org.gnome.desktop.peripherals.touchpad {key}")
        if ok and out != "not_found":
            settings[key] = out
    return settings


def write_xorg_touchpad_config(enabled=True, tap=True, speed=0.5, vert_scroll=True, naturalscroll=False):
    content = f"""Section "InputClass"
    Identifier "touchpad catchall"
    Driver "libinput"
    MatchIsTouchpad "on"
    Option "Tapping" "{'on' if tap else 'off'}"
    Option "PointerSpeed" "{speed}"
    Option "VertScrollDelta" "{80 if vert_scroll else 0}"
    Option "NaturalScrolling" "{'on' if naturalscroll else 'off'}"
    Option "DisableWhileTyping" "on"
EndSection
"""
    try:
        os.makedirs(os.path.dirname(TOUCHPAD_CONF), exist_ok=True)
        with open(TOUCHPAD_CONF, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        log_error(f"Touchpad config write failed: {e}")
        try:
            os.makedirs(os.path.dirname(USER_TOUCHPAD), exist_ok=True)
            with open(USER_TOUCHPAD, "w") as f:
                f.write(content)
            return True
        except Exception as e2:
            log_error(f"User touchpad config write failed: {e2}")
            return False


class MouseSettings(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Mouse & Touchpad")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._devices = get_touchpad_devices()
        self._init_ui()
        self._load_current()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Mouse & Touchpad Settings")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Touchpad
        tp_box = QGroupBox("Touchpad")
        tp = QVBoxLayout(tp_box)

        self._tp_enabled_cb = QCheckBox("Enable touchpad")
        self._tp_enabled_cb.setChecked(True)
        self._tp_enabled_cb.toggled.connect(self._apply)
        tp.addWidget(self._tp_enabled_cb)

        self._tap_cb = QCheckBox("Tap-to-click")
        self._tap_cb.toggled.connect(self._apply)
        tp.addWidget(self._tap_cb)

        self._dwt_cb = QCheckBox("Disable touchpad while typing")
        self._dwt_cb.setChecked(True)
        self._dwt_cb.toggled.connect(self._apply)
        tp.addWidget(self._dwt_cb)

        self._edge_scroll_cb = QCheckBox("Edge scrolling")
        self._edge_scroll_cb.toggled.connect(self._apply)
        tp.addWidget(self._edge_scroll_cb)

        self._natural_cb = QCheckBox("Natural scrolling")
        self._natural_cb.toggled.connect(self._apply)
        tp.addWidget(self._natural_cb)

        # Speed slider
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(-10, 10)
        self._speed_slider.setValue(0)
        self._speed_slider.valueChanged.connect(self._apply)
        speed_row.addWidget(self._speed_slider)
        self._speed_label = QLabel("0")
        self._speed_label.setFixedWidth(30)
        speed_row.addWidget(self._speed_label)
        tp.addLayout(speed_row)

        root.addWidget(tp_box)

        # Mouse settings
        mouse_box = QGroupBox("Mouse")
        m = QVBoxLayout(mouse_box)

        m.addWidget(QLabel("Mouse speed:"))
        speed_row2 = QHBoxLayout()
        self._mouse_speed_slider = QSlider(Qt.Horizontal)
        self._mouse_speed_slider.setRange(-10, 10)
        self._mouse_speed_slider.setValue(0)
        speed_row2.addWidget(self._mouse_speed_slider)
        self._mouse_speed_label = QLabel("0")
        self._mouse_speed_label.setFixedWidth(30)
        speed_row2.addWidget(self._mouse_speed_label)
        m.addLayout(speed_row2)

        m.addWidget(QLabel("Double-click speed (ms):"))
        self._dclick_spin = QSpinBox()
        self._dclick_spin.setRange(100, 1000)
        self._dclick_spin.setSingleStep(50)
        self._dclick_spin.setValue(400)
        m.addWidget(self._dclick_spin)

        root.addWidget(mouse_box)

        # Buttons
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _load_current(self):
        out, ok = run_cmd("gsettings get org.gnome.desktop.peripherals.touchpad tap-to-click 2>/dev/null")
        if ok:
            self._tap_cb.setChecked("true" in out.lower())
        out, ok = run_cmd("gsettings get org.gnome.desktop.peripherals.touchpad disable-while-typing 2>/dev/null")
        if ok:
            self._dwt_cb.setChecked("true" in out.lower())
        out, ok = run_cmd("gsettings get org.gnome.desktop.peripherals.touchpad natural-scroll 2>/dev/null")
        if ok:
            self._natural_cb.setChecked("true" in out.lower())
        out, ok = run_cmd("gsettings get org.gnome.desktop.peripherals.touchpad edge-scrolling-enabled 2>/dev/null")
        if ok:
            self._edge_scroll_cb.setChecked("true" in out.lower())
        self._status.setText(f"Touchpad device(s): {', '.join(self._devices) or 'not detected'}")

    def _apply(self):
        tap = self._tap_cb.isChecked()
        dwt = self._dwt_cb.isChecked()
        edge = self._edge_scroll_cb.isChecked()
        natural = self._natural_cb.isChecked()
        speed = self._speed_slider.value()
        self._speed_label.setText(str(speed))
        self._mouse_speed_label.setText(str(self._mouse_speed_slider.value()))

        # gsettings
        run_cmd(f"gsettings set org.gnome.desktop.peripherals.touchpad tap-to-click {str(tap).lower()}")
        run_cmd(f"gsettings set org.gnome.desktop.peripherals.touchpad disable-while-typing {str(dwt).lower()}")
        run_cmd(f"gsettings set org.gnome.desktop.peripherals.touchpad natural-scroll {str(natural).lower()}")
        run_cmd(f"gsettings set org.gnome.desktop.peripherals.touchpad edge-scrolling-enabled {str(edge).lower()}")

        # X input for immediate effect
        for dev in self._devices:
            set_xinput(dev, "libinput Tapping Enabled", 1 if tap else 0)
            set_xinput(dev, "libinput Disable While Typing Enabled", 1 if dwt else 0)
            set_xinput(dev, "libinput Natural Scrolling Enabled", 1 if natural else 0)
            set_xinput(dev, "libinput Accel Speed", speed / 10.0)

        # Write Xorg config for persistence
        ok = write_xorg_touchpad_config(
            enabled=self._tp_enabled_cb.isChecked(),
            tap=tap, speed=speed / 10.0,
            vert_scroll=edge, naturalscroll=natural
        )
        self._status.setText("Settings applied" + ("" if ok else " (Xorg config requires sudo)"))
        log_info(f"Mouse/touchpad settings applied: tap={tap} dwt={dwt} edge={edge} natural={natural} speed={speed}")

    def _reset(self):
        self._tap_cb.setChecked(True)
        self._dwt_cb.setChecked(True)
        self._edge_scroll_cb.setChecked(False)
        self._natural_cb.setChecked(False)
        self._speed_slider.setValue(0)
        self._mouse_speed_slider.setValue(0)
        self._dclick_spin.setValue(400)
        self._apply()


def main():
    app = QApplication(sys.argv)
    win = MouseSettings()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()