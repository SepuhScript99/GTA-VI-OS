#!/usr/bin/env python3
"""Vice OS — Theme Manager. Apply color themes, GTK/Qt styling, font selection, icon themes."""

import json
import os
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGroupBox, QFontComboBox, QSlider, QListWidget,
    QListWidgetItem, QSplitter, QFrame, QLineEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info, log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    CJK_FONT_FAMILIES,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 920
WINDOW_HEIGHT = 640

THEME_FILE = os.path.expanduser("~/.config/vice-os/theme.json")
QSS_FILE = os.path.expanduser("~/.config/vice-os/theme.qss")

THEMES = {
    "Leonida Dusk": {
        "primary": COLORS["accent_coral"],
        "accent": COLORS["accent_aqua"],
        "bg": COLORS["bg_canvas"],
        "fg": COLORS["text_primary"],
    },
    "Sunset Coral": {"primary": "#FF9A62", "accent": "#F7C873", "bg": "#121018", "fg": "#F5F6FA"},
    "Emerald Pine": {"primary": "#3ED598", "accent": "#36D6C3", "bg": "#0B1210", "fg": "#EAF5F0"},
    "Crimson Slate": {"primary": "#F25C6E", "accent": "#FF9A62", "bg": "#130F14", "fg": "#F5F6FA"},
    "Ocean Mist": {"primary": "#5E9EFF", "accent": "#36D6C3", "bg": "#0D111A", "fg": "#EDF2FA"},
    "Nord Dusk": {"primary": "#88C0D0", "accent": "#EBCB8B", "bg": "#1D222B", "fg": "#ECEFF4"},
    "Solar Gold": {"primary": "#F7C873", "accent": "#FF9A62", "bg": "#12110E", "fg": "#F8F6EE"},
    "Obsidian Mono": {"primary": "#A6AEBF", "accent": "#F5F6FA", "bg": "#0E1015", "fg": "#F5F6FA"},
}


def build_qss(theme):
    fonts = ", ".join(f'"{f}"' for f in CJK_FONT_FAMILIES)
    return (
        f"QWidget {{ background-color: {theme['bg']}; color: {theme['fg']}; font-family: {fonts}; }}\n"
        f"QPushButton {{ background: #141621; color: {theme['fg']}; border: 1px solid #262A3D; border-radius: 6px; padding: 6px 14px; }}\n"
        f"QPushButton:hover {{ border-color: {theme['primary']}; background: #1B1E2D; }}\n"
        f"QPushButton:disabled {{ color: #6E778C; border-color: #262A3D; }}\n"
        f"QLineEdit, QComboBox {{ background: #141621; color: {theme['fg']}; border: 1px solid #262A3D; border-radius: 6px; padding: 5px 8px; }}\n"
        f"QTableWidget, QListWidget, QTextEdit {{ background: #141621; color: {theme['fg']}; border: 1px solid #262A3D; border-radius: 6px; }}\n"
        f"QListWidget::item:selected, QTableWidget::item:selected {{ background: #23273A; color: {theme['primary']}; }}\n"
        f"QTabBar::tab {{ background: #141621; color: #A6AEBF; padding: 6px 14px; }}\n"
        f"QTabBar::tab:selected {{ color: {theme['primary']}; border-bottom: 2px solid {theme['primary']}; }}\n"
        f"QGroupBox {{ border: 1px solid #262A3D; border-radius: 8px; margin-top: 10px; padding: 8px; }}\n"
        f"QGroupBox::title {{ color: {theme['accent']}; subcontrol-origin: margin; left: 8px; }}\n"
        f"QProgressBar {{ border: 1px solid #262A3D; background: #141621; text-align: center; color: {theme['fg']}; }}\n"
        f"QProgressBar::chunk {{ background: {theme['primary']}; }}\n"
    )


