#!/usr/bin/env python3
"""Vice OS — Checksum Verifier. Compute/verify MD5, SHA1, SHA256, SHA512 for any file."""

import sys
import os
import hashlib
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QComboBox, QGroupBox, QPlainTextEdit, QFileDialog,
    QMessageBox, QProgressBar, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 820
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QPlainTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QLabel { color: #00ffff; }
"""

CHUNK = 1024 * 1024
ALGOS = ["SHA256", "SHA512", "SHA1", "MD5"]


def hash_file(path, algo, progress_cb=None):
    """Hash a file in chunks, reporting progress. Returns hex digest."""
    h = hashlib.new(algo.lower())
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
            done += len(chunk)
            if progress_cb and total:
                progress_cb(int(done / total * 100))
    return h.hexdigest()


class HashWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, path, algo):
        super().__init__()
        self._path = path
        self._algo = algo

    def run(self):
        try:
            digest = hash_file(self._path, self._algo,
                               lambda p: self.progress.emit(p))
            self.finished.emit(digest)
        except Exception as e:
            self.finished.emit(f"ERROR: {e}")


class ChecksumVerifier(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Checksum Verifier")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._computed = ""
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Checksum Verifier")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # File selection
        file_box = QGroupBox("File")
        fl = QHBoxLayout(file_box)
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("/path/to/file or ISO")
        fl.addWidget(self._file_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        fl.addWidget(browse_btn)
        root.addWidget(file_box)

        # Algorithm
        algo_row = QHBoxLayout()
        algo_row.addWidget(QLabel("Algorithm:"))
        self._algo_combo = QComboBox()
        self._algo_combo.addItems(ALGOS)
        algo_row.addWidget(self._algo_combo)

        compute_btn = QPushButton("Compute")
        compute_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        compute_btn.clicked.connect(self._compute)
        algo_row.addWidget(compute_btn)
        algo_row.addStretch()
        root.addLayout(algo_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Result
        res_box = QGroupBox("Computed Checksum")
        rl = QVBoxLayout(res_box)
        self._result_edit = QLineEdit()
        self._result_edit.setReadOnly(True)
        self._result_edit.setStyleSheet("font-size: 11px;")
        rl.addWidget(self._result_edit)
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy)
        rl.addWidget(copy_btn)
        root.addWidget(res_box)

        # Verify
        ver_box = QGroupBox("Verify Against Expected")
        vl = QHBoxLayout(ver_box)
        self._expected_edit = QLineEdit()
        self._expected_edit.setPlaceholderText("Paste expected checksum here...")
        vl.addWidget(self._expected_edit, 1)
        verify_btn = QPushButton("Verify")
        verify_btn.clicked.connect(self._verify)
        vl.addWidget(verify_btn)
        root.addWidget(ver_box)

        self._verify_result = QLabel("")
        self._verify_result.setAlignment(Qt.AlignCenter)
        self._verify_result.setStyleSheet("font-size: 13px; font-weight: bold;")
        root.addWidget(self._verify_result)

        # SHA256SUMS tab-style batch verify
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        batch_tab = QWidget()
        bl = QVBoxLayout(batch_tab)
        bl.addWidget(QLabel("Batch Verify (sha256sum format: <hash>  <filename>):"))
        self._batch_edit = QLineEdit()
        self._batch_edit.setPlaceholderText("Select a SHA256SUMS file...")
        bl.addWidget(self._batch_edit)
        batch_btns = QHBoxLayout()
        sums_btn = QPushButton("Select SHA256SUMS File")
        sums_btn.clicked.connect(self._browse_sums)
        batch_btns.addWidget(sums_btn)
        run_batch_btn = QPushButton("Verify All")
        run_batch_btn.clicked.connect(self._run_batch)
        batch_btns.addWidget(run_batch_btn)
        batch_btns.addStretch()
        bl.addLayout(batch_btns)
        self._batch_log = QPlainTextEdit()
        self._batch_log.setReadOnly(True)
        bl.addWidget(self._batch_log)
        tabs.addTab(batch_tab, "Batch Verify (SHA256SUMS)")

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", os.path.expanduser("~"))
        if path:
            self._file_edit.setText(path)

    def _browse_sums(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SHA256SUMS", os.path.expanduser("~"), "Checksums (SHA256SUMS* *.sha256);;All files (*)"
        )
        if path:
            self._batch_edit.setText(path)

    def _compute(self):
        path = self._file_edit.text().strip()
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Invalid File", "Select a valid file first.")
            return
        algo = self._algo_combo.currentText()
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText(f"Computing {algo} for {os.path.basename(path)}...")
        self._result_edit.clear()
        self._verify_result.setText("")

        self._worker = HashWorker(path, algo)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_computed)
        self._worker.start()

    def _on_computed(self, digest):
        self._progress.setVisible(False)
        if digest.startswith("ERROR:"):
            self._status.setText(digest)
            QMessageBox.warning(self, "Hash Failed", digest)
            return
        self._computed = digest
        self._result_edit.setText(digest)
        self._status.setText(f"{self._algo_combo.currentText()} computed")
        log_info(f"Checksum computed: {digest[:16]}...")

    def _copy(self):
        QApplication.clipboard().setText(self._result_edit.text())
        self._status.setText("Copied to clipboard")

    def _verify(self):
        expected = self._expected_edit.text().strip().lower()
        if not self._computed:
            QMessageBox.information(self, "Nothing to Compare", "Compute a checksum first.")
            return
        if not expected:
            QMessageBox.warning(self, "Missing Expected", "Paste the expected checksum.")
            return
        if expected == self._computed:
            self._verify_result.setText("✓ MATCH — checksum verified")
            self._verify_result.setStyleSheet("color: #00ff88; font-size: 13px; font-weight: bold;")
            log_info("Checksum verified: MATCH")
        else:
            self._verify_result.setText("✗ MISMATCH — file corrupted or altered")
            self._verify_result.setStyleSheet("color: #ff4444; font-size: 13px; font-weight: bold;")
            log_error("Checksum MISMATCH")

    def _run_batch(self):
        sums_path = self._batch_edit.text().strip()
        if not os.path.isfile(sums_path):
            QMessageBox.warning(self, "Missing File", "Select a SHA256SUMS file first.")
            return
        base_dir = os.path.dirname(os.path.abspath(sums_path))
        self._batch_log.clear()
        passed = failed = missing = 0

        try:
            with open(sums_path) as f:
                lines = f.readlines()
        except Exception as e:
            QMessageBox.warning(self, "Read Failed", str(e))
            return

        self._batch_log.appendPlainText(f"Verifying {len(lines)} entries against {sums_path}\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            expected, filename = parts[0].lower(), parts[1].strip().lstrip("*").strip()
            filepath = os.path.join(base_dir, filename)
            if not os.path.isfile(filepath):
                self._batch_log.appendPlainText(f"[MISSING] {filename}")
                missing += 1
                continue
            try:
                actual = hash_file(filepath, "sha256")
                if actual == expected:
                    self._batch_log.appendPlainText(f"[PASS] {filename}")
                    passed += 1
                else:
                    self._batch_log.appendPlainText(f"[FAIL] {filename} — expected {expected[:16]}..., got {actual[:16]}...")
                    failed += 1
            except Exception as e:
                self._batch_log.appendPlainText(f"[ERROR] {filename}: {e}")
                failed += 1

        summary = f"\n{'='*50}\n{passed} passed | {failed} failed | {missing} missing"
        self._batch_log.appendPlainText(summary)
        self._status.setText(f"Batch: {passed} pass, {failed} fail, {missing} missing")
        log_info(f"Batch checksum verify: {passed}/{passed+failed+missing} passed")


def main():
    app = QApplication(sys.argv)
    win = ChecksumVerifier()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()