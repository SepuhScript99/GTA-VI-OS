#!/usr/bin/env python3
"""Vice OS — Mouse & Touchpad Settings. Speed, tap-to-click, scrolling, disable while typing."""

import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QGroupBox, QHBoxLayout, QLabel, QSlider,
    QSpinBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 580
WINDOW_HEIGHT = 560

TOUCHPAD_CONF = "/etc/X11/xorg.conf.d/90-touchpad.conf"
USER_TOUCHPAD = os.path.expanduser("~/.config/touchpad.conf")


def run_cmd(cmd):
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=5)
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out, r.returncode == 0
    except Exception as e:
        return str(e), False


def get_touchpad_devices():
    out, ok = run_cmd(["xinput", "list", "--name-only"])
    if not ok:
        return []
    return [
        line.strip() for line in out.splitlines()
        if "touchpad" in line.lower() or "trackpad" in line.lower()
    ]


def get_mouse_props(device):
    props = {}
    out, ok = run_cmd(["xinput", "list-props", device])
    if not ok:
        return props
    for line in out.splitlines():
        if ":" in line:
            prop, val = line.split(":", 1)
            props[prop.strip()] = val.strip().strip("()")
    return props


def set_xinput(device, prop_name, value):
    run_cmd(["xinput", "set-prop", device, prop_name, str(value)])


