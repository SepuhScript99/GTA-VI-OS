#!/usr/bin/env python3
"""Vice OS — Accessibility Settings. Font size, contrast, cursor, sticky keys, slow keys."""

import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel,
    QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 660

ACC_CONFIG = os.path.expanduser("~/.config/vice-os/accessibility.conf")


def run_cmd(cmd):
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=5)
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out, r.returncode == 0
    except Exception:
        return "", False


def read_acc_config():
    cfg = {}
    if os.path.exists(ACC_CONFIG):
        try:
            with open(ACC_CONFIG, encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        cfg[k] = v.strip()
        except Exception:
            pass
    return cfg


def write_acc_config(cfg):
    os.makedirs(os.path.dirname(ACC_CONFIG), exist_ok=True)
    try:
        with open(ACC_CONFIG, "w", encoding="utf-8") as f:
            for k, v in cfg.items():
                f.write(f"{k}={v}\n")
        return True
    except Exception as e:
        log_error(f"Accessibility config write failed: {e}")
        return False


class AccessibilitySettings(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Accessibility Settings")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(540, 520)
        vt.apply_app_theme(self)
        self._cfg = read_acc_config()
        self._init_ui()
        self._load_current()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Accessibility Settings",
            "Font scale, contrast, pointer size, sticky/slow/bounce keys",
            icon_name="preferences-desktop-accessibility",
            badge_text="A11Y",
            badge_variant="aqua",
            parent=self,
        ))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget(scroll)
        bl = QVBoxLayout(body)

        vis_box = QGroupBox("Visual")
        vv = QVBoxLayout(vis_box)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font scale (x0.1):"))
        self._font_slider = QSlider(Qt.Horizontal)
        self._font_slider.setRange(8, 18)
        self._font_slider.setTickPosition(QSlider.TicksBelow)
        self._font_slider.setTickInterval(1)
        self._font_slider.setValue(11)
        self._font_slider.valueChanged.connect(self._font_changed)
        font_row.addWidget(self._font_slider)
        self._font_label = QLabel("11")
        self._font_label.setFixedWidth(30)
        font_row.addWidget(self._font_label)
        vv.addLayout(font_row)

        cur_row = QHBoxLayout()
        cur_row.addWidget(QLabel("Cursor size:"))
        self._cursor_combo = QComboBox()
        self._cursor_combo.addItems(["Small", "Medium", "Large", "Extra Large"])
        cur_row.addWidget(self._cursor_combo)
        vv.addLayout(cur_row)

        self._contrast_cb = QCheckBox("High contrast mode")
        vv.addWidget(self._contrast_cb)

        self._large_text_cb = QCheckBox("Enlarge text in menus and dialogs")
        vv.addWidget(self._large_text_cb)
        bl.addWidget(vis_box)

        kb_box = QGroupBox("Keyboard")
        vk = QVBoxLayout(kb_box)

        self._sticky_cb = QCheckBox("Sticky keys (press modifier keys once)")
        vk.addWidget(self._sticky_cb)

        self._slow_keys_cb = QCheckBox("Slow keys (delay before key press)")
        vk.addWidget(self._slow_keys_cb)

        slow_row = QHBoxLayout()
        slow_row.addWidget(QLabel("Delay (ms):"))
        self._slow_delay_spin = QSpinBox()
        self._slow_delay_spin.setRange(100, 2000)
        self._slow_delay_spin.setSingleStep(100)
        slow_row.addWidget(self._slow_delay_spin)
        slow_row.addStretch()
        vk.addLayout(slow_row)

        self._bounce_keys_cb = QCheckBox("Bounce keys (ignore rapid key repeats)")
        vk.addWidget(self._bounce_keys_cb)

        bounce_row = QHBoxLayout()
        bounce_row.addWidget(QLabel("Delay (ms):"))
        self._bounce_delay_spin = QSpinBox()
        self._bounce_delay_spin.setRange(100, 2000)
        self._bounce_delay_spin.setSingleStep(100)
        bounce_row.addWidget(self._bounce_delay_spin)
        bounce_row.addStretch()
        vk.addLayout(bounce_row)
        bl.addWidget(kb_box)

        mouse_box = QGroupBox("Mouse / Pointing")
        vm = QVBoxLayout(mouse_box)
        self._mouse_keys_cb = QCheckBox("Mouse keys (use numeric keypad to move cursor)")
        vm.addWidget(self._mouse_keys_cb)
        self._dwell_cb = QCheckBox("Dwell click (pause to click)")
        vm.addWidget(self._dwell_cb)
        bl.addWidget(mouse_box)
        bl.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

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

    def _font_changed(self, val):
        self._font_label.setText(str(val))

    def _load_current(self):
        self._font_slider.setValue(int(self._cfg.get("font_scale", 11)))
        self._contrast_cb.setChecked(self._cfg.get("high_contrast", "off") == "on")
        self._large_text_cb.setChecked(self._cfg.get("large_text", "off") == "on")
        self._sticky_cb.setChecked(self._cfg.get("sticky_keys", "off") == "on")
        self._slow_keys_cb.setChecked(self._cfg.get("slow_keys", "off") == "on")
        self._slow_delay_spin.setValue(int(self._cfg.get("slow_delay", 300)))
        self._bounce_keys_cb.setChecked(self._cfg.get("bounce_keys", "off") == "on")
        self._bounce_delay_spin.setValue(int(self._cfg.get("bounce_delay", 500)))
        self._mouse_keys_cb.setChecked(self._cfg.get("mouse_keys", "off") == "on")
        self._dwell_cb.setChecked(self._cfg.get("dwell_click", "off") == "on")

        cur_map = {"small": 0, "medium": 1, "large": 2, "extra large": 3}
        cur = self._cfg.get("cursor_size", "medium").lower()
        self._cursor_combo.setCurrentIndex(cur_map.get(cur, 1))

        out, ok = run_cmd(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"])
        if ok and out not in ("not_found", ""):
            try:
                val = int(float(out) * 10)
                self._font_slider.setValue(min(max(val, 8), 18))
            except ValueError:
                pass

    def _apply(self):
        cfg = {
            "font_scale": str(self._font_slider.value()),
            "high_contrast": "on" if self._contrast_cb.isChecked() else "off",
            "large_text": "on" if self._large_text_cb.isChecked() else "off",
            "sticky_keys": "on" if self._sticky_cb.isChecked() else "off",
            "slow_keys": "on" if self._slow_keys_cb.isChecked() else "off",
            "slow_delay": str(self._slow_delay_spin.value()),
            "bounce_keys": "on" if self._bounce_keys_cb.isChecked() else "off",
            "bounce_delay": str(self._bounce_delay_spin.value()),
            "mouse_keys": "on" if self._mouse_keys_cb.isChecked() else "off",
            "dwell_click": "on" if self._dwell_cb.isChecked() else "off",
            "cursor_size": self._cursor_combo.currentText().lower(),
        }
        write_acc_config(cfg)

        factor = self._font_slider.value() / 10.0
        if self._large_text_cb.isChecked():
            factor = max(factor, 1.25)
        run_cmd(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", str(factor)])
        cursor_px = {"small": "24", "medium": "32", "large": "48", "extra large": "64"}
        run_cmd([
            "gsettings", "set", "org.gnome.desktop.interface", "cursor-size",
            cursor_px.get(cfg["cursor_size"], "32"),
        ])

        scheme = "prefer-high-contrast" if self._contrast_cb.isChecked() else "default"
        run_cmd(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", scheme])

        run_cmd([
            "gsettings", "set", "org.gnome.desktop.a11y.keyboard", "stickykeys-enable",
            "true" if self._sticky_cb.isChecked() else "false",
        ])
        run_cmd([
            "gsettings", "set", "org.gnome.desktop.a11y.keyboard", "slowkeys-enable",
            "true" if self._slow_keys_cb.isChecked() else "false",
        ])
        if self._slow_keys_cb.isChecked():
            run_cmd([
                "gsettings", "set", "org.gnome.desktop.a11y.keyboard", "slowkeys-delay",
                str(self._slow_delay_spin.value()),
            ])
        run_cmd([
            "gsettings", "set", "org.gnome.desktop.a11y.keyboard", "bouncekeys-enable",
            "true" if self._bounce_keys_cb.isChecked() else "false",
        ])
        if self._bounce_keys_cb.isChecked():
            run_cmd([
                "gsettings", "set", "org.gnome.desktop.a11y.keyboard", "bouncekeys-delay",
                str(self._bounce_delay_spin.value()),
            ])
        run_cmd([
            "gsettings", "set", "org.gnome.desktop.a11y.keyboard", "mousekeys-enable",
            "true" if self._mouse_keys_cb.isChecked() else "false",
        ])
        run_cmd([
            "gsettings", "set", "org.gnome.desktop.a11y.mouse", "dwell-click-enabled",
            "true" if self._dwell_cb.isChecked() else "false",
        ])

        self._status.setText("Settings applied")
        log_info("Accessibility settings applied")

    def _reset(self):
        self._font_slider.setValue(11)
        self._contrast_cb.setChecked(False)
        self._large_text_cb.setChecked(False)
        self._sticky_cb.setChecked(False)
        self._slow_keys_cb.setChecked(False)
        self._slow_delay_spin.setValue(300)
        self._bounce_keys_cb.setChecked(False)
        self._bounce_delay_spin.setValue(500)
        self._mouse_keys_cb.setChecked(False)
        self._dwell_cb.setChecked(False)
        self._cursor_combo.setCurrentIndex(1)
        self._apply()


def main():
    app = QApplication(sys.argv)
    win = AccessibilitySettings()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
