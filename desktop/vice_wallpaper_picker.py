#!/usr/bin/env python3
"""Vice OS — Wallpaper Picker. Browse, preview, and set wallpapers (X11 + Wayland)."""

import glob
import os
import shutil
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QRadioButton,
    QScrollArea, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660

WALLPAPER_DIRS = [
    "/usr/share/backgrounds",
    os.path.expanduser("~/Pictures/Wallpapers"),
    os.path.expanduser("~/Pictures"),
]
IMAGE_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp")
THUMB_W, THUMB_H = 220, 124


def detect_session():
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "none"


def apply_wallpaper(path, mode, session):
    """Apply wallpaper via swaybg (Wayland) or feh/nitrogen (X11)."""
    if session == "wayland":
        if not shutil.which("swaybg"):
            return None
        subprocess.run(["pkill", "swaybg"], capture_output=True)
        fill_mode = {
            "fill": "fill", "stretch": "stretch", "fit": "fit",
            "center": "center", "tile": "tile",
        }.get(mode, "fill")
        return subprocess.Popen(
            ["swaybg", "-i", path, "-m", fill_mode],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    bg_styles = {
        "fill": "--bg-fill", "stretch": "--bg-scale", "fit": "--bg-max",
        "center": "--bg-center", "tile": "--bg-tile",
    }
    nitro_styles = {
        "fill": "--set-zoom-fill", "stretch": "--set-scaled",
        "fit": "--set-auto", "center": "--set-centered", "tile": "--set-tiled",
    }
    for tool in ("feh", "nitrogen"):
        if shutil.which(tool):
            args = (
                [tool, bg_styles.get(mode, "--bg-fill"), path]
                if tool == "feh"
                else [tool, nitro_styles.get(mode, "--set-zoom-fill"), path]
            )
            return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


class ThumbBatchLoader(QThread):
    """Loads thumbnail previews sequentially in a single background worker."""

    loaded = pyqtSignal(int, QImage)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        for row, path in self._items:
            if self._cancelled:
                return
            img = QImage(path)
            if not img.isNull() and not self._cancelled:
                thumb = img.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.loaded.emit(row, thumb)


class WallpaperCard(QFrame):
    """Clickable wallpaper preview card."""

    def __init__(self, path, row, on_click):
        super().__init__()
        self.path = path
        self.row = row
        self.setFixedSize(THUMB_W + 16, THUMB_H + 52)
        self.setStyleSheet(
            f"QFrame {{ background: {vt.COLORS['bg_surface']}; border: 1px solid {vt.COLORS['border']}; border-radius: 8px; }}"
            f"QFrame:hover {{ border: 1px solid {vt.COLORS['accent_coral']}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        self._preview = QLabel()
        self._preview.setFixedSize(THUMB_W, THUMB_H)
        self._preview.setStyleSheet(f"background: {vt.COLORS['bg_canvas']}; border: none;")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setText("...")
        layout.addWidget(self._preview)

        raw_name = os.path.basename(path)
        display = raw_name[:28] + "…" if len(raw_name) > 30 else raw_name
        name = QLabel(display)
        name.setStyleSheet(f"color: {vt.COLORS['text_primary']}; font-size: 10px; border: none;")
        name.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)

        self.setCursor(Qt.PointingHandCursor)
        self.mouseReleaseEvent = lambda _e: on_click(self)

    def set_thumbnail(self, pix):
        self._preview.setPixmap(
            pix.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )


class WallpaperPicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Wallpaper Picker")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        vt.apply_app_theme(self)
        self._cards = []
        self._loader = None
        self._session = detect_session()
        self._init_ui()
        self._load_wallpapers()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Wallpaper Picker",
            "Browse backgrounds, choose scaling mode and apply immediately",
            icon_name="preferences-desktop-wallpaper",
            badge_text=self._session.upper(),
            badge_variant="aqua",
            parent=self,
        ))

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Folder:"))
        self._dir_edit = QLineEdit(WALLPAPER_DIRS[0])
        ctrl.addWidget(self._dir_edit, 1)

        browse_btn = vt.make_button("Browse", "secondary", parent=self)
        browse_btn.clicked.connect(self._browse)
        ctrl.addWidget(browse_btn)

        reload_btn = vt.make_button("Reload", "primary", parent=self)
        reload_btn.clicked.connect(self._load_wallpapers)
        ctrl.addWidget(reload_btn)
        root.addLayout(ctrl)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_group = QButtonGroup(self)
        for i, mode in enumerate(("fill", "stretch", "fit", "center", "tile")):
            rb = QRadioButton(mode)
            if mode == "fill":
                rb.setChecked(True)
            self._mode_group.addButton(rb, i)
            mode_row.addWidget(rb)
        mode_row.addStretch()

        session_label = QLabel(f"Session: {self._session.upper()}")
        session_label.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        mode_row.addWidget(session_label)
        root.addLayout(mode_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(8)
        self._scroll.setWidget(self._grid_widget)
        root.addWidget(self._scroll, 1)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _stop_loader(self):
        if self._loader is not None and self._loader.isRunning():
            self._loader.stop()
            self._loader.wait(2000)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Wallpaper Folder", self._dir_edit.text())
        if path:
            self._dir_edit.setText(path)
            self._load_wallpapers()

    def _load_wallpapers(self):
        self._stop_loader()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        folder = self._dir_edit.text().strip()
        if not os.path.isdir(folder):
            self._status.setText(f"Folder not found: {folder}")
            return

        images = []
        for ext in IMAGE_EXTS:
            images.extend(glob.glob(os.path.join(folder, ext)))
            images.extend(glob.glob(os.path.join(folder, ext.upper())))
        images = sorted(set(images))[:80]

        if not images:
            self._status.setText("No images found in folder")
            return

        cols = 4
        items = []
        for i, path in enumerate(images):
            card = WallpaperCard(path, i, self._on_card_click)
            row, col = divmod(i, cols)
            self._grid.addWidget(card, row, col)
            self._cards.append(card)
            items.append((i, path))

        self._loader = ThumbBatchLoader(items, parent=self)
        self._loader.loaded.connect(self._on_thumb_loaded)
        self._loader.start()

        self._status.setText(f"{len(self._cards)} wallpaper(s)")

    def _on_thumb_loaded(self, row, img):
        if 0 <= row < len(self._cards):
            self._cards[row].set_thumbnail(QPixmap.fromImage(img))

    def _on_card_click(self, card):
        checked_btn = self._mode_group.checkedButton()
        mode = checked_btn.text() if checked_btn else "fill"
        proc = apply_wallpaper(card.path, mode, self._session)
        if proc is None:
            self._status.setText("No wallpaper tool found (need feh or swaybg)")
            QMessageBox.warning(
                self, "Apply Failed",
                "No wallpaper tool available.\nX11: install feh\nWayland: install swaybg",
            )
            return
        self._status.setText(f"Applied: {os.path.basename(card.path)} ({mode})")
        log_info(f"Wallpaper applied: {card.path} mode={mode} session={self._session}")

    def closeEvent(self, event):
        self._stop_loader()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = WallpaperPicker()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
