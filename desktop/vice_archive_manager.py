#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Archive Manager.
GUI tool for creating, extracting, and managing tar, gz, bz2, xz, zip, and 7z archives.
"""

import os
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLineEdit, QComboBox, QGroupBox, QTextEdit, QProgressBar,
    QTabWidget, QListWidget, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 640

FORMATS = {
    "zip": ("zip", "-r", "{out}", "{src}"),
    "tar.gz": ("tar", "-czf", "{out}", "{src}"),
    "tar.bz2": ("tar", "-cjf", "{out}", "{src}"),
    "tar.xz": ("tar", "-cJf", "{out}", "{src}"),
    "tar": ("tar", "-cf", "{out}", "{src}"),
    "7z": ("7z", "a", "{out}", "{src}"),
}


class ArchiveWorker(QThread):
    line_out = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = list(cmd)
        self._stopped = False
        self._proc = None

    def stop(self):
        self._stopped = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.3)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in self._proc.stdout:
                if self._stopped:
                    break
                self.line_out.emit(line.rstrip())
            self._proc.wait()
            if not self._stopped:
                self.finished.emit(self._proc.returncode == 0)
        except Exception as e:
            if not self._stopped:
                self.line_out.emit(f"Error: {e}")
                self.finished.emit(False)
        finally:
            self._proc = None


class ArchiveManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Archive Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(720, 500)
        apply_app_theme(self)
        self._worker = None
        self._create_files = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Archive Manager",
            subtitle="Create and extract ZIP, TAR, GZ, BZ2, XZ, and 7Z archives",
            icon_name="package-x-generic",
            badge_text="ARCHIVES",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        create_tab = QWidget()
        cl = QVBoxLayout(create_tab)

        out_box = QGroupBox("Output Archive")
        ol = QHBoxLayout(out_box)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Output archive path...")
        ol.addWidget(self._out_edit)
        browse_out = make_button("Browse", variant="secondary", parent=self)
        browse_out.clicked.connect(self._browse_output)
        ol.addWidget(browse_out)
        ol.addWidget(QLabel("Format:"))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(list(FORMATS.keys()))
        ol.addWidget(self._fmt_combo)
        cl.addWidget(out_box)

        files_box = QGroupBox("Files / Folders to Archive")
        fl = QVBoxLayout(files_box)
        self._files_list = QListWidget()
        fl.addWidget(self._files_list)
        files_btns = QHBoxLayout()
        add_file_btn = make_button("Add Files", variant="secondary", parent=self)
        add_file_btn.clicked.connect(self._add_files)
        files_btns.addWidget(add_file_btn)
        add_dir_btn = make_button("Add Folder", variant="secondary", parent=self)
        add_dir_btn.clicked.connect(self._add_dir)
        files_btns.addWidget(add_dir_btn)
        remove_btn = make_button("Remove Selected", variant="danger", parent=self)
        remove_btn.clicked.connect(self._remove_file)
        files_btns.addWidget(remove_btn)
        fl.addLayout(files_btns)
        cl.addWidget(files_box)

        self._create_btn = make_button("Create Archive", variant="primary", parent=self)
        self._create_btn.clicked.connect(self._create_archive)
        cl.addWidget(self._create_btn)
        tabs.addTab(create_tab, "Create")

        extract_tab = QWidget()
        el = QVBoxLayout(extract_tab)

        src_box = QGroupBox("Archive to Extract")
        sl = QHBoxLayout(src_box)
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText("Select archive file...")
        sl.addWidget(self._src_edit)
        browse_src = make_button("Browse", variant="secondary", parent=self)
        browse_src.clicked.connect(self._browse_src)
        sl.addWidget(browse_src)
        el.addWidget(src_box)

        dest_box = QGroupBox("Extract To")
        dl = QHBoxLayout(dest_box)
        self._dest_edit = QLineEdit(os.path.expanduser("~"))
        dl.addWidget(self._dest_edit)
        browse_dest = make_button("Browse", variant="secondary", parent=self)
        browse_dest.clicked.connect(self._browse_dest)
        dl.addWidget(browse_dest)
        el.addWidget(dest_box)

        self._extract_btn = make_button("Extract Archive", variant="primary", parent=self)
        self._extract_btn.clicked.connect(self._extract_archive)
        el.addWidget(self._extract_btn)
        el.addStretch()
        tabs.addTab(extract_tab, "Extract")

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(150)
        root.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _browse_output(self):
        fmt = self._fmt_combo.currentText()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Archive As", os.path.expanduser("~"),
            f"{fmt.upper()} (*.{fmt});;All files (*)"
        )
        if path:
            if not path.endswith(f".{fmt}"):
                path += f".{fmt}"
            self._out_edit.setText(path)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files", os.path.expanduser("~"))
        for p in paths:
            if p not in self._create_files:
                self._create_files.append(p)
                self._files_list.addItem(p)

    def _add_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Add Folder", os.path.expanduser("~"))
        if path and path not in self._create_files:
            self._create_files.append(path)
            self._files_list.addItem(path)

    def _remove_file(self):
        row = self._files_list.currentRow()
        if row >= 0:
            self._create_files.pop(row)
            self._files_list.takeItem(row)

    def _browse_src(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Archive", os.path.expanduser("~"),
            "Archives (*.zip *.tar *.tar.gz *.tar.bz2 *.tar.xz *.7z *.tgz);;All files (*)"
        )
        if path:
            self._src_edit.setText(path)

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Extract To", self._dest_edit.text())
        if path:
            self._dest_edit.setText(path)

    def _create_archive(self):
        out = self._out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "No Output", "Specify an output archive path.")
            return
        if not self._create_files:
            QMessageBox.warning(self, "No Files", "Add files or folders to archive.")
            return
        fmt = self._fmt_combo.currentText()
        template = FORMATS[fmt]
        cmd = [c.replace("{out}", out) for c in template]
        src_idx = cmd.index("{src}") if "{src}" in cmd else -1
        if src_idx >= 0:
            cmd = cmd[:src_idx] + self._create_files + cmd[src_idx + 1:]
        self._run(cmd, f"Creating {os.path.basename(out)}...")

    def _extract_archive(self):
        src = self._src_edit.text().strip()
        dest = self._dest_edit.text().strip()
        if not src or not os.path.isfile(src):
            QMessageBox.warning(self, "No Archive", "Select an existing archive to extract.")
            return
        if not dest:
            dest = os.path.expanduser("~")
        os.makedirs(dest, exist_ok=True)
        low = src.lower()
        if low.endswith(".zip"):
            cmd = ["unzip", "-o", src, "-d", dest]
        elif low.endswith(".7z"):
            cmd = ["7z", "x", src, f"-o{dest}", "-y"]
        elif any(low.endswith(e) for e in (".tar.gz", ".tgz")):
            cmd = ["tar", "-xzf", src, "-C", dest]
        elif low.endswith(".tar.bz2"):
            cmd = ["tar", "-xjf", src, "-C", dest]
        elif low.endswith(".tar.xz"):
            cmd = ["tar", "-xJf", src, "-C", dest]
        else:
            cmd = ["tar", "-xf", src, "-C", dest]
        self._run(cmd, f"Extracting to {dest}...")

    def _run(self, cmd, msg):
        if self._worker is not None and self._worker.isRunning():
            self._status.setText("Another archive task is already running...")
            return
        if not shutil.which(cmd[0]):
            QMessageBox.warning(self, "Missing Tool", f"Archive utility '{cmd[0]}' is not installed.")
            return
        self._create_btn.setEnabled(False)
        self._extract_btn.setEnabled(False)
        self._log.clear()
        self._progress.setVisible(True)
        self._status.setText(msg)
        self._log.append(f"$ {' '.join(cmd)}\n")
        w = ArchiveWorker(cmd)
        w.line_out.connect(self._log.append)
        w.finished.connect(self._done)
        w.start()
        self._worker = w

    def _done(self, ok):
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)
        self._extract_btn.setEnabled(True)
        c = COLORS["success"] if ok else COLORS["danger"]
        msg = "Done" if ok else "Failed"
        self._log.append(f'<span style="color:{c};">[{msg}]</span>')
        self._status.setText(msg)
        log_info(f"Archive operation: {msg}")

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = ArchiveManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
