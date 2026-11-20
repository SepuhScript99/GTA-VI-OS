#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Package Search
Search and browse Debian APT repositories and Flathub packages with details and install options.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QTextEdit,
    QComboBox, QProgressBar, QAbstractItemView, QSplitter, QTabWidget,
    QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
QLabel { color: #00ffff; }
"""


class SearchWorker(QThread):
    result = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, query, source):
        super().__init__()
        self.query = query
        self.source = source

    def run(self):
        results = []
        if self.source in ("APT", "Both"):
            try:
                out = subprocess.check_output(
                    ["apt-cache", "search", "--names-only", self.query],
                    text=True, timeout=15
                )
                for line in out.splitlines():
                    if " - " in line:
                        name, desc = line.split(" - ", 1)
                        results.append({
                            "name": name.strip(),
                            "desc": desc.strip(),
                            "source": "APT",
                            "installed": self._apt_installed(name.strip()),
                            "version": "",
                        })
            except Exception as e:
                log_error(f"apt-cache search failed: {e}")

        if self.source in ("Flatpak", "Both"):
            try:
                out = subprocess.check_output(
                    ["flatpak", "search", "--columns=application,name,description,version", self.query],
                    text=True, timeout=20
                )
                for line in out.splitlines()[1:]:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        app_id = parts[0].strip()
                        name = parts[1].strip()
                        desc = parts[2].strip() if len(parts) > 2 else ""
                        ver = parts[3].strip() if len(parts) > 3 else ""
                        results.append({
                            "name": app_id,
                            "desc": f"{name} — {desc}",
                            "source": "Flatpak",
                            "installed": self._flatpak_installed(app_id),
                            "version": ver,
                        })
            except Exception as e:
                log_error(f"flatpak search failed: {e}")

        self.result.emit(results)
        self.finished.emit()

    def _apt_installed(self, name):
        try:
            r = subprocess.run(["dpkg", "-l", name], capture_output=True, text=True, timeout=3)
            return "ii" in r.stdout
        except Exception:
            return False

    def _flatpak_installed(self, app_id):
        try:
            r = subprocess.run(["flatpak", "info", app_id], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False


class DetailWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, name, source):
        super().__init__()
        self.name = name
        self.source = source

    def run(self):
        try:
            if self.source == "APT":
                out = subprocess.check_output(
                    ["apt-cache", "show", self.name],
                    text=True, timeout=10
                )
            else:
                out = subprocess.check_output(
                    ["flatpak", "info", self.name],
                    text=True, stderr=subprocess.DEVNULL, timeout=10
                )
                if not out:
                    out = subprocess.check_output(
                        ["flatpak", "search", "--columns=application,name,description,version", self.name],
                        text=True, timeout=10
                    )
            self.done.emit(out[:3000])
        except Exception as e:
            self.done.emit(f"Could not fetch details: {e}")


class InstallWorker(QThread):
    line_out = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, name, source, remove=False):
        super().__init__()
        self.name = name
        self.source = source
        self.remove = remove

    def run(self):
        if self.source == "APT":
            if self.remove:
                cmd = ["sudo", "apt", "remove", "-y", self.name]
            else:
                cmd = ["sudo", "apt", "install", "-y", self.name]
        else:
            if self.remove:
                cmd = ["flatpak", "uninstall", "-y", self.name]
            else:
                cmd = ["flatpak", "install", "-y", "flathub", self.name]

        self.line_out.emit(f"$ {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self.line_out.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode == 0)
        except Exception as e:
            self.line_out.emit(f"Error: {e}")
            self.finished.emit(False)


class PackageSearch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Package Search")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._results = []
        self._workers = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Package Search")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Search bar
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search packages...")
        self._search_edit.returnPressed.connect(self._search)
        search_row.addWidget(self._search_edit)

        search_row.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItems(["Both", "APT", "Flatpak"])
        search_row.addWidget(self._source_combo)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._search)
        search_row.addWidget(self._search_btn)
        root.addLayout(search_row)

        # Main splitter: results | detail
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: results table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Package", "Source", "Installed", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_selected)
        ll.addWidget(self._table)

        act_row = QHBoxLayout()
        self._install_btn = QPushButton("Install")
        self._install_btn.clicked.connect(self._install)
        act_row.addWidget(self._install_btn)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        self._remove_btn.clicked.connect(self._remove)
        act_row.addWidget(self._remove_btn)
        act_row.addStretch()
        ll.addLayout(act_row)
        splitter.addWidget(left)

        # Right: detail + log
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        right_tabs = QTabWidget()

        self._detail_view = QTextEdit()
        self._detail_view.setReadOnly(True)
        right_tabs.addTab(self._detail_view, "Details")

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        right_tabs.addTab(self._log_view, "Install Log")

        rl.addWidget(right_tabs)
        splitter.addWidget(right)
        splitter.setSizes([560, 520])

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("Enter a search term and press Search")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _search(self):
        query = self._search_edit.text().strip()
        if not query:
            return
        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._table.setRowCount(0)
        self._results.clear()
        self._status.setText(f"Searching for '{query}'...")

        w = SearchWorker(query, self._source_combo.currentText())
        w.result.connect(self._on_results)
        w.finished.connect(self._search_done)
        w.start()
        self._workers.append(w)

    def _on_results(self, results):
        self._results = results
        self._table.setRowCount(0)
        for pkg in results:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(pkg["name"]))

            src_item = QTableWidgetItem(pkg["source"])
            src_item.setForeground(QBrush(QColor("#00ffff" if pkg["source"] == "APT" else "#ff00ff")))
            self._table.setItem(row, 1, src_item)

            inst_item = QTableWidgetItem("Yes" if pkg["installed"] else "No")
            inst_item.setForeground(QBrush(QColor("#00ff88" if pkg["installed"] else "#888")))
            self._table.setItem(row, 2, inst_item)

            self._table.setItem(row, 3, QTableWidgetItem(pkg["desc"]))

    def _search_done(self):
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status.setText(f"{len(self._results)} result(s) found")

    def _on_selected(self, row):
        if row < 0 or row >= len(self._results):
            return
        pkg = self._results[row]
        self._detail_view.setPlainText("Loading details...")
        w = DetailWorker(pkg["name"], pkg["source"])
        w.done.connect(self._detail_view.setPlainText)
        w.start()
        self._workers.append(w)

    def _selected_pkg(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._results):
            QMessageBox.warning(self, "No Selection", "Select a package first.")
            return None
        return self._results[row]

    def _install(self):
        pkg = self._selected_pkg()
        if not pkg:
            return
        if QMessageBox.question(
            self, "Install", f"Install {pkg['name']}?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_op(pkg, remove=False)

    def _remove(self):
        pkg = self._selected_pkg()
        if not pkg:
            return
        if not pkg["installed"]:
            QMessageBox.information(self, "Not Installed", f"{pkg['name']} is not installed.")
            return
        if QMessageBox.question(
            self, "Remove", f"Remove {pkg['name']}?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_op(pkg, remove=True)

    def _run_op(self, pkg, remove):
        self._install_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log_view.clear()
        op = "Removing" if remove else "Installing"
        self._status.setText(f"{op}: {pkg['name']}...")

        w = InstallWorker(pkg["name"], pkg["source"], remove)
        w.line_out.connect(self._log_view.append)
        w.finished.connect(lambda ok: self._op_done(ok, pkg, remove))
        w.start()
        self._workers.append(w)

    def _op_done(self, ok, pkg, remove):
        self._install_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)
        self._progress.setVisible(False)
        op = "Remove" if remove else "Install"
        c = "#00ff88" if ok else "#ff4444"
        result = "succeeded" if ok else "failed"
        self._log_view.append(f'<span style="color:{c};">[{op} {result.upper()}] {pkg["name"]}</span>')
        self._status.setText(f"{op} {result}: {pkg['name']}")
        log_info(f"Package {op} {result}: {pkg['name']}")


def main():
    app = QApplication(sys.argv)
    win = PackageSearch()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
