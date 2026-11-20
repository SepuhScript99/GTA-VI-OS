#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Font Manager
Font viewer and installer: preview system fonts, install TTF/OTF files, and rebuild font cache.
"""

import sys
import os
import subprocess
import shutil

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit, QFileDialog, QMessageBox,
    QSpinBox, QSplitter, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QFontDatabase, QFontMetrics

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 640
USER_FONT_DIR = os.path.expanduser("~/.local/share/fonts")

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""

PREVIEW_TEXT = "The quick brown fox jumps over the lazy dog\nABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789"


class FontLoader(QThread):
    done = pyqtSignal(list)

    def run(self):
        db = QFontDatabase()
        families = sorted(db.families())
        self.done.emit(families)


class FontManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Font Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._families = []
        self._init_ui()
        self._load_fonts()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Font Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: font list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter fonts...")
        self._search.textChanged.connect(self._filter_fonts)
        search_row.addWidget(self._search)
        ll.addLayout(search_row)

        self._font_list = QListWidget()
        self._font_list.currentTextChanged.connect(self._preview_font)
        ll.addWidget(self._font_list)

        self._count_label = QLabel("Loading...")
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        ll.addWidget(self._count_label)
        splitter.addWidget(left)

        # Right: preview + actions
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        preview_box = QGroupBox("Preview")
        pl = QVBoxLayout(preview_box)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(8, 96)
        self._size_spin.setValue(18)
        self._size_spin.valueChanged.connect(self._update_preview)
        size_row.addWidget(self._size_spin)
        size_row.addStretch()
        pl.addLayout(size_row)

        self._preview_label = QLabel(PREVIEW_TEXT)
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(Qt.AlignTop)
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setStyleSheet("border: 1px solid #333; padding: 8px; background: #0d0d0d; color: #ffffff;")
        pl.addWidget(self._preview_label)

        self._font_info = QLabel("")
        self._font_info.setStyleSheet("color: #888; font-size: 11px;")
        pl.addWidget(self._font_info)
        rl.addWidget(preview_box)

        action_box = QGroupBox("Actions")
        al = QHBoxLayout(action_box)

        install_btn = QPushButton("Install Font File")
        install_btn.clicked.connect(self._install_font)
        al.addWidget(install_btn)

        open_dir_btn = QPushButton("Open Font Folder")
        open_dir_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", USER_FONT_DIR]))
        al.addWidget(open_dir_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_fonts)
        al.addWidget(refresh_btn)
        rl.addWidget(action_box)

        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([300, 580])

    def _load_fonts(self):
        self._font_list.clear()
        self._count_label.setText("Loading fonts...")
        w = FontLoader()
        w.done.connect(self._on_fonts_loaded)
        w.start()
        self._loader = w

    def _on_fonts_loaded(self, families):
        self._families = families
        self._filter_fonts()
        self._count_label.setText(f"{len(families)} font(s) installed")

    def _filter_fonts(self):
        search = self._search.text().lower()
        self._font_list.clear()
        for f in self._families:
            if search and search not in f.lower():
                continue
            self._font_list.addItem(f)

    def _preview_font(self, family):
        if not family:
            return
        self._update_preview()
        db = QFontDatabase()
        styles = db.styles(family)
        self._font_info.setText(f"Styles: {', '.join(styles)}")

    def _update_preview(self):
        family = self._font_list.currentItem()
        if not family:
            return
        size = self._size_spin.value()
        font = QFont(family.text(), size)
        self._preview_label.setFont(font)
        self._preview_label.setText(PREVIEW_TEXT)

    def _install_font(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Font File(s)", os.path.expanduser("~"),
            "Font files (*.ttf *.otf *.woff *.woff2 *.ttc);;All files (*)"
        )
        if not paths:
            return
        os.makedirs(USER_FONT_DIR, exist_ok=True)
        installed = []
        for path in paths:
            dest = os.path.join(USER_FONT_DIR, os.path.basename(path))
            try:
                shutil.copy2(path, dest)
                installed.append(os.path.basename(path))
                log_info(f"Font installed: {dest}")
            except Exception as e:
                log_error(f"Font install failed {path}: {e}")
        if installed:
            subprocess.run(["fc-cache", "-f", USER_FONT_DIR], capture_output=True)
            QMessageBox.information(self, "Installed", f"Installed {len(installed)} font(s):\n" + "\n".join(installed))
            self._load_fonts()


def main():
    app = QApplication(sys.argv)
    win = FontManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