def read_libinput_settings():
    settings = {}
    for key in ("tap-to-click", "disable-while-typing", "edge-scrolling-enabled", "natural-scroll"):
        out, ok = run_cmd(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", key])
        if ok and out != "not_found":
            settings[key] = out
    return settings


def write_xorg_touchpad_config(enabled=True, tap=True, speed=0.5, vert_scroll=True, naturalscroll=False):
    content = (
        'Section "InputClass"\n'
        '    Identifier "touchpad catchall"\n'
        '    Driver "libinput"\n'
        '    MatchIsTouchpad "on"\n'
        f'    Option "Tapping" "{"on" if tap else "off"}"\n'
        f'    Option "PointerSpeed" "{speed}"\n'
        f'    Option "VertScrollDelta" "{80 if vert_scroll else 0}"\n'
        f'    Option "NaturalScrolling" "{"on" if naturalscroll else "off"}"\n'
        '    Option "DisableWhileTyping" "on"\n'
        'EndSection\n'
    )
    target = TOUCHPAD_CONF if (os.geteuid() == 0 if hasattr(os, "geteuid") else False) else USER_TOUCHPAD
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except OSError as e:
        log_error(f"Touchpad config write failed: {e}")
        return False


class MouseSettings(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Mouse & Touchpad")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(500, 480)
        vt.apply_app_theme(self)
        self._loading = False
        self._devices = get_touchpad_devices()
        self._init_ui()
        self._load_current()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Mouse & Touchpad",
            "Pointer acceleration, tap-to-click, natural scroll & palm rejection",
            icon_name="input-mouse",
            badge_text="INPUT",
            badge_variant="aqua",
            parent=self,
        ))

        tp_box = QGroupBox("Touchpad")
        tp = QVBoxLayout(tp_box)

        self._tp_enabled_cb = QCheckBox("Enable touchpad")
        self._tp_enabled_cb.setChecked(True)
        self._tp_enabled_cb.toggled.connect(self._on_option_changed)
        tp.addWidget(self._tp_enabled_cb)

        self._tap_cb = QCheckBox("Tap-to-click")
        self._tap_cb.toggled.connect(self._on_option_changed)
        tp.addWidget(self._tap_cb)

        self._dwt_cb = QCheckBox("Disable touchpad while typing")
        self._dwt_cb.setChecked(True)
        self._dwt_cb.toggled.connect(self._on_option_changed)
        tp.addWidget(self._dwt_cb)

        self._edge_scroll_cb = QCheckBox("Edge scrolling")
        self._edge_scroll_cb.toggled.connect(self._on_option_changed)
        tp.addWidget(self._edge_scroll_cb)

        self._natural_cb = QCheckBox("Natural scrolling")
        self._natural_cb.toggled.connect(self._on_option_changed)
        tp.addWidget(self._natural_cb)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(-10, 10)
        self._speed_slider.setValue(0)
        self._speed_slider.valueChanged.connect(lambda v: self._speed_label.setText(str(v)))
        self._speed_slider.sliderReleased.connect(self._apply)
        speed_row.addWidget(self._speed_slider)
        self._speed_label = QLabel("0")
        self._speed_label.setFixedWidth(30)
        speed_row.addWidget(self._speed_label)
        tp.addLayout(speed_row)
        root.addWidget(tp_box)

        mouse_box = QGroupBox("Mouse")
        m = QVBoxLayout(mouse_box)

        m.addWidget(QLabel("Mouse speed:"))
        speed_row2 = QHBoxLayout()
        self._mouse_speed_slider = QSlider(Qt.Horizontal)
        self._mouse_speed_slider.setRange(-10, 10)
        self._mouse_speed_slider.setValue(0)
        self._mouse_speed_slider.valueChanged.connect(
            lambda v: self._mouse_speed_label.setText(str(v))
        )
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

        btn_row = QHBoxLayout()
        apply_btn = vt.make_button("Apply", "primary", parent=self)
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)

        reset_btn = vt.make_button("Reset", "secondary", parent=self)
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _on_option_changed(self):
        if not self._loading:
            self._apply()

    def _load_current(self):
        self._loading = True
        try:
            mapping = (
                ("tap-to-click", self._tap_cb),
                ("disable-while-typing", self._dwt_cb),
                ("natural-scroll", self._natural_cb),
                ("edge-scrolling-enabled", self._edge_scroll_cb),
            )
            for key, cb in mapping:
                out, ok = run_cmd(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", key])
                if ok:
                    cb.setChecked("true" in out.lower())
        finally:
            self._loading = False
        self._status.setText(f"Touchpad device(s): {', '.join(self._devices) or 'not detected'}")

    def _apply(self):
        enabled = self._tp_enabled_cb.isChecked()
        tap = self._tap_cb.isChecked()
        dwt = self._dwt_cb.isChecked()
        edge = self._edge_scroll_cb.isChecked()
        natural = self._natural_cb.isChecked()
        speed = self._speed_slider.value()
        mouse_speed = self._mouse_speed_slider.value()
        self._speed_label.setText(str(speed))
        self._mouse_speed_label.setText(str(mouse_speed))

        gsettings_pairs = (
            ("tap-to-click", str(tap).lower()),
            ("disable-while-typing", str(dwt).lower()),
            ("natural-scroll", str(natural).lower()),
            ("edge-scrolling-enabled", str(edge).lower()),
        )
        for key, val in gsettings_pairs:
            run_cmd(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", key, val])

        for dev in self._devices:
            run_cmd(["xinput", "enable" if enabled else "disable", dev])
            set_xinput(dev, "libinput Tapping Enabled", 1 if tap else 0)
            set_xinput(dev, "libinput Disable While Typing Enabled", 1 if dwt else 0)
            set_xinput(dev, "libinput Natural Scrolling Enabled", 1 if natural else 0)
            set_xinput(dev, "libinput Accel Speed", speed / 10.0)

        ok = write_xorg_touchpad_config(
            enabled=enabled, tap=tap, speed=speed / 10.0,
            vert_scroll=edge, naturalscroll=natural,
        )
        self._status.setText("Settings applied" if ok else "Applied runtime only (config save failed)")
        log_info(
            f"Mouse/touchpad settings applied: tap={tap} dwt={dwt} edge={edge} "
            f"natural={natural} speed={speed}"
        )

    def _reset(self):
        self._loading = True
        try:
            self._tp_enabled_cb.setChecked(True)
            self._tap_cb.setChecked(True)
            self._dwt_cb.setChecked(True)
            self._edge_scroll_cb.setChecked(False)
            self._natural_cb.setChecked(False)
            self._speed_slider.setValue(0)
            self._mouse_speed_slider.setValue(0)
            self._dclick_spin.setValue(400)
        finally:
            self._loading = False
        self._apply()


def main():
    app = QApplication(sys.argv)
    win = MouseSettings()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
