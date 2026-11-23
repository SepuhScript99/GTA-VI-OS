#!/usr/bin/env python3
"""Vice OS — PDF Viewer. Page navigation, zoom, rendered via poppler (pdftoppm)."""

import glob
import os
import shutil
import subprocess
import sys
import tempfile

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720


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

    def __init__(self, pdf_path, page, dpi, parent=None):
        super().__init__(parent)
        self._pdf = pdf_path
        self._page = page
        self._dpi = dpi
        self._tmp = None
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        if not shutil.which("pdftoppm"):
            if not self._cancelled:
                self.done.emit(False, "pdftoppm not found. Install: apt install poppler-utils")
            return
        try:
            self._tmp = tempfile.mkdtemp(prefix="vice_pdf_")
            out_prefix = os.path.join(self._tmp, "page")
            self._proc = subprocess.Popen(
                [
                    "pdftoppm", "-png", "-f", str(self._page), "-l", str(self._page),
                    "-r", str(self._dpi), self._pdf, out_prefix,
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            _, stderr = self._proc.communicate(timeout=30)
            if self._cancelled:
                return
            if self._proc.returncode != 0:
                self.done.emit(False, f"pdftoppm error: {(stderr or '')[:200]}")
                return
            pngs = sorted(glob.glob(out_prefix + "*.png"))
            if pngs:
                self.done.emit(True, pngs[0])
            else:
                self.done.emit(False, "No page rendered")
        except Exception as e:
            if not self._cancelled:
                self.done.emit(False, str(e))

    def cleanup(self):
        if self._tmp and os.path.isdir(self._tmp):
            shutil.rmtree(self._tmp, ignore_errors=True)


class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — PDF Viewer")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 560)
        vt.apply_app_theme(self)
        self._pdf = None
        self._pages = 0
        self._page = 1
        self._dpi = 120
        self._worker = None
        self._last_png = None
        self._rerender_pending = False
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "PDF Viewer",
            "Inspect multi-page PDF documents rendered via Poppler (pdftoppm)",
            icon_name="application-pdf",
            badge_text="PDF",
            badge_variant="gold",
            parent=self,
        ))

        toolbar = QHBoxLayout()

        open_btn = vt.make_button("Open PDF", "primary", parent=self)
        open_btn.clicked.connect(self._open_pdf)
        toolbar.addWidget(open_btn)

        toolbar.addStretch()

        prev_btn = vt.make_button("Prev", "secondary", parent=self)
        prev_btn.clicked.connect(self._prev_page)
        toolbar.addWidget(prev_btn)

        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 1)
        self._page_spin.valueChanged.connect(self._goto_page)
        toolbar.addWidget(self._page_spin)

        self._total_label = QLabel("/ 0")
        toolbar.addWidget(self._total_label)

        next_btn = vt.make_button("Next", "secondary", parent=self)
        next_btn.clicked.connect(self._next_page)
        toolbar.addWidget(next_btn)

        toolbar.addStretch()

        zoom_out_btn = vt.make_button("Zoom -", "secondary", parent=self)
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)
        zoom_in_btn = vt.make_button("Zoom +", "secondary", parent=self)
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)

        self._zoom_label = QLabel("120 DPI")
        self._zoom_label.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        toolbar.addWidget(self._zoom_label)
        root.addLayout(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._page_label = QLabel("Open a PDF to begin")
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setStyleSheet(f"color: {vt.COLORS['text_muted']}; font-size: 16px;")
        self._page_label.setMinimumSize(720, 480)
        self._scroll.setWidget(self._page_label)
        root.addWidget(self._scroll, 1)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
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
            QMessageBox.warning(
                self, "Invalid PDF",
                "Could not read page count.\nInstall poppler-utils: apt install poppler-utils",
            )
            return
        self._page_spin.setRange(1, self._pages)
        self._page_spin.setValue(1)
        self._total_label.setText(f"/ {self._pages}")
        self._page = 1
        self._render_page()
        self._status.setText(f"{os.path.basename(path)} — {self._pages} page(s)")

    def _prev_page(self):
        if self._page > 1:
            self._page_spin.setValue(self._page - 1)

    def _next_page(self):
        if self._page < self._pages:
            self._page_spin.setValue(self._page + 1)

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
        if self._worker and self._worker.isRunning():
            self._rerender_pending = True
            return
        self._rerender_pending = False
        self._page_label.setText(f"Rendering page {self._page}...")
        self._worker = RenderWorker(self._pdf, self._page, self._dpi, parent=self)
        self._worker.done.connect(self._on_rendered)
        self._worker.start()

    def _on_rendered(self, ok, result):
        pix = QPixmap(result) if ok and os.path.exists(result) else QPixmap()
        if self._worker:
            self._worker.cleanup()
        if not ok or pix.isNull():
            self._page_label.setPixmap(QPixmap())
            self._page_label.setText("Render failed")
            self._status.setText(f"Error: {result}")
            log_error(f"PDF render failed: {result}")
        else:
            self._last_png = result
            self._page_label.setPixmap(pix)
            self._page_label.adjustSize()
            self._status.setText(f"Page {self._page}/{self._pages} @ {self._dpi} DPI")

        if self._rerender_pending:
            self._rerender_pending = False
            self._render_page()

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2500)
            self._worker.cleanup()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = PDFViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
