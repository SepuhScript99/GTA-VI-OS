#!/usr/bin/env python3
"""Vice OS — Disk Usage Analyzer. Folder size tree with bar visualization."""

import sys
import os

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QComboBox, QProgressBar, QFileDialog,
    QMessageBox, QSplitter, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTreeWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; font-size: 12px; }
QTreeWidget::item:selected { background: #003333; color: #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""

SKIP_DIRS = {"/proc", "/sys", "/dev", "/run"}


def fmt_size(n):
    for unit, factor in [("B", 1), ("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4)]:
        if n < factor * 1024:
            return f"{n / factor:.1f} {unit}"
    return f"{n / 1024**4:.1f} TB"


class ScanWorker(QThread):
    """Scans directory tree, computing sizes. Emits incremental results."""
    node_done = pyqtSignal(str, int, int)  # path, size, file count
    finished = pyqtSignal(int)            # total size

    def __init__(self, root):
        super().__init__()
        self._root = root
        self._stop = False

    def stop(self):
        self._stop = True

    def _dir_size(self, path):
        """Compute directory size; emit per top-level child for responsiveness."""
        total = 0
        files = 0
        for dirpath, dirnames, filenames in os.walk(path):
            if self._stop:
                break
            # Skip pseudo-filesystems
            dirnames[:] = [d for d in dirnames
                           if os.path.join(dirpath, d) not in SKIP_DIRS]
            for f in filenames:
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
            self.finished.emit(0)
            return

        for entry in entries:
            if self._stop:
                break
            path = os.path.join(self._root, entry)
            try:
                if os.path.islink(path):
                    continue
                if os.path.isdir(path):
                    size, files = self._dir_size(path)
                    grand_total += size
                    self.node_done.emit(entry, size, files)
                else:
                    size = os.path.getsize(path)
                    grand_total += size
                    self.node_done.emit(entry, size, 1)
            except OSError:
                continue

        self.finished.emit(grand_total)


class DiskUsageAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Disk Usage Analyzer")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._total = 0
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Disk Usage Analyzer")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Path selection
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Analyze:"))
        self._path_edit = QLineEdit(os.path.expanduser("~"))
        path_row.addWidget(self._path_edit, 1)

        quick_box = QComboBox()
        for label, path in [("Home", "~"), ("Root /", "/"), ("/var", "/var"),
                            ("/usr", "/usr"), ("/etc", "/etc")]:
            quick_box.addItem(label, path)
        quick_box.currentIndexChanged.connect(
            lambda i: self._path_edit.setText(os.path.expanduser(quick_box.itemData(i)))
        )
        path_row.addWidget(quick_box)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        self._stop_btn.clicked.connect(self._stop_scan)
        btn_row.addWidget(self._stop_btn)

        drill_btn = QPushButton("Drill Into Selected")
        drill_btn.clicked.connect(self._drill_down)
        btn_row.addWidget(drill_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Size", "Files", "% of Parent"])
        self._tree.setColumnWidth(0, 420)
        self._tree.setColumnWidth(1, 100)
        self._tree.setColumnWidth(2, 70)
        self._tree.setRootIsDecorated(False)
        self._tree.setSortingEnabled(False)
        root.addWidget(self._tree, 1)

        self._status = QLabel("Ready — pick a folder and press Scan")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Analyze Directory", self._path_edit.text())
        if path:
            self._path_edit.setText(path)

    def _start_scan(self):
        path = self._path_edit.text().strip()
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Path", f"'{path}' is not a directory.")
            return
        if any(path.startswith(s) for s in SKIP_DIRS):
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

    def _add_node(self, name, size, files):
        item = QTreeWidgetItem([name, fmt_size(size), str(files), ""])
        item.setData(0, Qt.UserRole, size)
        if size > 1024**3:
            item.setForeground(1, QBrush(QColor("#ff4444")))
        elif size > 100 * 1024**2:
            item.setForeground(1, QBrush(QColor("#ffaa00")))
        else:
            item.setForeground(1, QBrush(QColor("#00ff88")))
        self._tree.addTopLevelItem(item)
        self._total += size

    def _scan_done(self, total):
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status.setText(f"Total: {fmt_size(total)} in {self._tree.topLevelItemCount()} top-level entries")

        # Update % column with final total
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


def main():
    app = QApplication(sys.argv)
    win = DiskUsageAnalyzer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()