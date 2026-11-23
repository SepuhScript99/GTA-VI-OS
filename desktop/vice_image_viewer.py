#!/usr/bin/env python3
"""Vice OS — Image Viewer. Browse folder, zoom, rotate, slideshow, thumbnails."""

import glob
import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QTransform
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QSplitter, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700

IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif", "*.webp", "*.xpm", "*.svg")
SLIDE_INTERVAL = 3000


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Image Viewer")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        vt.apply_app_theme(self)
        self._pixmap = None
        self._scale = 1.0
        self._rotation = 0
        self._files = []
        self._index = -1
        self._slide_timer = QTimer(self)
        self._slide_timer.setInterval(SLIDE_INTERVAL)
        self._slide_timer.timeout.connect(self._next_image)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Image Viewer",
            "Browse image folders, zoom, rotate and run slideshows",
            icon_name="image-x-generic",
            badge_text="IMAGES",
            badge_variant="aqua",
            parent=self,
        ))

        toolbar = QHBoxLayout()

        open_btn = vt.make_button("Open Folder", "primary", parent=self)
        open_btn.clicked.connect(self._open_folder)
        toolbar.addWidget(open_btn)

        prev_btn = vt.make_button("Prev", "secondary", parent=self)
        prev_btn.clicked.connect(self._prev_image)
        toolbar.addWidget(prev_btn)

        next_btn = vt.make_button("Next", "secondary", parent=self)
        next_btn.clicked.connect(self._next_image)
        toolbar.addWidget(next_btn)

        zoom_in_btn = vt.make_button("Zoom +", "secondary", parent=self)
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = vt.make_button("Zoom -", "secondary", parent=self)
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)

        fit_btn = vt.make_button("Fit", "secondary", parent=self)
        fit_btn.clicked.connect(self._fit_image)
        toolbar.addWidget(fit_btn)

        actual_btn = vt.make_button("1:1", "secondary", parent=self)
        actual_btn.clicked.connect(self._actual_size)
        toolbar.addWidget(actual_btn)

        rot_btn = vt.make_button("Rotate 90", "secondary", parent=self)
        rot_btn.clicked.connect(self._rotate)
        toolbar.addWidget(rot_btn)

        self._slide_btn = vt.make_button("Slideshow", "secondary", parent=self)
        self._slide_btn.clicked.connect(self._toggle_slideshow)
        toolbar.addWidget(self._slide_btn)

        toolbar.addStretch()
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        self._file_list = QListWidget()
        self._file_list.setFixedWidth(220)
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        splitter.addWidget(self._file_list)

        self._viewer = QLabel()
        self._viewer.setAlignment(Qt.AlignCenter)
        self._viewer.setMinimumSize(500, 420)
        self._viewer.setStyleSheet(
            f"background: {vt.COLORS['bg_surface']}; border: 1px solid {vt.COLORS['border']}; border-radius: 8px;"
        )
        self._viewer.setText("Open a folder to browse images")
        splitter.addWidget(self._viewer)
        splitter.setSizes([220, 860])

        status_row = QHBoxLayout()
        self._status = QLabel("No image loaded")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        status_row.addWidget(self._status)
        status_row.addStretch()
        root.addLayout(status_row)

    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open Image Folder", os.path.expanduser("~"))
        if not path:
            return
        files = []
        for ext in IMAGE_EXTS:
            files.extend(glob.glob(os.path.join(path, ext)))
            files.extend(glob.glob(os.path.join(path, ext.upper())))
        self._files = sorted(set(files))
        self._file_list.clear()
        for f in self._files:
            self._file_list.addItem(QListWidgetItem(os.path.basename(f)))
        self._status.setText(f"{len(self._files)} image(s) in {path}")
        if self._files:
            self._file_list.setCurrentRow(0)

    def _on_file_selected(self, row):
        if row < 0 or row >= len(self._files):
            return
        self._index = row
        self._load_image(self._files[row])

    def _load_image(self, path):
        self._pixmap = QPixmap(path)
        if self._pixmap.isNull():
            self._viewer.setPixmap(QPixmap())
            self._viewer.setText("Cannot load image")
            self._status.setText(f"Failed: {path}")
            return
        self._scale = 1.0
        self._rotation = 0
        self._fit_image()
        try:
            size_kb = os.path.getsize(path) // 1024
        except OSError:
            size_kb = 0
        self._status.setText(
            f"{os.path.basename(path)}  |  {self._pixmap.width()}x{self._pixmap.height()}  |  "
            f"{size_kb} KB  |  {self._index + 1}/{len(self._files)}"
        )

    def _render(self):
        if not self._pixmap or self._pixmap.isNull():
            return
        transform = QTransform().rotate(self._rotation)
        rotated = self._pixmap.transformed(transform, Qt.SmoothTransformation)
        tw = max(1, int(rotated.width() * self._scale))
        th = max(1, int(rotated.height() * self._scale))
        scaled = rotated.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._viewer.setPixmap(scaled)

    def _fit_image(self):
        if not self._pixmap or self._pixmap.isNull():
            return
        vw = max(1, self._viewer.width() - 20)
        vh = max(1, self._viewer.height() - 20)
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw == 0 or ph == 0:
            return
        self._scale = min(vw / pw, vh / ph, 1.0)
        self._render()

    def _actual_size(self):
        self._scale = 1.0
        self._render()

    def _zoom_in(self):
        self._scale = min(self._scale * 1.25, 10.0)
        self._render()

    def _zoom_out(self):
        self._scale = max(self._scale / 1.25, 0.05)
        self._render()

    def _rotate(self):
        self._rotation = (self._rotation + 90) % 360
        self._render()

    def _prev_image(self):
        if not self._files:
            return
        self._index = (self._index - 1) % len(self._files)
        self._file_list.setCurrentRow(self._index)

    def _next_image(self):
        if not self._files:
            return
        self._index = (self._index + 1) % len(self._files)
        self._file_list.setCurrentRow(self._index)

    def _toggle_slideshow(self):
        if self._slide_timer.isActive():
            self._slide_timer.stop()
            self._slide_btn.setText("Slideshow")
            self._status.setText("Slideshow stopped")
        else:
            if not self._files:
                QMessageBox.information(self, "No Images", "Open a folder first.")
                return
            self._slide_timer.start()
            self._slide_btn.setText("Pause Show")
            self._status.setText(f"Slideshow running ({SLIDE_INTERVAL // 1000}s interval)")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()

    def closeEvent(self, event):
        self._slide_timer.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = ImageViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
