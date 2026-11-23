#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Screenshot Utility
Full screen, active window, and custom region screen capture with clipboard copying and saving.
"""

import datetime
import os
import shutil
import subprocess
import sys
import time

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 560
WINDOW_HEIGHT = 500
SAVE_DIR = os.path.expanduser("~/Pictures/Screenshots")


class CaptureWorker(QThread):
    done = pyqtSignal(str, bool)

    def __init__(self, mode, delay, path, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.delay = delay
        self.path = path
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        remaining = float(self.delay)
        while remaining > 0 and not self._cancelled:
            step = min(0.1, remaining)
            time.sleep(step)
            remaining -= step
        if self._cancelled:
            return
        try:
            if shutil.which("scrot"):
                if self.mode == "Active Window":
                    cmd = ["scrot", "-u", self.path]
                elif self.mode == "Select Region":
                    cmd = ["scrot", "-s", self.path]
                else:
                    cmd = ["scrot", self.path]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and os.path.isfile(self.path):
                    self.done.emit(self.path, True)
                    return

            if shutil.which("gnome-screenshot"):
                if self.mode == "Active Window":
                    cmd = ["gnome-screenshot", "-w", "-f", self.path]
                elif self.mode == "Select Region":
                    cmd = ["gnome-screenshot", "-a", "-f", self.path]
                else:
                    cmd = ["gnome-screenshot", "-f", self.path]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and os.path.isfile(self.path):
                    self.done.emit(self.path, True)
                    return

            if shutil.which("import"):
                if self.mode == "Select Region":
                    cmd = ["import", self.path]
                else:
                    cmd = ["import", "-window", "root", self.path]
                r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                self.done.emit(self.path, r2.returncode == 0 and os.path.isfile(self.path))
                return

            self.done.emit("No screenshot tool found (scrot, gnome-screenshot, or import)", False)
        except Exception as e:
            self.done.emit(str(e), False)


class ScreenshotTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Screenshot Tool")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(480, 440)
        vt.apply_app_theme(self)
        self._worker = None
        self._last_path = None
        os.makedirs(SAVE_DIR, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Screenshot Tool",
            "Full screen, active window and region capture to file & clipboard",
            icon_name="camera-photo",
            badge_text="CAPTURE",
            badge_variant="aqua",
            parent=self,
        ))

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

        save_box = QGroupBox("Save Options")
        sl = QVBoxLayout(save_box)
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Save to:"))
        self._dir_edit = QLineEdit(SAVE_DIR)
        dir_row.addWidget(self._dir_edit)
        browse_btn = vt.make_button("Browse", "secondary", parent=self)
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

        self._preview = QLabel("No screenshot taken yet")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setFixedHeight(140)
        self._preview.setStyleSheet(
            f"border: 1px solid {vt.COLORS['border']}; background: {vt.COLORS['bg_surface']}; "
            f"color: {vt.COLORS['text_muted']}; border-radius: 8px;"
        )
        root.addWidget(self._preview)

        btn_row = QHBoxLayout()
        self._capture_btn = vt.make_button("Capture", "primary", parent=self)
        self._capture_btn.clicked.connect(self._capture)
        btn_row.addWidget(self._capture_btn)

        self._open_btn = vt.make_button("Open in Viewer", "secondary", parent=self)
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._open_last)
        btn_row.addWidget(self._open_btn)

        self._open_dir_btn = vt.make_button("Open Folder", "secondary", parent=self)
        self._open_dir_btn.clicked.connect(
            lambda: subprocess.Popen(["xdg-open", self._dir_edit.text()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        )
        btn_row.addWidget(self._open_dir_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Save Screenshots To", self._dir_edit.text())
        if path:
            self._dir_edit.setText(path)

    def _capture(self):
        if self._worker is not None and self._worker.isRunning():
            return
        mode = self._mode_combo.currentText()
        delay = self._delay_spin.value()
        fmt = self._fmt_combo.currentText()
        save_dir = self._dir_edit.text().strip() or SAVE_DIR
        os.makedirs(save_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(save_dir, f"vice_shot_{ts}.{fmt}")

        self._capture_btn.setEnabled(False)
        self._status.setText(f"Capturing in {delay}s..." if delay else "Capturing...")

        if mode == "Select Region":
            self.hide()
            QTimer.singleShot(200, lambda: self._do_capture(mode, delay, path))
        else:
            self._do_capture(mode, delay, path)

    def _do_capture(self, mode, delay, path):
        self._worker = CaptureWorker(mode, delay, path, parent=self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, path_or_err, ok):
        self.show()
        if ok and os.path.exists(path_or_err):
            self._last_path = path_or_err
            self._status.setText(f"Saved: {os.path.basename(path_or_err)}")
            self._open_btn.setEnabled(True)
            pix = QPixmap(path_or_err)
            if not pix.isNull():
                self._preview.setPixmap(
                    pix.scaled(
                        max(1, self._preview.width() - 4),
                        max(1, self._preview.height() - 4),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            if self._copy_cb.isChecked() and not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
            log_info(f"Screenshot saved: {path_or_err}")
        else:
            self._status.setText(f"Failed: {path_or_err}")
            log_error(f"Screenshot failed: {path_or_err}")
        self._capture_btn.setEnabled(True)

    def _open_last(self):
        if self._last_path and os.path.exists(self._last_path):
            subprocess.Popen(["xdg-open", self._last_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = ScreenshotTool()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
