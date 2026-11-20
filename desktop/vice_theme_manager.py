#!/usr/bin/env python3
"""Vice OS — Theme Manager. Apply color themes, GTK/Qt styling, font selection, icon themes."""

import sys
import os
import subprocess
import json

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGroupBox, QMessageBox, QFontComboBox, QSlider, QListWidget,
    QListWidgetItem, QSplitter, QFrame, QLineEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPainter

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 10px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QSlider::groove:horizontal { background: #1a1a1a; height: 6px; border: 1px solid #00ffff; }
QSlider::handle:horizontal { background: #00ffff; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""

THEME_FILE = os.path.expanduser("~/.config/vice-os/theme.json")
QSS_FILE = os.path.expanduser("~/.config/vice-os/theme.qss")

THEMES = {
    "Cyberpunk Cyan":  {"primary": "#00ffff", "accent": "#ff00ff", "bg": "#0a0a0a", "fg": "#ccffff"},
    "Blood Red":       {"primary": "#ff2222", "accent": "#ff8800", "bg": "#0a0a0a", "fg": "#ffcccc"},
    "Matrix Green":    {"primary": "#00ff41", "accent": "#00aa00", "bg": "#000a00", "fg": "#ccffcc"},
    "Neon Purple":     {"primary": "#bf00ff", "accent": "#ff00ff", "bg": "#0a0a0a", "fg": "#eeccff"},
    "Solar Gold":      {"primary": "#ffd700", "accent": "#ff8c00", "bg": "#0a0a0a", "fg": "#fff8dd"},
    "Ice Blue":        {"primary": "#88ccff", "accent": "#0088ff", "bg": "#0d0d12", "fg": "#e0f0ff"},
    "Vaporwave":       {"primary": "#ff71ce", "accent": "#01cdfe", "bg": "#0d0221", "fg": "#ffb3f0"},
    "Terminal Amber":  {"primary": "#ffb000", "accent": "#ff6600", "bg": "#0a0a00", "fg": "#ffe0a0"},
}


def build_qss(theme):
    return f"""
QWidget {{ background-color: {theme['bg']}; color: {theme['fg']}; font-family: monospace; }}
QPushButton {{ background: #1a1a1a; color: {theme['primary']}; border: 1px solid {theme['primary']}; padding: 5px 14px; }}
QPushButton:hover {{ background: {theme['primary']}; color: {theme['bg']}; }}
QPushButton:disabled {{ color: #444; border-color: #444; }}
QLineEdit {{ background: #1a1a1a; color: {theme['primary']}; border: 1px solid {theme['primary']}; padding: 5px; }}
QComboBox {{ background: #1a1a1a; color: {theme['primary']}; border: 1px solid {theme['primary']}; padding: 4px; }}
QTableWidget {{ background: #0d0d0d; color: {theme['primary']}; gridline-color: #1a4a4a; border: 1px solid {theme['primary']}; }}
QHeaderView::section {{ background: {theme['primary']}; color: {theme['bg']}; padding: 4px; font-weight: bold; }}
QTableWidget::item:selected {{ background: {theme['accent']}; color: {theme['bg']}; }}
QListWidget {{ background: #0d0d0d; color: {theme['primary']}; border: 1px solid {theme['primary']}; }}
QListWidget::item:selected {{ background: {theme['primary']}; color: {theme['bg']}; }}
QTabBar::tab {{ background: #1a1a1a; color: {theme['primary']}; padding: 6px 14px; }}
QTabBar::tab:selected {{ background: {theme['primary']}; color: {theme['bg']}; }}
QTabWidget::pane {{ border: 1px solid {theme['primary']}; }}
QGroupBox {{ border: 1px solid {theme['primary']}; margin-top: 10px; padding: 8px; }}
QGroupBox::title {{ color: {theme['accent']}; subcontrol-origin: margin; left: 8px; }}
QProgressBar {{ border: 1px solid {theme['primary']}; background: #1a1a1a; text-align: center; color: {theme['primary']}; }}
QProgressBar::chunk {{ background: {theme['primary']}; }}
QTextEdit {{ background: #0d0d0d; color: {theme['fg']}; border: 1px solid #1a4a4a; }}
QScrollBar:vertical {{ background: {theme['bg']}; width: 8px; }}
QScrollBar::handle:vertical {{ background: {theme['primary']}; border-radius: 4px; }}
QLabel {{ color: {theme['primary']}; }}
"""


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
        p.setPen(QColor("#000000") if self._color.lightness() > 128 else QColor("#ffffff"))
        p.drawText(self.rect(), Qt.AlignCenter, self._label)


class ThemeManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Theme Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._current_theme = "Cyberpunk Cyan"
        self._init_ui()
        self._load_current()
        self._apply_preview()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Theme Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: theme list
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

        # Right: preview + options
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        # Preview widgets
        prev_box = QGroupBox("Preview")
        pv = QVBoxLayout(prev_box)

        self._preview_frame = QFrame()
        self._preview_frame.setMinimumHeight(120)
        pv.addWidget(self._preview_frame)

        swatch_row = QHBoxLayout()
        self._swatch_primary = ColorSwatch("#00ffff", "P")
        self._swatch_accent = ColorSwatch("#ff00ff", "A")
        self._swatch_bg = ColorSwatch("#0a0a0a", "B")
        self._swatch_fg = ColorSwatch("#ccffff", "F")
        swatch_row.addWidget(QLabel("Colors:"))
        swatch_row.addWidget(self._swatch_primary)
        swatch_row.addWidget(self._swatch_accent)
        swatch_row.addWidget(self._swatch_bg)
        swatch_row.addWidget(self._swatch_fg)
        swatch_row.addStretch()
        pv.addLayout(swatch_row)
        rl.addWidget(prev_box)

        # Font selection
        font_box = QGroupBox("System Font")
        fb = QVBoxLayout(font_box)
        self._font_combo = QFontComboBox()
        self._font_combo.currentFontChanged.connect(self._font_changed)
        fb.addWidget(self._font_combo)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._font_size = QSlider(Qt.Horizontal)
        self._font_size.setRange(8, 16)
        self._font_size.setValue(11)
        size_row.addWidget(self._font_size)
        self._font_size_label = QLabel("11")
        size_row.addWidget(self._font_size_label)
        fb.addLayout(size_row)
        rl.addWidget(font_box)

        # Icon theme
        icon_box = QGroupBox("Icon Theme")
        ib = QVBoxLayout(icon_box)
        self._icon_combo = QComboBox()
        self._icon_combo.addItems(["Papirus-Dark", "Adwaita-dark", "breeze-dark", "Faenza-Dark", "System Default"])
        ib.addWidget(self._icon_combo)
        rl.addWidget(icon_box)

        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([260, 620])

        # Buttons
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply Theme")
        apply_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        apply_btn.clicked.connect(self._apply_theme)
        btn_row.addWidget(apply_btn)

        reset_btn = QPushButton("Reset to Cyberpunk Cyan")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _load_current(self):
        if os.path.exists(THEME_FILE):
            try:
                with open(THEME_FILE) as f:
                    data = json.load(f)
                name = data.get("name", "Cyberpunk Cyan")
                if name in THEMES:
                    self._current_theme = name
            except Exception:
                pass
        idx = list(THEMES.keys()).index(self._current_theme)
        self._theme_list.setCurrentRow(idx)

    def _on_theme_selected(self, name):
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
            f"background-color: {theme['bg']}; border: 2px solid {theme['primary']};"
        )

        # Live preview via layout children
        inner = QVBoxLayout(self._preview_frame)
        while inner.count():
            w = inner.takeAt(0).widget()
            if w:
                w.deleteLater()

        btn = QPushButton("Button")
        edit = QLineEdit("Text input")
        lbl = QLabel("Label text")
        for w in (btn, edit, lbl):
            inner.addWidget(w)

    def _font_changed(self, font):
        self._font_size_label.setText(str(self._font_size.value()))

    def _apply_theme(self):
        theme = THEMES[self._current_theme]
        font = self._font_combo.currentFont().family()
        font_size = self._font_size.value()
        icon_theme = self._icon_combo.currentText()

        # Save theme config
        os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
        config = {
            "name": self._current_theme,
            **theme,
            "font": font,
            "font_size": font_size,
            "icon_theme": icon_theme,
        }
        try:
            with open(THEME_FILE, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            log_error(f"Theme save failed: {e}")

        # Write QSS file
        try:
            qss = build_qss(theme)
            with open(QSS_FILE, "w") as f:
                f.write(qss)
        except Exception as e:
            log_error(f"QSS write failed: {e}")

        # Apply GTK theme hint via gsettings
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme",
                        "'Adwaita-dark'"], capture_output=True)
        if icon_theme != "System Default":
            subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme",
                            f"'{icon_theme}'"], capture_output=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "font-name",
                        f"'{font} {font_size}'"], capture_output=True)

        self._status.setText(f"Theme applied: {self._current_theme}")
        log_info(f"Theme applied: {self._current_theme} font={font} size={font_size}")

    def _reset(self):
        self._current_theme = "Cyberpunk Cyan"
        self._theme_list.setCurrentRow(0)
        self._font_size.setValue(11)
        self._apply_theme()


def main():
    app = QApplication(sys.argv)
    win = ThemeManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()