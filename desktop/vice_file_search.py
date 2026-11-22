#!/usr/bin/env python3
"""Vice OS — File Content Search. Recursive grep with regex, filters, and result preview."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QSplitter, QFileDialog, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 14px; height: 14px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""

MAX_FILE_SIZE = 5 * 1024 * 1024  # skip files > 5MB


class SearchWorker(QThread):
    """Searches files directly in Python (no grep dependency)."""
    result = pyqtSignal(str, int, str)   # path, line number, line
    progress = pyqtSignal(int)
    finished = pyqtSignal(int, int)       # matches, files scanned
    cancelled = pyqtSignal()

    def __init__(self, root, pattern, regex, case_sensitive, file_glob, max_depth, include_hidden):
        super().__init__()
        self._root = root
        self._pattern = pattern
        self._regex = regex
        self._case = case_sensitive
        self._glob = file_glob
        self._max_depth = max_depth
        self._hidden = include_hidden
        self._stop = False

    def stop(self):
        self._stop = True

    def _matches(self, text):
        try:
            if self._regex:
                import re
                flags = 0 if self._case else re.IGNORECASE
                return bool(re.search(self._pattern, text, flags))
            if self._case:
                return self._pattern in text
            return self._pattern.lower() in text.lower()
        except re.error:
            return False

    def _glob_matches(self, filename):
        if not self._glob:
            return True
        import fnmatch
        return fnmatch.fnmatch(filename, self._glob)

    def run(self):
        matches = 0
        scanned = 0
        base_depth = self._root.rstrip(os.sep).count(os.sep)

        for dirpath, dirnames, filenames in os.walk(self._root):
            if self._stop:
                break
            depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
            if self._max_depth > 0 and depth >= self._max_depth:
                dirnames[:] = []
                continue
            if not self._hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            for fname in filenames:
                if self._stop:
                    break
                if not self._hidden and fname.startswith("."):
                    continue
                if not self._glob_matches(fname):
                    continue
                path = os.path.join(dirpath, fname)
                try:
                    if os.path.getsize(path) > MAX_FILE_SIZE:
                        continue
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if self._stop:
                                break
                            if self._matches(line):
                                matches += 1
                                self.result.emit(path, lineno, line.rstrip())
                                if matches >= 1000:
                                    self.finished.emit(matches, scanned)
                                    return
                    scanned += 1
                    if scanned % 25 == 0:
                        self.progress.emit(scanned)
                except (OSError, PermissionError):
                    continue

        self.finished.emit(matches, scanned)


class FileSearch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — File Content Search")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — File Content Search")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Search params
        grid = QHBoxLayout()

        grid.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Text or regex to find...")
        self._search_edit.returnPressed.connect(self._start_search)
        grid.addWidget(self._search_edit, 1)

        grid.addWidget(QLabel("In:"))
        self._dir_edit = QLineEdit(os.path.expanduser("~"))
        grid.addWidget(self._dir_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        grid.addWidget(browse_btn)
        root.addLayout(grid)

        opts_row = QHBoxLayout()
        self._regex_cb = QCheckBox("Regex")
        opts_row.addWidget(self._regex_cb)
        self._case_cb = QCheckBox("Case sensitive")
        opts_row.addWidget(self._case_cb)
        self._hidden_cb = QCheckBox("Include hidden")
        opts_row.addWidget(self._hidden_cb)

        opts_row.addWidget(QLabel("File filter:"))
        self._glob_edit = QLineEdit()
        self._glob_edit.setPlaceholderText("*.py, *.txt, *.sh (empty = all)")
        self._glob_edit.setFixedWidth(220)
        opts_row.addWidget(self._glob_edit)

        opts_row.addWidget(QLabel("Max depth:"))
        self._depth_combo = QComboBox()
        self._depth_combo.addItems(["Unlimited", "1", "2", "3", "5", "10"])
        opts_row.addWidget(self._depth_combo)

        opts_row.addStretch()
        root.addLayout(opts_row)

        # Buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Search")
        self._start_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        self._start_btn.clicked.connect(self._start_search)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        self._stop_btn.clicked.connect(self._stop_search)
        btn_row.addWidget(self._stop_btn)

        export_btn = QPushButton("Export Results")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Results + preview
        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter, 1)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["File", "Line", "Content"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._table.setColumnWidth(0, 340)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellClicked.connect(self._preview_file)
        splitter.addWidget(self._table)

        preview_panel = QWidget()
        pv = QVBoxLayout(preview_panel)
        pv.setContentsMargins(0, 4, 0, 0)
        pv.addWidget(QLabel("File Preview:"))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        pv.addWidget(self._preview)
        splitter.addWidget(preview_panel)
        splitter.setSizes([420, 220])

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Search Directory", self._dir_edit.text())
        if path:
            self._dir_edit.setText(path)

    def _start_search(self):
        pattern = self._search_edit.text().strip()
        root_dir = self._dir_edit.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Missing Pattern", "Enter text to search for.")
            return
        if not os.path.isdir(root_dir):
            QMessageBox.warning(self, "Invalid Directory", f"'{root_dir}' is not a directory.")
            return

        depth_text = self._depth_combo.currentText()
        max_depth = int(depth_text) if depth_text != "Unlimited" else -1

        self._table.setRowCount(0)
        self._preview.clear()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.setText("Searching...")

        self._worker = SearchWorker(
            root_dir, pattern,
            self._regex_cb.isChecked(),
            self._case_cb.isChecked(),
            self._glob_edit.text().strip(),
            max_depth,
            self._hidden_cb.isChecked(),
        )
        self._worker.result.connect(self._add_result)
        self._worker.progress.connect(lambda n: self._status.setText(f"Searching... {n} files scanned"))
        self._worker.finished.connect(self._search_done)
        self._worker.start()

    def _stop_search(self):
        if self._worker:
            self._worker.stop()

    def _add_result(self, path, lineno, content):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(path))
        line_item = QTableWidgetItem(str(lineno))
        line_item.setForeground(QBrush(QColor("#ff00ff")))
        self._table.setItem(row, 1, line_item)
        self._table.setItem(row, 2, QTableWidgetItem(content[:200]))

    def _search_done(self, matches, scanned):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.setText(f"{matches} match(es) in {scanned} file(s)")
        log_info(f"Content search: {matches} matches in {scanned} files")

    def _preview_file(self, row, _col):
        path = self._table.item(row, 0).text()
        if not os.path.exists(path):
            self._preview.setPlainText("File no longer exists.")
            return
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read(100000)
            self._preview.setPlainText(content)
        except Exception as e:
            self._preview.setPlainText(f"Cannot read file: {e}")

    def _export(self):
        if self._table.rowCount() == 0:
            QMessageBox.information(self, "No Results", "Nothing to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Search Results",
            os.path.expanduser("~/vice_search_results.txt"), "Text (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                for row in range(self._table.rowCount()):
                    f.write(f"{self._table.item(row, 0).text()}:{self._table.item(row, 1).text()}: {self._table.item(row, 2).text()}\n")
            self._status.setText(f"Exported to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))


def main():
    app = QApplication(sys.argv)
    win = FileSearch()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()