class ColorSwatch(QFrame):
    def __init__(self, color, label_text):
        super().__init__()
        self.setFixedSize(48, 48)
        self._color = QColor(color)
        self._label = label_text
        self.setToolTip(f"{label_text}: {color}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), self._color)
        p.setPen(QColor("#0D0E15") if self._color.lightness() > 128 else QColor("#F5F6FA"))
        p.drawText(self.rect(), Qt.AlignCenter, self._label)
        p.end()


class ThemeManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Theme Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(720, 500)
        apply_app_theme(self)
        self._current_theme = "Leonida Dusk"
        self._init_ui()
        self._load_current()
        self._apply_preview()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Theme Manager",
            subtitle="Customize Vice OS palette presets, system fonts, and icon themes",
            icon_name="preferences-desktop-theme",
            badge_text="APPEARANCE",
            badge_variant="coral",
            parent=self,
        )
        root.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Available Themes:"))
        self._theme_list = QListWidget()
        for name in THEMES:
            item = QListWidgetItem(name)
            t = THEMES[name]
            item.setForeground(QColor(t["primary"]))
            self._theme_list.addItem(item)
        self._theme_list.currentTextChanged.connect(self._on_theme_selected)
        ll.addWidget(self._theme_list)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        prev_box = QGroupBox("Preview")
        pv = QVBoxLayout(prev_box)

        self._preview_frame = QFrame()
        self._preview_frame.setMinimumHeight(120)
        self._preview_layout = QVBoxLayout(self._preview_frame)
        pv.addWidget(self._preview_frame)

        swatch_row = QHBoxLayout()
        t_def = THEMES[self._current_theme]
        self._swatch_primary = ColorSwatch(t_def["primary"], "P")
        self._swatch_accent = ColorSwatch(t_def["accent"], "A")
        self._swatch_bg = ColorSwatch(t_def["bg"], "B")
        self._swatch_fg = ColorSwatch(t_def["fg"], "F")
        swatch_row.addWidget(QLabel("Colors:"))
        swatch_row.addWidget(self._swatch_primary)
        swatch_row.addWidget(self._swatch_accent)
        swatch_row.addWidget(self._swatch_bg)
        swatch_row.addWidget(self._swatch_fg)
        swatch_row.addStretch()
        pv.addLayout(swatch_row)
        rl.addWidget(prev_box)

        font_box = QGroupBox("System Font")
        fb = QVBoxLayout(font_box)
        self._font_combo = QFontComboBox()
        self._font_combo.currentFontChanged.connect(self._font_changed)
        fb.addWidget(self._font_combo)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._font_size = QSlider(Qt.Horizontal)
        self._font_size.setRange(8, 16)
        self._font_size.setValue(10)
        size_row.addWidget(self._font_size)
        self._font_size_label = QLabel("10")
        self._font_size.valueChanged.connect(lambda v: self._font_size_label.setText(str(v)))
        size_row.addWidget(self._font_size_label)
        fb.addLayout(size_row)
        rl.addWidget(font_box)

        icon_box = QGroupBox("Icon Theme")
        ib = QVBoxLayout(icon_box)
        self._icon_combo = QComboBox()
        self._icon_combo.addItems(["Papirus-Dark", "Adwaita-dark", "breeze-dark", "System Default"])
        ib.addWidget(self._icon_combo)
        rl.addWidget(icon_box)

        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([260, 620])

        btn_row = QHBoxLayout()
        apply_btn = make_button("Apply Theme", variant="primary", parent=self)
        apply_btn.clicked.connect(self._apply_theme)
        btn_row.addWidget(apply_btn)

        reset_btn = make_button("Reset to Leonida Dusk", variant="secondary", parent=self)
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _load_current(self):
        if os.path.exists(THEME_FILE):
            try:
                with open(THEME_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("name", "Leonida Dusk")
                if name in THEMES:
                    self._current_theme = name
            except Exception:
                pass
        idx = list(THEMES.keys()).index(self._current_theme)
        self._theme_list.setCurrentRow(idx)

    def _on_theme_selected(self, name):
        if name in THEMES:
            self._current_theme = name
            self._apply_preview()

    def _apply_preview(self):
        theme = THEMES[self._current_theme]
        self._swatch_primary._color = QColor(theme["primary"])
        self._swatch_accent._color = QColor(theme["accent"])
        self._swatch_bg._color = QColor(theme["bg"])
        self._swatch_fg._color = QColor(theme["fg"])
        for sw in (self._swatch_primary, self._swatch_accent, self._swatch_bg, self._swatch_fg):
            sw.update()

        self._preview_frame.setStyleSheet(
            f"background-color: {theme['bg']}; border: 1px solid {theme['primary']}; border-radius: 8px; padding: 8px;"
        )

        inner = self._preview_layout
        while inner.count():
            item = inner.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        btn = QPushButton("Sample Button")
        edit = QLineEdit("Text input")
        lbl = QLabel("Sample Label")
        for w in (btn, edit, lbl):
            inner.addWidget(w)

    def _font_changed(self, _font):
        self._font_size_label.setText(str(self._font_size.value()))

    def _apply_theme(self):
        theme = THEMES[self._current_theme]
        font = self._font_combo.currentFont().family()
        font_size = self._font_size.value()
        icon_theme = self._icon_combo.currentText()

        os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
        config = {
            "name": self._current_theme,
            **theme,
            "font": font,
            "font_size": font_size,
            "icon_theme": icon_theme,
        }
        try:
            with open(THEME_FILE, "w", encoding="utf-8", newline="\n") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            log_error(f"Theme save failed: {e}")

        try:
            qss = build_qss(theme)
            with open(QSS_FILE, "w", encoding="utf-8", newline="\n") as f:
                f.write(qss)
        except Exception as e:
            log_error(f"QSS write failed: {e}")

        if shutil.which("gsettings"):
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Adwaita-dark"],
                capture_output=True,
            )
            if icon_theme != "System Default":
                subprocess.run(
                    ["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icon_theme],
                    capture_output=True,
                )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "font-name", f"{font} {font_size}"],
                capture_output=True,
            )

        self._status.setText(f"Theme applied: {self._current_theme}")
        log_info(f"Theme applied: {self._current_theme} font={font} size={font_size}")

    def _reset(self):
        self._current_theme = "Leonida Dusk"
        self._theme_list.setCurrentRow(0)
        self._font_size.setValue(10)
        self._apply_theme()


def main():
    app = QApplication(sys.argv)
    win = ThemeManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
