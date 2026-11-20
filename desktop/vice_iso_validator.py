#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) ISO Validator
GUI test runner for Vice OS ISO verification scripts (rootfs, kernel, packages, bootloader).
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QTextEdit, QProgressBar, QLineEdit, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from python.vice_utils import log_info, log_error

WORKDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VALIDATION_DIR = os.path.join(WORKDIR, 'validation')
DEFAULT_ISO = os.path.join(WORKDIR, 'out', 'gta-vi-os-amd64.iso')

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTextEdit { background: #0d0d0d; color: #00e5ff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 8px; padding: 6px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""

VALIDATORS = [
    ("Package List",  "validate_packages.sh",  None),
    ("RootFS",        "validate_rootfs.sh",     "{chroot}"),
    ("Kernel",        "validate_kernel.sh",     "{chroot}"),
    ("Initramfs",     "validate_initramfs.sh",  "{chroot}"),
    ("ISO Image",     "validate_iso.sh",        "{iso}"),
]


class ValidatorWorker(QThread):
    step_started  = pyqtSignal(str)
    step_done     = pyqtSignal(str, bool, str)
    line_out      = pyqtSignal(str)
    all_done      = pyqtSignal(int, int, int)

    def __init__(self, iso_path, chroot_path, run_single=None):
        super().__init__()
        self.iso_path    = iso_path
        self.chroot_path = chroot_path
        self.run_single  = run_single

    def _run_script(self, script, arg):
        path = os.path.join(VALIDATION_DIR, script)
        if not os.path.isfile(path):
            return False, f"Script not found: {path}"
        cmd = ["bash", path] + ([arg] if arg else [])
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            output = []
            for line in proc.stdout:
                stripped = line.rstrip()
                self.line_out.emit(stripped)
                output.append(stripped)
            proc.wait()
            return proc.returncode == 0, "\n".join(output)
        except Exception as e:
            return False, str(e)

    def run(self):
        passed = failed = skipped = 0
        validators = ([v for v in VALIDATORS if v[0] == self.run_single]
                      if self.run_single else VALIDATORS)

        for name, script, arg_template in validators:
            arg = None
            if arg_template == "{iso}":
                if not self.iso_path or not os.path.isfile(self.iso_path):
                    self.line_out.emit(f"[SKIP] {name} — ISO not found")
                    skipped += 1
                    continue
                arg = self.iso_path
            elif arg_template == "{chroot}":
                if not self.chroot_path or not os.path.isdir(self.chroot_path):
                    self.line_out.emit(f"[SKIP] {name} — chroot not found")
                    skipped += 1
                    continue
                arg = self.chroot_path

            self.step_started.emit(name)
            ok, _ = self._run_script(script, arg)
            self.step_done.emit(name, ok, "")
            if ok:
                passed += 1
            else:
                failed += 1

        self.all_done.emit(passed, failed, skipped)


class ISOValidator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — ISO Build Validator")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — ISO Build Validator")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # ISO path selector
        iso_group = QGroupBox("ISO Image")
        iso_layout = QHBoxLayout(iso_group)
        self._iso_edit = QLineEdit(DEFAULT_ISO)
        iso_layout.addWidget(self._iso_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_iso)
        iso_layout.addWidget(browse_btn)
        root.addWidget(iso_group)

        # Chroot path selector
        chroot_group = QGroupBox("Chroot Directory (for RootFS/Kernel/Initramfs checks)")
        chroot_layout = QHBoxLayout(chroot_group)
        self._chroot_edit = QLineEdit(os.path.join(WORKDIR, 'chroot'))
        chroot_layout.addWidget(self._chroot_edit)
        browse_chroot = QPushButton("Browse")
        browse_chroot.clicked.connect(self._browse_chroot)
        chroot_layout.addWidget(browse_chroot)
        root.addWidget(chroot_group)

        # Output log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, len(VALIDATORS))
        self._progress.setValue(0)
        root.addWidget(self._progress)

        # Buttons
        btn_row = QHBoxLayout()
        self._run_all_btn = QPushButton("Run All Validators")
        self._run_all_btn.clicked.connect(self._run_all)
        btn_row.addWidget(self._run_all_btn)

        self._run_iso_btn = QPushButton("ISO Only")
        self._run_iso_btn.clicked.connect(lambda: self._run_single("ISO Image"))
        btn_row.addWidget(self._run_iso_btn)

        self._run_rootfs_btn = QPushButton("RootFS Only")
        self._run_rootfs_btn.clicked.connect(lambda: self._run_single("RootFS"))
        btn_row.addWidget(self._run_rootfs_btn)

        btn_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._log.clear)
        btn_row.addWidget(clear_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)

        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _browse_iso(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select ISO", WORKDIR, "ISO files (*.iso)")
        if path:
            self._iso_edit.setText(path)

    def _browse_chroot(self):
        path = QFileDialog.getExistingDirectory(self, "Select Chroot Directory", WORKDIR)
        if path:
            self._chroot_edit.setText(path)

    def _run_all(self):
        self._start_worker(None)

    def _run_single(self, name):
        self._start_worker(name)

    def _start_worker(self, single):
        self._run_all_btn.setEnabled(False)
        self._run_iso_btn.setEnabled(False)
        self._run_rootfs_btn.setEnabled(False)
        self._progress.setValue(0)
        self._log.clear()
        self._log.append("Starting validation...\n")

        self._worker = ValidatorWorker(
            self._iso_edit.text().strip(),
            self._chroot_edit.text().strip(),
            single
        )
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.line_out.connect(self._log.append)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_step_started(self, name):
        self._status.setText(f"Running: {name}")
        self._log.append(f"\n{'─'*50}\n[{name}]\n{'─'*50}")

    def _on_step_done(self, name, ok, _):
        val = self._progress.value() + 1
        self._progress.setValue(val)
        c = "#00ff88" if ok else "#ff4444"
        label = "PASS" if ok else "FAIL"
        self._log.append(f'<span style="color:{c};">[{label}] {name}</span>')
        log_info(f"Validator {name}: {label}")

    def _on_all_done(self, passed, failed, skipped):
        self._run_all_btn.setEnabled(True)
        self._run_iso_btn.setEnabled(True)
        self._run_rootfs_btn.setEnabled(True)

        c = "#00ff88" if failed == 0 else "#ff4444"
        self._log.append(
            f'\n<span style="color:{c}; font-weight:bold;">'
            f'Results: {passed} passed  |  {failed} failed  |  {skipped} skipped'
            f'</span>'
        )
        self._status.setText(f"Done — {passed} passed, {failed} failed, {skipped} skipped")

    def _export(self):
        import datetime
        path = os.path.expanduser(
            f"~/vice_validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        try:
            with open(path, "w") as f:
                f.write(self._log.toPlainText())
            log_info(f"Validation report exported to {path}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")


def main():
    app = QApplication(sys.argv)
    win = ISOValidator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
