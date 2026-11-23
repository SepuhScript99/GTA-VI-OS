#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Update Manager.
APT update checker, upgrade staging, changelog preview, and system package maintenance.
"""

import os
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar,
    QAbstractItemView, QSplitter, QMessageBox
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
WINDOW_HEIGHT = 680


def _priv_cmd(cmd):
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if not is_root and shutil.which("pkexec"):
        return ["pkexec"] + list(cmd)
    return list(cmd)


class CheckWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, refresh_cache=False):
        super().__init__()
        self._refresh_cache = refresh_cache
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
        packages = []
        try:
            if self._refresh_cache and not self._stopped:
                self._proc = subprocess.Popen(
                    _priv_cmd(["apt-get", "update", "-qq"]),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                self._proc.communicate(timeout=60)
                self._proc = None
            if self._stopped:
                return
            self._proc = subprocess.Popen(
                ["apt", "list", "--upgradable", "--quiet=2"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            out, _ = self._proc.communicate(timeout=30)
            self._proc = None
            for line in (out or "").splitlines():
                if "/" not in line:
                    continue
                parts = line.split()
                name = parts[0].split("/")[0]
                new_ver = parts[1] if len(parts) > 1 else ""
                arch = parts[2] if len(parts) > 2 else ""
                old_ver = ""
                for idx, p in enumerate(parts):
                    if p.startswith("[upgradable") and idx + 2 < len(parts):
                        old_ver = parts[idx + 2].rstrip("]")
                        break
                packages.append({
                    "name": name, "new": new_ver,
                    "old": old_ver, "arch": arch,
                })
        except Exception as e:
            if not self._stopped:
                log_error(f"apt check failed: {e}")
        finally:
            self._proc = None
        if not self._stopped:
            self.done.emit(packages)


class UpgradeWorker(QThread):
    line_out = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, packages=None):
        super().__init__()
        self.packages = packages
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
        base = ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get"]
        if self.packages:
            cmd = _priv_cmd(base + ["install", "--only-upgrade", "-y"] + self.packages)
        else:
            cmd = _priv_cmd(base + ["upgrade", "-y"])
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
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


class ChangelogWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, pkg):
        super().__init__()
        self.pkg = pkg
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
                ["apt-get", "changelog", "--quiet", self.pkg],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            out, _ = self._proc.communicate(timeout=15)
            rc = self._proc.returncode
            self._proc = None
            if self._stopped:
                return
            if rc == 0 and (out or "").strip():
                self.done.emit(out[:3000])
                return
        except Exception:
            if self._proc is not None:
                self._proc.kill()
                self._proc.communicate()
                self._proc = None
        if self._stopped:
            return
        try:
            self._proc = subprocess.Popen(
                ["apt-cache", "show", self.pkg],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            out, _ = self._proc.communicate(timeout=10)
            if not self._stopped:
                self.done.emit((out or "").strip() or "No details available.")
        except Exception as e:
            if not self._stopped:
                self.done.emit(f"Could not fetch changelog: {e}")
        finally:
            self._proc = None


class UpdateManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Update Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        apply_app_theme(self)
        self._packages = []
        self._workers = []
        self._init_ui()
        self._check_updates(refresh_cache=False)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Update Manager",
            subtitle="Inspect pending Debian APT package upgrades and review changelogs",
            icon_name="system-software-update",
            badge_text="APT",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

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
        self._table.currentCellChanged.connect(lambda row, _c, _pr, _pc: self._on_pkg_selected(row))
        ll.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._check_btn = make_button("Refresh Updates", variant="secondary", parent=self)
        self._check_btn.clicked.connect(lambda: self._check_updates(refresh_cache=True))
        btn_row.addWidget(self._check_btn)

        self._upgrade_sel_btn = make_button("Upgrade Selected", variant="secondary", parent=self)
        self._upgrade_sel_btn.clicked.connect(self._upgrade_selected)
        btn_row.addWidget(self._upgrade_sel_btn)

        self._upgrade_all_btn = make_button("Upgrade All", variant="primary", parent=self)
        self._upgrade_all_btn.clicked.connect(self._upgrade_all)
        btn_row.addWidget(self._upgrade_all_btn)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

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
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _check_updates(self, refresh_cache=True):
        self._check_btn.setEnabled(False)
        self._upgrade_all_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Refreshing APT lists..." if refresh_cache else "Checking cached updates...")
        self._table.setRowCount(0)
        w = CheckWorker(refresh_cache=refresh_cache)
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
            new_item.setForeground(QBrush(QColor(COLORS["success"])))
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
        c = COLORS["success"] if ok else COLORS["danger"]
        result = "Upgrade complete" if ok else "Upgrade failed"
        self._log.append(f'<span style="color:{c}; font-weight:bold;">{result}</span>')
        self._status.setText(result)
        log_info(f"Upgrade: {result}")
        if ok:
            self._check_updates(refresh_cache=False)

    def closeEvent(self, event):
        for w in self._workers:
            w.stop()
        for w in self._workers:
            if w.isRunning():
                w.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = UpdateManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
