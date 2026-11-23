#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) ISO Validator
GUI test runner for Vice OS ISO verification scripts (rootfs, kernel, packages, bootloader).
"""

import datetime
import os
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WORKDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VALIDATION_DIR = os.path.join(WORKDIR, 'validation')
DEFAULT_ISO = os.path.join(WORKDIR, 'out', 'gta-vi-os-amd64.iso')

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 620

VALIDATORS = [
    ("Package List", "validate_packages.sh", None),
    ("RootFS", "validate_rootfs.sh", "{chroot}"),
    ("Kernel", "validate_kernel.sh", "{chroot}"),
    ("Initramfs", "validate_initramfs.sh", "{chroot}"),
    ("ISO Image", "validate_iso.sh", "{iso}"),
]


class ValidatorWorker(QThread):
    step_started = pyqtSignal(str)
    step_done = pyqtSignal(str, bool, str)
    line_out = pyqtSignal(str)
    all_done = pyqtSignal(int, int, int)

    def __init__(self, iso_path, chroot_path, run_single=None, parent=None):
        super().__init__(parent)
        self.iso_path = iso_path
        self.chroot_path = chroot_path
        self.run_single = run_single
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _run_script(self, script, arg):
        path = os.path.join(VALIDATION_DIR, script)
        if not os.path.isfile(path):
            return False, f"Script not found: {path}"
        cmd = ["bash", path] + ([arg] if arg else [])
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            output = []
            if self._proc.stdout:
                for line in self._proc.stdout:
                    if self._cancelled:
                        break
                    stripped = line.rstrip()
                    self.line_out.emit(stripped)
                    output.append(stripped)
            rc = self._proc.wait()
            return rc == 0, "\n".join(output)
        except Exception as e:
            return False, str(e)

    def run(self):
        passed = failed = skipped = 0
        validators = (
            [v for v in VALIDATORS if v[0] == self.run_single]
            if self.run_single
            else VALIDATORS
        )

        for name, script, arg_template in validators:
            if self._cancelled:
                break
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
            if self._cancelled:
                break
            self.step_done.emit(name, ok, "")
            if ok:
                passed += 1
            else:
                failed += 1

        if not self._cancelled:
            self.all_done.emit(passed, failed, skipped)


class ISOValidator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — ISO Build Validator")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(720, 500)
        vt.apply_app_theme(self)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "ISO Build Validator",
            "Verify Vice OS package list, rootfs, kernel, initramfs and ISO image",
            icon_name="media-optical",
            badge_text="ISO CHECK",
            badge_variant="gold",
            parent=self,
        ))

        iso_group = QGroupBox("ISO Image")
        iso_layout = QHBoxLayout(iso_group)
        self._iso_edit = QLineEdit(DEFAULT_ISO)
        iso_layout.addWidget(self._iso_edit)
        browse_btn = vt.make_button("Browse", "secondary", parent=iso_group)
        browse_btn.clicked.connect(self._browse_iso)
        iso_layout.addWidget(browse_btn)
        root.addWidget(iso_group)

        chroot_group = QGroupBox("Chroot Directory (for RootFS/Kernel/Initramfs checks)")
        chroot_layout = QHBoxLayout(chroot_group)
        self._chroot_edit = QLineEdit(os.path.join(WORKDIR, 'chroot'))
        chroot_layout.addWidget(self._chroot_edit)
        browse_chroot = vt.make_button("Browse", "secondary", parent=chroot_group)
        browse_chroot.clicked.connect(self._browse_chroot)
        chroot_layout.addWidget(browse_chroot)
        root.addWidget(chroot_group)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, len(VALIDATORS))
        self._progress.setValue(0)
        root.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._run_all_btn = vt.make_button("Run All Validators", "primary", parent=self)
        self._run_all_btn.clicked.connect(self._run_all)
        btn_row.addWidget(self._run_all_btn)

        self._run_iso_btn = vt.make_button("ISO Only", "secondary", parent=self)
        self._run_iso_btn.clicked.connect(lambda: self._run_single("ISO Image"))
        btn_row.addWidget(self._run_iso_btn)

        self._run_rootfs_btn = vt.make_button("RootFS Only", "secondary", parent=self)
        self._run_rootfs_btn.clicked.connect(lambda: self._run_single("RootFS"))
        btn_row.addWidget(self._run_rootfs_btn)

        btn_row.addStretch()

        clear_btn = vt.make_button("Clear", "secondary", parent=self)
        clear_btn.clicked.connect(self._log.clear)
        btn_row.addWidget(clear_btn)

        export_btn = vt.make_button("Export", "secondary", parent=self)
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
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
        if self._worker is not None and self._worker.isRunning():
            return
        self._run_all_btn.setEnabled(False)
        self._run_iso_btn.setEnabled(False)
        self._run_rootfs_btn.setEnabled(False)
        self._progress.setRange(0, 1 if single else len(VALIDATORS))
        self._progress.setValue(0)
        self._log.clear()
        self._log.append("Starting validation...\n")

        self._worker = ValidatorWorker(
            self._iso_edit.text().strip(),
            self._chroot_edit.text().strip(),
            single,
            parent=self,
        )
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.line_out.connect(self._log.append)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_step_started(self, name):
        self._status.setText(f"Running: {name}")
        self._log.append(f"\n{'-' * 50}\n[{name}]\n{'-' * 50}")

    def _on_step_done(self, name, ok, _):
        self._progress.setValue(self._progress.value() + 1)
        c = vt.COLORS["success"] if ok else vt.COLORS["danger"]
        label = "PASS" if ok else "FAIL"
        self._log.append(f'<span style="color:{c};">[{label}] {name}</span>')
        log_info(f"Validator {name}: {label}")

    def _on_all_done(self, passed, failed, skipped):
        self._run_all_btn.setEnabled(True)
        self._run_iso_btn.setEnabled(True)
        self._run_rootfs_btn.setEnabled(True)

        c = vt.COLORS["success"] if failed == 0 else vt.COLORS["danger"]
        self._log.append(
            f'\n<span style="color:{c}; font-weight:bold;">'
            f'Results: {passed} passed  |  {failed} failed  |  {skipped} skipped'
            f'</span>'
        )
        self._status.setText(f"Done — {passed} passed, {failed} failed, {skipped} skipped")

    def _export(self):
        path = os.path.expanduser(
            f"~/vice_validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._log.toPlainText())
            log_info(f"Validation report exported to {path}")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = ISOValidator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
