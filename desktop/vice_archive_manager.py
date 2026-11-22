#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Archive Manager
GUI tool for creating, extracting, and managing tar, gz, bz2, xz, zip, and 7z archives.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLineEdit, QComboBox, QGroupBox, QTextEdit, QProgressBar,
    QTabWidget, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTextEdit { background: #0d0d0d; color: #00e5ff; border: 1px solid #1a4a4a; font-size: 11px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QLabel { color: #00ffff; }
"""

FORMATS = {
    "zip":      ("zip", "-r", "{out}", "{src}"),
    "tar.gz":   ("tar", "-czf", "{out}", "{src}"),
    "tar.bz2":  ("tar", "-cjf", "{out}", "{src}"),
    "tar.xz":   ("tar", "-cJf", "{out}", "{src}"),
    "tar":      ("tar", "-cf",  "{out}", "{src}"),
    "7z":       ("7z", "a", "{out}", "{src}"),
}


class ArchiveWorker(QThread):
    line_out = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True
            )
            for line in proc.stdout:
                self.line_out.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode == 0)
        except Exception as e:
            self.line_out.emit(f"Error: {e}")
            self.finished.emit(False)


class ArchiveManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Archive Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._create_files = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Archive Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Create tab ---
        create_tab = QWidget()
        cl = QVBoxLayout(create_tab)

        out_box = QGroupBox("Output Archive")
        ol = QHBoxLayout(out_box)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Output archive path...")
        ol.addWidget(self._out_edit)
        browse_out = QPushButton("Browse")
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
        add_file_btn = QPushButton("Add Files")
        add_file_btn.clicked.connect(self._add_files)
        files_btns.addWidget(add_file_btn)
        add_dir_btn = QPushButton("Add Folder")
        add_dir_btn.clicked.connect(self._add_dir)
        files_btns.addWidget(add_dir_btn)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_file)
        files_btns.addWidget(remove_btn)
        fl.addLayout(files_btns)
        cl.addWidget(files_box)

        self._create_btn = QPushButton("Create Archive")
        self._create_btn.clicked.connect(self._create_archive)
        cl.addWidget(self._create_btn)
        tabs.addTab(create_tab, "Create")

        # --- Extract tab ---
        extract_tab = QWidget()
        el = QVBoxLayout(extract_tab)

        src_box = QGroupBox("Archive to Extract")
        sl = QHBoxLayout(src_box)
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText("Select archive file...")
        sl.addWidget(self._src_edit)
        browse_src = QPushButton("Browse")
        browse_src.clicked.connect(self._browse_src)
        sl.addWidget(browse_src)
        el.addWidget(src_box)

        dest_box = QGroupBox("Extract To")
        dl = QHBoxLayout(dest_box)
        self._dest_edit = QLineEdit(os.path.expanduser("~"))
        dl.addWidget(self._dest_edit)
        browse_dest = QPushButton("Browse")
        browse_dest.clicked.connect(self._browse_dest)
        dl.addWidget(browse_dest)
        el.addWidget(dest_box)

        self._extract_btn = QPushButton("Extract Archive")
        self._extract_btn.clicked.connect(self._extract_archive)
        el.addWidget(self._extract_btn)
        tabs.addTab(extract_tab, "Extract")

        # Output log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        root.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
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
        cmd = list(template)
        cmd = [c.replace("{out}", out) for c in cmd]
        src_idx = cmd.index("{src}") if "{src}" in cmd else -1
        if src_idx >= 0:
            cmd = cmd[:src_idx] + self._create_files + cmd[src_idx+1:]
        self._run(cmd, f"Creating {os.path.basename(out)}...")

    def _extract_archive(self):
        src = self._src_edit.text().strip()
        dest = self._dest_edit.text().strip()
        if not src:
            QMessageBox.warning(self, "No Archive", "Select an archive to extract.")
            return
        os.makedirs(dest, exist_ok=True)
        if src.endswith(".zip"):
            cmd = ["unzip", "-o", src, "-d", dest]
        elif src.endswith(".7z"):
            cmd = ["7z", "x", src, f"-o{dest}", "-y"]
        elif any(src.endswith(e) for e in (".tar.gz", ".tgz")):
            cmd = ["tar", "-xzf", src, "-C", dest]
        elif src.endswith(".tar.bz2"):
            cmd = ["tar", "-xjf", src, "-C", dest]
        elif src.endswith(".tar.xz"):
            cmd = ["tar", "-xJf", src, "-C", dest]
        elif src.endswith(".tar"):
            cmd = ["tar", "-xf", src, "-C", dest]
        else:
            cmd = ["tar", "-xf", src, "-C", dest]
        self._run(cmd, f"Extracting to {dest}...")

    def _run(self, cmd, msg):
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
        c = "#00ff88" if ok else "#ff4444"
        msg = "Done" if ok else "Failed"
        self._log.append(f'<span style="color:{c};">[{msg}]</span>')
        self._status.setText(msg)
        log_info(f"Archive operation: {msg}")


def main():
    app = QApplication(sys.argv)
    win = ArchiveManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
