#!/usr/bin/env python3
"""Vice OS — Wallpaper Picker. Browse, preview, and set wallpapers (X11 + Wayland)."""

import sys
import os
import subprocess
import glob

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QGridLayout, QFrame, QFileDialog, QLineEdit,
    QMessageBox, QComboBox, QCheckBox, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QColor

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QRadioButton { color: #00ffff; }
QLabel { color: #00ffff; }
QScrollArea { border: 1px solid #1a4a4a; background: #0d0d0d; }
QScrollBar:vertical { background: #0a0a0a; width: 8px; }
QScrollBar::handle:vertical { background: #00ffff; border-radius: 4px; min-height: 30px; }
"""

WALLPAPER_DIRS = [
    "/usr/share/backgrounds",
    os.path.expanduser("~/Pictures/Wallpapers"),
    os.path.expanduser("~/Pictures"),
]
IMAGE_EXTS = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]
THUMB_W, THUMB_H = 220, 124


def detect_session():
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "none"


def apply_wallpaper(path, mode, session):
    """Apply wallpaper via swaybg (Wayland) or feh (X11)."""
    if session == "wayland":
        subprocess.run(["pkill", "swaybg"], capture_output=True)
        fill_mode = {"fill": "fill", "stretch": "stretch", "fit": "fit",
                     "center": "center", "tile": "tile"}[mode]
        return subprocess.Popen(["swaybg", "-i", path, "-m", fill_mode],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:  # x11
        bg_styles = {"fill": "--bg-fill", "stretch": "--bg-scale", "fit": "--bg-max",
                     "center": "--bg-center", "tile": "--bg-tile"}
        style = bg_styles.get(mode, "--bg-fill")
        for tool in ("feh", "nitrogen"):
            if subprocess.run(["which", tool], capture_output=True).returncode == 0:
                if tool == "feh":
                    return subprocess.Popen([tool, style, path],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None


class ThumbLoader(QThread):
    """Loads a thumbnail in the background."""
    loaded = pyqtSignal(int, QPixmap)

    def __init__(self, row, path):
        super().__init__()
        self._row = row
        self._path = path

    def run(self):
        pix = QPixmap(self._path)
        if not pix.isNull():
            thumb = pix.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
            self.loaded.emit(self._row, thumb)


class WallpaperCard(QFrame):
    """Clickable wallpaper preview card."""

    def __init__(self, path, row, on_click):
        super().__init__()
        self.path = path
        self.row = row
        self.setFixedSize(THUMB_W + 16, THUMB_H + 52)
        self.setStyleSheet(
            "QFrame { background: #0d0d0d; border: 1px solid #1a4a4a; border-radius: 4px; }"
            "QFrame:hover { border: 1px solid #00ffff; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        self._preview = QLabel()
        self._preview.setFixedSize(THUMB_W, THUMB_H)
        self._preview.setStyleSheet("background: #111; border: none;")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setText("...")
        layout.addWidget(self._preview)

        name = QLabel(os.path.basename(path))
        name.setStyleSheet("color: #aaffff; font-size: 10px; border: none;")
        name.setAlignment(Qt.AlignCenter)
        if len(name.text()) > 30:
            name.setText(name.text()[:28] + "…")
        layout.addWidget(name)

        self.setCursor(Qt.PointingHandCursor)
        self.mouseReleaseEvent = lambda e: on_click(self)

    def set_thumbnail(self, pix):
        self._preview.setPixmap(pix.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation))


class WallpaperPicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Wallpaper Picker")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._cards = []
        self._loaders = []
        self._session = detect_session()
        self._init_ui()
        self._load_wallpapers()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Wallpaper Picker")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Controls row
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Folder:"))
        self._dir_edit = QLineEdit(WALLPAPER_DIRS[0])
        ctrl.addWidget(self._dir_edit, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        ctrl.addWidget(browse_btn)

        reload_btn = QPushButton("↻ Reload")
        reload_btn.clicked.connect(self._load_wallpapers)
        ctrl.addWidget(reload_btn)
        root.addLayout(ctrl)

        # Display mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_group = QButtonGroup(self)
        for i, mode in enumerate(["fill", "stretch", "fit", "center", "tile"]):
            rb = QRadioButton(mode)
            if mode == "fill":
                rb.setChecked(True)
            self._mode_group.addButton(rb, i)
            mode_row.addWidget(rb)
        mode_row.addStretch()

        session_label = QLabel(f"Session: {self._session.upper()}")
        session_label.setStyleSheet("color: #888; font-size: 11px;")
        mode_row.addWidget(session_label)
        root.addLayout(mode_row)

        # Scroll grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(8)
        self._scroll.setWidget(self._grid_widget)
        root.addWidget(self._scroll, 1)

        # Status
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Wallpaper Folder", self._dir_edit.text())
        if path:
            self._dir_edit.setText(path)
            self._load_wallpapers()

    def _load_wallpapers(self):
        # Clear existing
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        self._loaders.clear()

        folder = self._dir_edit.text().strip()
        if not os.path.isdir(folder):
            self._status.setText(f"Folder not found: {folder}")
            return

        images = []
        for ext in IMAGE_EXTS:
            images.extend(glob.glob(os.path.join(folder, ext)))
            images.extend(glob.glob(os.path.join(folder, ext.upper())))
        images = sorted(set(images))

        if not images:
            self._status.setText("No images found in folder")
            return

        cols = 4
        for i, path in enumerate(images[:80]):  # cap at 80
            card = WallpaperCard(path, i, self._on_card_click)
            row, col = divmod(i, cols)
            self._grid.addWidget(card, row, col)
            self._cards.append(card)

            loader = ThumbLoader(i, path)
            loader.loaded.connect(self._on_thumb_loaded)
            loader.start()
            self._loaders.append(loader)

        self._status.setText(f"{len(self._cards)} wallpaper(s)")

    def _on_thumb_loaded(self, row, pix):
        if 0 <= row < len(self._cards):
            self._cards[row].set_thumbnail(pix)

    def _on_card_click(self, card):
        mode = self._mode_group.button(self._mode_group.checkedId()).text()
        proc = apply_wallpaper(card.path, mode, self._session)
        if proc is None:
            self._status.setText("No wallpaper tool found (need feh or swaybg)")
            QMessageBox.warning(self, "Apply Failed",
                                 "No wallpaper tool available.\n"
                                 "X11: install feh\nWayland: install swaybg")
            return
        self._status.setText(f"Applied: {os.path.basename(card.path)} ({mode})")
        log_info(f"Wallpaper applied: {card.path} mode={mode} session={self._session}")


def main():
    app = QApplication(sys.argv)
    win = WallpaperPicker()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()