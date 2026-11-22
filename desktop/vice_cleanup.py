#!/usr/bin/env python3
"""Vice OS — System Cleanup. Safe disk space reclaimer with preview before delete."""

import sys
import os
import subprocess
import glob
import shutil

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QProgressBar, QPlainTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 16px; height: 16px; background: #1a1a1a; border: 1px solid #00ffff; border-radius: 3px; }
QCheckBox::indicator:checked { background: #00ffff; }
QPlainTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QLabel { color: #00ffff; }
"""

HOME = os.path.expanduser("~")


def dir_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, onerror=lambda e: None):
        for f in filenames:
            try:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def fmt_size(n):
    for unit, factor in [("B", 1), ("KB", 1024), ("MB", 1024**2), ("GB", 1024**3)]:
        if n < factor * 1024:
            return f"{n / factor:.1f} {unit}"
    return f"{n / 1024**3:.1f} GB"


def apt_cache_size():
    out, _ = "", False
    try:
        r = subprocess.run(["sh", "-c", "du -sb /var/cache/apt 2>/dev/null | cut -f1"],
                           capture_output=True, text=True, timeout=5)
        return int(r.stdout.strip() or 0)
    except Exception:
        return 0


def journal_size():
    try:
        r = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True, timeout=5)
        # "Archived and active journals take up 123.4M"
        m = None
        import re
        m = re.search(r"take up ([\d.]+[KMGT])", r.stdout)
        if m:
            s = m.group(1)
            units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
            return int(float(s[:-1]) * units.get(s[-1], 1))
    except Exception:
        pass
    return 0


def count_thumbnails():
    path = os.path.join(HOME, ".cache/thumbnails")
    n = 0
    for _root, _dirs, files in os.walk(path, onerror=lambda e: None):
        n += len(files)
    return n


def old_kernels_count():
    try:
        r = subprocess.run(["dpkg", "-l"], capture_output=True, text=True, timeout=5)
        running, _ = subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip(), True
        count = 0
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "ii" and parts[1].startswith("linux-image-"):
                ver = parts[1].replace("linux-image-", "")
                if ver != running:
                    count += 1
        return count
    except Exception:
        return 0


class CleanupTargets:
    """Registry of cleanup targets: id, name, description, size_fn, clean_fn."""

    @staticmethod
    def targets():
        return [
            {
                "id": "apt_cache",
                "name": "APT Package Cache",
                "desc": "Downloaded .deb files in /var/cache/apt",
                "size_fn": apt_cache_size,
                "clean_fn": lambda log: log.append(CleanupTargets._sudo_run(
                    ["apt-get", "clean"], "apt-get clean")),
            },
            {
                "id": "apt_autoremove",
                "name": "Orphaned Packages (autoremove)",
                "desc": "Packages installed as dependencies no longer needed",
                "size_fn": lambda: 0,
                "size_note": "variable",
                "clean_fn": lambda log: log.append(CleanupTargets._sudo_run(
                    ["apt-get", "autoremove", "-y"], "apt-get autoremove")),
            },
            {
                "id": "thumbnails",
                "name": "Thumbnail Cache",
                "desc": f"~/.cache/thumbnails ({count_thumbnails()} files)",
                "size_fn": lambda: dir_size(os.path.join(HOME, ".cache", "thumbnails")),
                "clean_fn": lambda log: log.append(CleanupTargets._rm_tree(
                    os.path.join(HOME, ".cache", "thumbnails"))),
            },
            {
                "id": "journal",
                "name": "Systemd Journal (vacuum to 100M)",
                "desc": "Old systemd journal entries",
                "size_fn": journal_size,
                "clean_fn": lambda log: log.append(CleanupTargets._sudo_run(
                    ["journalctl", "--vacuum-size=100M"], "journalctl vacuum")),
            },
            {
                "id": "trash",
                "name": "Trash",
                "desc": f"~/.local/share/Trash",
                "size_fn": lambda: dir_size(os.path.join(HOME, ".local", "share", "Trash")),
                "clean_fn": lambda log: (
                    log.append(CleanupTargets._rm_tree(
                        os.path.join(HOME, ".local", "share", "Trash", "files"))),
                    log.append(CleanupTargets._rm_tree(
                        os.path.join(HOME, ".local", "share", "Trash", "info")))
                ),
            },
            {
                "id": "tmp_user",
                "name": "User Temp Files",
                "desc": "~/.cache/temp, /tmp/vice_* owned by user",
                "size_fn": lambda: dir_size(os.path.join(HOME, ".cache", "temp")) +
                                      sum(dir_size(p) for p in glob.glob("/tmp/vice_*")),
                "clean_fn": lambda log: log.append(
                    CleanupTargets._rm_tree(os.path.join(HOME, ".cache", "temp"))),
            },
        ]

    @staticmethod
    def _sudo_run(cmd, label):
        try:
            proc = subprocess.Popen(["sudo"] + cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            out = proc.communicate()[0]
            return f"[{'OK' if proc.returncode == 0 else 'FAIL'}] {label}\n{out.strip()[:300]}"
        except Exception as e:
            return f"[FAIL] {label}: {e}"

    @staticmethod
    def _rm_tree(path):
        if os.path.isdir(path):
            try:
                shutil.rmtree(path)
                return f"[OK] Removed {path}"
            except Exception as e:
                return f"[FAIL] {path}: {e}"
        return f"[SKIP] {path} not present"


class ScanWorker(QThread):
    """Scans target sizes off the UI thread."""
    progress = pyqtSignal(int, int)  # index, size
    finished = pyqtSignal(int)       # total size

    def __init__(self, targets):
        super().__init__()
        self._targets = targets

    def run(self):
        total = 0
        for i, t in enumerate(self._targets):
            size = t["size_fn"]()
            total += size
            self.progress.emit(i, size)
        self.finished.emit(total)


class CleanWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, targets):
        super().__init__()
        self._targets = targets

    def run(self):
        class Emitter:
            def __init__(self, emit):
                self._emit = emit

            def append(self, text):
                self._emit(str(text))

        em = Emitter(self.line.emit)
        for t in self._targets:
            self.line.emit(f"--- Cleaning: {t['name']} ---")
            try:
                t["clean_fn"](em)
            except Exception as e:
                self.line.emit(f"[FAIL] {t['name']}: {e}")
        self.finished.emit()


class SystemCleanup(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — System Cleanup")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._targets = CleanupTargets.targets()
        self._scan_worker = None
        self._clean_worker = None
        self._init_ui()
        self._scan()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — System Cleanup")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Targets table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Clean", "Target", "Description", "Size"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        for i, t in enumerate(self._targets):
            self._table.insertRow(i)

            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(t["id"] in ("apt_cache", "thumbnails", "trash"))
            cb_widget.setProperty("row", i)
            self._table.setCellWidget(i, 0, cb_widget)
            self._checkboxes = getattr(self, "_checkboxes", [])
            self._checkboxes.append(cb)

            name_item = QTableWidgetItem(t["name"])
            name_item.setForeground(QBrush(QColor("#00ffff")))
            self._table.setItem(i, 1, name_item)
            self._table.setItem(i, 2, QTableWidgetItem(t["desc"]))
            size_item = QTableWidgetItem("scanning...")
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(i, 3, size_item)

        # Buttons
        btn_row = QHBoxLayout()
        rescan_btn = QPushButton("↻ Rescan Sizes")
        rescan_btn.clicked.connect(self._scan)
        btn_row.addWidget(rescan_btn)

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb in self._checkboxes])
        btn_row.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in self._checkboxes])
        btn_row.addWidget(select_none_btn)
        btn_row.addStretch()

        clean_btn = QPushButton("🧹 Clean Selected")
        clean_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        clean_btn.clicked.connect(self._clean_selected)
        btn_row.addWidget(clean_btn)
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Log
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(150)
        root.addWidget(self._log)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _scan(self):
        self._status.setText("Scanning target sizes...")
        self._scan_worker = ScanWorker(self._targets)
        self._scan_worker.progress.connect(self._on_size)
        self._scan_worker.finished.connect(self._scan_done)
        self._scan_worker.start()

    def _on_size(self, index, size):
        item = self._table.item(index, 3)
        if item:
            if size == 0 and "size_note" in self._targets[index]:
                item.setText(self._targets[index]["size_note"])
            else:
                item.setText(fmt_size(size) if size else "0 B")

    def _scan_done(self, total):
        self._status.setText(f"Total reclaimable: ~{fmt_size(total)} (excluding autoremove)")
        log_info(f"Cleanup scan: {fmt_size(total)} reclaimable")

    def _clean_selected(self):
        selected = []
        for i, cb in enumerate(self._checkboxes):
            if cb.isChecked():
                selected.append(self._targets[i])
        if not selected:
            QMessageBox.information(self, "Nothing Selected", "Select at least one cleanup target.")
            return
        names = "\n".join("  • " + t["name"] for t in selected)
        if QMessageBox.question(
            self, "Clean Now",
            f"Clean the following targets?\n\n{names}\n\nSome actions require sudo.",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._progress.setVisible(True)
        self._log.clear()
        self._clean_worker = CleanWorker(selected)
        self._clean_worker.line.connect(self._log.appendPlainText)
        self._clean_worker.finished.connect(self._clean_done)
        self._clean_worker.start()

    def _clean_done(self):
        self._progress.setVisible(False)
        self._status.setText("Cleanup complete — rescanning")
        self._log.appendPlainText("[DONE] Cleanup finished")
        log_info("System cleanup executed")
        self._scan()


def main():
    app = QApplication(sys.argv)
    win = SystemCleanup()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()