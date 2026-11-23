#!/usr/bin/env python3
"""Vice OS — Disk Usage Analyzer. Folder size tree with bar visualization."""

import os
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QComboBox, QProgressBar, QFileDialog,
    QMessageBox, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info, log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640

SKIP_DIRS = {"/proc", "/sys", "/dev", "/run"}


def fmt_size(n):
    for unit, factor in (("B", 1), ("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4)):
        if n < factor * 1024:
            return f"{n / factor:.1f} {unit}"
    return f"{n / 1024**4:.1f} TB"


class ScanWorker(QThread):
    """Scans directory tree, computing sizes. Emits incremental results."""
    node_done = pyqtSignal(str, int, int)
    finished = pyqtSignal(int)

    def __init__(self, root):
        super().__init__()
        self._root = root
        self._stop = False

    def stop(self):
        self._stop = True

    def _dir_size(self, path):
        total = 0
        files = 0
        for dirpath, dirnames, filenames in os.walk(path):
            if self._stop:
                break
            dirnames[:] = [
                d for d in dirnames
                if os.path.join(dirpath, d) not in SKIP_DIRS
            ]
            for f in filenames:
                if self._stop:
                    break
                try:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                        files += 1
                except OSError:
                    pass
        return total, files

    def run(self):
        grand_total = 0
        try:
            entries = sorted(os.listdir(self._root))
        except OSError as e:
            log_error(f"Scan failed: {e}")
            if not self._stop:
                self.finished.emit(0)
            return

        for entry in entries:
            if self._stop:
                break
            path = os.path.join(self._root, entry)
            try:
                if os.path.islink(path) or path in SKIP_DIRS:
                    continue
                if os.path.isdir(path):
                    size, files = self._dir_size(path)
                    grand_total += size
                    if not self._stop:
                        self.node_done.emit(entry, size, files)
                else:
                    size = os.path.getsize(path)
                    grand_total += size
                    if not self._stop:
                        self.node_done.emit(entry, size, 1)
            except OSError:
                continue

        if not self._stop:
            self.finished.emit(grand_total)


class DiskUsageAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Disk Usage Analyzer")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 500)
        apply_app_theme(self)
        self._worker = None
        self._total = 0
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Disk Usage Analyzer",
            subtitle="Inspect top-level directory and file sizes with drill-down navigation",
            icon_name="drive-harddisk",
            badge_text="STORAGE",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Analyze:"))
        self._path_edit = QLineEdit(os.path.expanduser("~"))
        path_row.addWidget(self._path_edit, 1)

        quick_box = QComboBox()
        for label, path in (
            ("Home", "~"), ("Root /", "/"), ("/var", "/var"),
            ("/usr", "/usr"), ("/etc", "/etc"),
        ):
            quick_box.addItem(label, path)
        quick_box.currentIndexChanged.connect(
            lambda i: self._path_edit.setText(os.path.expanduser(quick_box.itemData(i)))
        )
        path_row.addWidget(quick_box)

        browse_btn = make_button("Browse", variant="secondary", parent=self)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        btn_row = QHBoxLayout()
        self._scan_btn = make_button("Scan", variant="primary", parent=self)
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._stop_btn = make_button("Stop", variant="danger", parent=self)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_scan)
        btn_row.addWidget(self._stop_btn)

        drill_btn = make_button("Drill Into Selected", variant="secondary", parent=self)
        drill_btn.clicked.connect(self._drill_down)
        btn_row.addWidget(drill_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Size", "Files", "% of Parent"])
        self._tree.setColumnWidth(0, 420)
        self._tree.setColumnWidth(1, 100)
        self._tree.setColumnWidth(2, 70)
        self._tree.setRootIsDecorated(False)
        self._tree.setSortingEnabled(False)
        root.addWidget(self._tree, 1)

        self._status = QLabel("Ready — pick a folder and press Scan")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Analyze Directory", self._path_edit.text())
        if path:
            self._path_edit.setText(path)

    def _start_scan(self):
        if self._worker is not None and self._worker.isRunning():
            return
        path = self._path_edit.text().strip()
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Path", f"'{path}' is not a directory.")
            return
        if any(path == s or path.startswith(s + "/") for s in SKIP_DIRS):
            QMessageBox.warning(self, "Skipped", "Pseudo-filesystems (/proc, /sys, /dev, /run) cannot be scanned.")
            return

        self._tree.clear()
        self._total = 0
        self._scan_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._status.setText(f"Scanning {path}...")

        self._worker = ScanWorker(path)
        self._worker.node_done.connect(self._add_node)
        self._worker.finished.connect(self._scan_done)
        self._worker.start()

    def _stop_scan(self):
        if self._worker:
            self._worker.stop()
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status.setText("Scan stopped")

    def _add_node(self, name, size, files):
        item = QTreeWidgetItem([name, fmt_size(size), str(files), ""])
        item.setData(0, Qt.UserRole, size)
        col = COLORS["danger"] if size > 1024**3 else COLORS["warning"] if size > 100 * 1024**2 else COLORS["success"]
        item.setForeground(1, QBrush(QColor(col)))
        self._tree.addTopLevelItem(item)
        self._total += size

    def _scan_done(self, total):
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status.setText(f"Total: {fmt_size(total)} in {self._tree.topLevelItemCount()} top-level entries")

        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            size = item.data(0, Qt.UserRole)
            if size is None:
                continue
            pct = (size / total * 100) if total else 0
            item.setText(3, f"{pct:.1f}%")

        log_info(f"Disk usage scan: {total} bytes in {self._path_edit.text()}")

    def _drill_down(self):
        item = self._tree.currentItem()
        if not item:
            QMessageBox.information(self, "No Selection", "Select an entry to drill into.")
            return
        child_path = os.path.join(self._path_edit.text(), item.text(0))
        if not os.path.isdir(child_path):
            QMessageBox.information(self, "Not a Folder", "Only folders can be drilled into.")
            return
        self._path_edit.setText(child_path)
        self._start_scan()

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = DiskUsageAnalyzer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
