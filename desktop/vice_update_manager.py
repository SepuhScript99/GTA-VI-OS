#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Update Manager
APT update checker, upgrade staging, changelog preview, and system package maintenance.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar,
    QAbstractItemView, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTextEdit { background: #0d0d0d; color: #00e5ff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
QLabel { color: #00ffff; }
"""


class CheckWorker(QThread):
    done = pyqtSignal(list)

    def run(self):
        packages = []
        try:
            subprocess.run(["sudo", "apt", "update", "-qq"],
                           capture_output=True, timeout=60)
            out = subprocess.check_output(
                ["apt", "list", "--upgradable", "--quiet=2"],
                stderr=subprocess.DEVNULL, text=True, timeout=30
            )
            for line in out.splitlines():
                if "/" not in line:
                    continue
                parts = line.split()
                name = parts[0].split("/")[0]
                new_ver = parts[1] if len(parts) > 1 else ""
                arch = parts[2] if len(parts) > 2 else ""
                old_ver = ""
                for p in parts:
                    if p.startswith("[upgradable"):
                        idx = parts.index(p)
                        if idx + 2 < len(parts):
                            old_ver = parts[idx + 2].rstrip("]")
                packages.append({
                    "name": name, "new": new_ver,
                    "old": old_ver, "arch": arch
                })
        except Exception as e:
            log_error(f"apt check failed: {e}")
        self.done.emit(packages)


class UpgradeWorker(QThread):
    line_out = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, packages=None):
        super().__init__()
        self.packages = packages

    def run(self):
        if self.packages:
            cmd = ["sudo", "apt", "install", "--only-upgrade", "-y"] + self.packages
        else:
            cmd = ["sudo", "apt", "upgrade", "-y"]
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


class ChangelogWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, pkg):
        super().__init__()
        self.pkg = pkg

    def run(self):
        try:
            out = subprocess.check_output(
                ["apt-get", "changelog", "--quiet", self.pkg],
                stderr=subprocess.DEVNULL, text=True, timeout=15
            )
            self.done.emit(out[:3000])
        except Exception:
            try:
                out = subprocess.check_output(
                    ["apt", "show", self.pkg],
                    stderr=subprocess.DEVNULL, text=True, timeout=10
                )
                self.done.emit(out)
            except Exception as e:
                self.done.emit(f"Could not fetch changelog: {e}")


class UpdateManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Update Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._packages = []
        self._workers = []
        self._init_ui()
        self._check_updates()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Update Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: package list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Package", "Current", "New Version", "Arch"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_pkg_selected)
        ll.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._check_btn = QPushButton("Check Updates")
        self._check_btn.clicked.connect(self._check_updates)
        btn_row.addWidget(self._check_btn)

        self._upgrade_sel_btn = QPushButton("Upgrade Selected")
        self._upgrade_sel_btn.clicked.connect(self._upgrade_selected)
        btn_row.addWidget(self._upgrade_sel_btn)

        self._upgrade_all_btn = QPushButton("Upgrade All")
        self._upgrade_all_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        self._upgrade_all_btn.clicked.connect(self._upgrade_all)
        btn_row.addWidget(self._upgrade_all_btn)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # Right: changelog + output log
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        rl.addWidget(QLabel("Changelog / Details:"))
        self._changelog = QTextEdit()
        self._changelog.setReadOnly(True)
        rl.addWidget(self._changelog)

        rl.addWidget(QLabel("Install Output:"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        rl.addWidget(self._log)
        splitter.addWidget(right)
        splitter.setSizes([460, 520])

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _check_updates(self):
        self._check_btn.setEnabled(False)
        self._upgrade_all_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Checking for updates...")
        self._table.setRowCount(0)
        w = CheckWorker()
        w.done.connect(self._on_check_done)
        w.start()
        self._workers.append(w)

    def _on_check_done(self, packages):
        self._packages = packages
        self._table.setRowCount(0)
        for p in packages:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(p["old"]))
            new_item = QTableWidgetItem(p["new"])
            new_item.setForeground(QBrush(QColor("#00ff88")))
            self._table.setItem(row, 2, new_item)
            self._table.setItem(row, 3, QTableWidgetItem(p["arch"]))

        self._progress.setVisible(False)
        self._check_btn.setEnabled(True)
        self._upgrade_all_btn.setEnabled(len(packages) > 0)
        count = len(packages)
        self._status.setText(f"{count} update(s) available" if count else "System is up to date")
        log_info(f"Update check: {count} packages upgradable")

    def _on_pkg_selected(self, row):
        if row < 0 or row >= len(self._packages):
            return
        pkg = self._packages[row]["name"]
        self._changelog.setPlainText("Loading changelog...")
        w = ChangelogWorker(pkg)
        w.done.connect(self._changelog.setPlainText)
        w.start()
        self._workers.append(w)

    def _upgrade_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a package to upgrade.")
            return
        pkg = self._packages[row]["name"]
        self._run_upgrade([pkg], f"Upgrading {pkg}...")

    def _upgrade_all(self):
        if not self._packages:
            return
        if QMessageBox.question(
            self, "Upgrade All",
            f"Upgrade all {len(self._packages)} package(s)?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_upgrade(None, f"Upgrading {len(self._packages)} package(s)...")

    def _run_upgrade(self, packages, msg):
        self._check_btn.setEnabled(False)
        self._upgrade_all_btn.setEnabled(False)
        self._upgrade_sel_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.clear()
        self._status.setText(msg)
        w = UpgradeWorker(packages)
        w.line_out.connect(self._log.append)
        w.finished.connect(self._upgrade_done)
        w.start()
        self._workers.append(w)

    def _upgrade_done(self, ok):
        self._progress.setVisible(False)
        self._check_btn.setEnabled(True)
        self._upgrade_sel_btn.setEnabled(True)
        c = "#00ff88" if ok else "#ff4444"
        result = "Upgrade complete" if ok else "Upgrade failed"
        self._log.append(f'<span style="color:{c}; font-weight:bold;">{result}</span>')
        self._status.setText(result)
        log_info(f"Upgrade: {result}")
        if ok:
            self._check_updates()


def main():
    app = QApplication(sys.argv)
    win = UpdateManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
