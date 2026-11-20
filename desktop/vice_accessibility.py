#!/usr/bin/env python3
"""Vice OS — Accessibility Settings. Font size, contrast, cursor, sticky keys, slow keys."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QGroupBox, QCheckBox, QSpinBox, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 620
WINDOW_HEIGHT = 620

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
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QLabel { color: #00ffff; }
"""

ACC_CONFIG = os.path.expanduser("~/.config/vice-os/accessibility.conf")


def run_cmd(cmd):
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip(), r.returncode == 0
    except Exception:
        return "", False


def read_acc_config():
    cfg = {}
    if os.path.exists(ACC_CONFIG):
        try:
            with open(ACC_CONFIG) as f:
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
        with open(ACC_CONFIG, "w") as f:
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
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._cfg = read_acc_config()
        self._init_ui()
        self._load_current()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Accessibility Settings")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # --- Visual ---
        vis_box = QGroupBox("Visual")
        vv = QVBoxLayout(vis_box)

        # Font scale
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font scale:"))
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

        # Cursor size
        cur_row = QHBoxLayout()
        cur_row.addWidget(QLabel("Cursor size:"))
        self._cursor_combo = QComboBox()
        self._cursor_combo.addItems(["Small", "Medium", "Large", "Extra Large"])
        cur_row.addWidget(self._cursor_combo)
        vv.addLayout(cur_row)

        # High contrast
        self._contrast_cb = QCheckBox("High contrast mode")
        vv.addWidget(self._contrast_cb)

        # Large text
        self._large_text_cb = QCheckBox("Enlarge text in menus and dialogs")
        vv.addWidget(self._large_text_cb)

        root.addWidget(vis_box)

        # --- Keyboard ---
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
        vk.addLayout(slow_row)

        self._bounce_keys_cb = QCheckBox("Bounce keys (ignore rapid key repeats)")
        vk.addWidget(self._bounce_keys_cb)

        bounce_row = QHBoxLayout()
        bounce_row.addWidget(QLabel("Delay (ms):"))
        self._bounce_delay_spin = QSpinBox()
        self._bounce_delay_spin.setRange(100, 2000)
        self._bounce_delay_spin.setSingleStep(100)
        bounce_row.addWidget(self._bounce_delay_spin)
        vk.addLayout(bounce_row)

        root.addWidget(kb_box)

        # --- Mouse / Pointing ---
        mouse_box = QGroupBox("Mouse / Pointing")
        vm = QVBoxLayout(mouse_box)

        self._mouse_keys_cb = QCheckBox("Mouse keys (use numeric keypad to move cursor)")
        vm.addWidget(self._mouse_keys_cb)

        self._dwell_cb = QCheckBox("Dwell click (pause to click)")
        vm.addWidget(self._dwell_cb)

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

        # Load from xsettings
        out, ok = run_cmd("gsettings get org.gnome.desktop.interface text-scaling-factor")
        if ok and out not in ("not_found", ""):
            try:
                val = int(float(out) * 10)
                self._font_slider.setValue(min(max(val, 8), 18))
            except Exception:
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

        # Apply font scaling
        factor = self._font_slider.value() / 10.0
        run_cmd(f"gsettings set org.gnome.desktop.interface text-scaling-factor {factor}")

        # High contrast
        if self._contrast_cb.isChecked():
            run_cmd("gsettings set org.gnome.desktop.interface color-scheme 'prefer-high-contrast'")
        else:
            run_cmd("gsettings set org.gnome.desktop.interface color-scheme 'default'")

        # Sticky keys via GNOME AT-SPI
        if self._sticky_cb.isChecked():
            run_cmd("gsettings set org.gnome.desktop.a11y.keyboard stickykeys-enable true")
        else:
            run_cmd("gsettings set org.gnome.desktop.a11y.keyboard stickykeys-enable false")

        if self._slow_keys_cb.isChecked():
            run_cmd("gsettings set org.gnome.desktop.a11y.keyboard slowkeys-enable true")
            run_cmd(f"gsettings set org.gnome.desktop.a11y.keyboard slowkeys-delay {self._slow_delay_spin.value()}")
        else:
            run_cmd("gsettings set org.gnome.desktop.a11y.keyboard slowkeys-enable false")

        if self._bounce_keys_cb.isChecked():
            run_cmd("gsettings set org.gnome.desktop.a11y.keyboard bouncekeys-enable true")
        else:
            run_cmd("gsettings set org.gnome.desktop.a11y.keyboard bouncekeys-enable false")

        if self._mouse_keys_cb.isChecked():
            run_cmd("gsettings set org.gnome.desktop.a11y.mousenamekeys enable true")
        else:
            run_cmd("gsettings set org.gnome.desktop.a11y.mousenamekeys enable false")

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