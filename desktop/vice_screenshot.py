#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Screenshot Utility
Full screen, active window, and custom region screen capture with clipboard copying and saving.
"""

import sys
import os
import subprocess
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSpinBox, QComboBox, QGroupBox, QLineEdit, QFileDialog, QMessageBox,
    QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 560
WINDOW_HEIGHT = 480
SAVE_DIR = os.path.expanduser("~/Pictures/Screenshots")

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px 16px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 13px; height: 13px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QLabel { color: #00ffff; }
"""


class CaptureWorker(QThread):
    done = pyqtSignal(str, bool)

    def __init__(self, mode, delay, path):
        super().__init__()
        self.mode = mode
        self.delay = delay
        self.path = path

    def run(self):
        import time
        time.sleep(self.delay)
        try:
            if self.mode == "Full Screen":
                cmd = ["scrot", self.path]
            elif self.mode == "Active Window":
                cmd = ["scrot", "-u", self.path]
            elif self.mode == "Select Region":
                cmd = ["scrot", "-s", self.path]
            else:
                cmd = ["scrot", self.path]

            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode != 0:
                # fallback to import (ImageMagick)
                if self.mode == "Select Region":
                    r2 = subprocess.run(["import", self.path], capture_output=True, timeout=30)
                else:
                    r2 = subprocess.run(["import", "-window", "root", self.path], capture_output=True, timeout=30)
                self.done.emit(self.path, r2.returncode == 0)
            else:
                self.done.emit(self.path, True)
        except Exception as e:
            self.done.emit(str(e), False)


class ScreenshotTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Screenshot Tool")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._last_path = None
        os.makedirs(SAVE_DIR, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Screenshot Tool")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Mode
        mode_box = QGroupBox("Capture Mode")
        ml = QHBoxLayout(mode_box)
        ml.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Full Screen", "Active Window", "Select Region"])
        ml.addWidget(self._mode_combo)
        ml.addWidget(QLabel("Delay (s):"))
        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 10)
        self._delay_spin.setValue(0)
        ml.addWidget(self._delay_spin)
        root.addWidget(mode_box)

        # Save options
        save_box = QGroupBox("Save Options")
        sl = QVBoxLayout(save_box)
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Save to:"))
        self._dir_edit = QLineEdit(SAVE_DIR)
        dir_row.addWidget(self._dir_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        sl.addLayout(dir_row)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["png", "jpg", "bmp"])
        fmt_row.addWidget(self._fmt_combo)
        self._copy_cb = QCheckBox("Copy to clipboard after capture")
        fmt_row.addWidget(self._copy_cb)
        sl.addLayout(fmt_row)
        root.addWidget(save_box)

        # Preview
        self._preview = QLabel("No screenshot taken yet")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setFixedHeight(140)
        self._preview.setStyleSheet("border: 1px solid #333; background: #0d0d0d; color: #444;")
        root.addWidget(self._preview)

        # Buttons
        btn_row = QHBoxLayout()
        self._capture_btn = QPushButton("Capture")
        self._capture_btn.setFont(QFont("monospace", 11, QFont.Bold))
        self._capture_btn.clicked.connect(self._capture)
        btn_row.addWidget(self._capture_btn)

        self._open_btn = QPushButton("Open in Viewer")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._open_last)
        btn_row.addWidget(self._open_btn)

        self._open_dir_btn = QPushButton("Open Folder")
        self._open_dir_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", self._dir_edit.text()]))
        btn_row.addWidget(self._open_dir_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Save Screenshots To", self._dir_edit.text())
        if path:
            self._dir_edit.setText(path)

    def _capture(self):
        mode = self._mode_combo.currentText()
        delay = self._delay_spin.value()
        fmt = self._fmt_combo.currentText()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._dir_edit.text(), f"vice_shot_{ts}.{fmt}")

        self._capture_btn.setEnabled(False)
        self._status.setText(f"Capturing in {delay}s..." if delay else "Capturing...")

        if mode == "Select Region":
            self.hide()
            QTimer.singleShot(200, lambda: self._do_capture(mode, delay, path))
        else:
            self._do_capture(mode, delay, path)

    def _do_capture(self, mode, delay, path):
        self._worker = CaptureWorker(mode, delay, path)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, path_or_err, ok):
        self.show()
        if ok:
            self._last_path = path_or_err
            self._status.setText(f"Saved: {os.path.basename(path_or_err)}")
            self._open_btn.setEnabled(True)
            pix = QPixmap(path_or_err)
            if not pix.isNull():
                self._preview.setPixmap(
                    pix.scaled(self._preview.width() - 4, self._preview.height() - 4,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            if self._copy_cb.isChecked():
                QApplication.clipboard().setPixmap(pix)
            log_info(f"Screenshot saved: {path_or_err}")
        else:
            self._status.setText(f"Failed: {path_or_err}")
            log_error(f"Screenshot failed: {path_or_err}")
        self._capture_btn.setEnabled(True)

    def _open_last(self):
        if self._last_path:
            subprocess.Popen(["xdg-open", self._last_path])


def main():
    app = QApplication(sys.argv)
    win = ScreenshotTool()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
