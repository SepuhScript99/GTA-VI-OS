#!/usr/bin/env python3
"""Vice OS — PDF Viewer. Page navigation, zoom, rendered via poppler (pdftoppm)."""

import sys
import os
import subprocess
import tempfile
import glob

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSpinBox, QScrollArea, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QScrollArea { background: #0d0d0d; border: 1px solid #1a4a4a; }
QLabel { color: #00ffff; }
"""


def get_page_count(pdf_path):
    """Get PDF page count via pdfinfo."""
    try:
        r = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception as e:
        log_error(f"pdfinfo failed: {e}")
    return 0


class RenderWorker(QThread):
    """Renders a single PDF page to PNG via pdftoppm."""
    done = pyqtSignal(bool, str)

    def __init__(self, pdf_path, page, dpi):
        super().__init__()
        self._pdf = pdf_path
        self._page = page
        self._dpi = dpi
        self._tmp = None

    def run(self):
        if not shutil_which("pdftoppm"):
            self.done.emit(False, "pdftoppm not found. Install: apt install poppler-utils")
            return
        try:
            self._tmp = tempfile.mkdtemp(prefix="vice_pdf_")
            out_prefix = os.path.join(self._tmp, "page")
            subprocess.run(
                ["pdftoppm", "-png", "-f", str(self._page), "-l", str(self._page),
                 "-r", str(self._dpi), self._pdf, out_prefix],
                capture_output=True, timeout=30, check=True
            )
            pngs = sorted(glob.glob(out_prefix + "*.png"))
            if pngs:
                self.done.emit(True, pngs[0])
            else:
                self.done.emit(False, "No page rendered")
        except subprocess.CalledProcessError as e:
            self.done.emit(False, f"pdftoppm error: {e.stderr.decode()[:200] if e.stderr else e}")
        except Exception as e:
            self.done.emit(False, str(e))

    def cleanup(self):
        if self._tmp and os.path.isdir(self._tmp):
            import shutil
            shutil.rmtree(self._tmp, ignore_errors=True)


def shutil_which(cmd):
    from shutil import which
    return which(cmd)


class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — PDF Viewer")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._pdf = None
        self._pages = 0
        self._page = 1
        self._dpi = 120
        self._worker = None
        self._last_png = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()

        open_btn = QPushButton("Open PDF")
        open_btn.clicked.connect(self._open_pdf)
        toolbar.addWidget(open_btn)

        toolbar.addStretch()

        prev_btn = QPushButton("◀ Prev")
        prev_btn.clicked.connect(self._prev_page)
        toolbar.addWidget(prev_btn)

        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 1)
        self._page_spin.valueChanged.connect(self._goto_page)
        toolbar.addWidget(self._page_spin)

        self._total_label = QLabel("/ 0")
        toolbar.addWidget(self._total_label)

        next_btn = QPushButton("Next ▶")
        next_btn.clicked.connect(self._next_page)
        toolbar.addWidget(next_btn)

        toolbar.addStretch()

        zoom_out_btn = QPushButton("Zoom −")
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)
        zoom_in_btn = QPushButton("Zoom +")
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)

        self._zoom_label = QLabel("120 DPI")
        self._zoom_label.setStyleSheet("color: #888; font-size: 11px;")
        toolbar.addWidget(self._zoom_label)

        root.addLayout(toolbar)

        # Viewer area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._page_label = QLabel("Open a PDF to begin")
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setStyleSheet("color: #444; font-size: 16px;")
        self._page_label.setMinimumSize(800, 560)
        self._scroll.setWidget(self._page_label)
        root.addWidget(self._scroll, 1)

        # Status
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", os.path.expanduser("~"), "PDF (*.pdf);;All files (*)"
        )
        if not path:
            return
        self._pdf = path
        self._pages = get_page_count(path)
        if self._pages == 0:
            QMessageBox.warning(self, "Invalid PDF",
                                "Could not read page count.\nInstall poppler-utils: apt install poppler-utils")
            return
        self._page_spin.setRange(1, self._pages)
        self._page_spin.setValue(1)
        self._total_label.setText(f"/ {self._pages}")
        self._page = 1
        self._render_page()
        self._status.setText(f"{os.path.basename(path)} — {self._pages} page(s)")

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self._page_spin.setValue(self._page)

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self._page_spin.setValue(self._page)

    def _goto_page(self, page):
        if not self._pdf or page == self._page:
            return
        self._page = page
        self._render_page()

    def _zoom_in(self):
        self._dpi = min(int(self._dpi * 1.25), 400)
        self._zoom_label.setText(f"{self._dpi} DPI")
        self._render_page()

    def _zoom_out(self):
        self._dpi = max(int(self._dpi / 1.25), 60)
        self._zoom_label.setText(f"{self._dpi} DPI")
        self._render_page()

    def _render_page(self):
        if not self._pdf:
            return
        self._page_label.setText(f"Rendering page {self._page}...")
        if self._worker and self._worker.isRunning():
            return
        self._worker = RenderWorker(self._pdf, self._page, self._dpi)
        self._worker.done.connect(self._on_rendered)
        self._worker.start()

    def _on_rendered(self, ok, result):
        if self._worker:
            self._worker.cleanup()
        if not ok:
            self._page_label.setText("Render failed")
            self._status.setText(f"Error: {result}")
            log_error(f"PDF render failed: {result}")
            return
        # Clean up previous temp file
        if self._last_png and os.path.exists(self._last_png):
            try:
                os.remove(self._last_png)
            except OSError:
                pass
        self._last_png = result
        pix = QPixmap(result)
        self._page_label.setPixmap(pix)
        self._page_label.adjustSize()
        self._status.setText(f"Page {self._page}/{self._pages} @ {self._dpi} DPI")

    def closeEvent(self, event):
        if self._last_png and os.path.exists(self._last_png):
            try:
                tmp_dir = os.path.dirname(self._last_png)
                os.remove(self._last_png)
                os.rmdir(tmp_dir)
            except OSError:
                pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = PDFViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()