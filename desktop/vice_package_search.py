#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Package Search
Search and browse Debian APT repositories and Flathub packages with details and install options.
"""

import os
import shutil
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700


def _elevate_prefix():
    """Return privilege escalation command prefix for package mutations."""
    if os.geteuid() == 0:
        return []
    if shutil.which("pkexec"):
        return ["pkexec"]
    if shutil.which("sudo"):
        return ["sudo", "-n"]
    return ["pkexec"]


class SearchWorker(QThread):
    result = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, query, source):
        super().__init__()
        self.query = query
        self.source = source
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        results = []
        if not self._stop_requested and self.source in ("APT", "Both"):
            try:
                out = subprocess.check_output(
                    ["apt-cache", "search", "--names-only", self.query],
                    text=True, timeout=15
                )
                for line in out.splitlines():
                    if self._stop_requested:
                        break
                    if " - " in line:
                        name, desc = line.split(" - ", 1)
                        pkg_name = name.strip()
                        results.append({
                            "name": pkg_name,
                            "desc": desc.strip(),
                            "source": "APT",
                            "installed": self._apt_installed(pkg_name),
                            "version": "",
                        })
            except Exception as e:
                log_error(f"apt-cache search failed: {e}")

        if not self._stop_requested and self.source in ("Flatpak", "Both") and shutil.which("flatpak"):
            try:
                out = subprocess.check_output(
                    ["flatpak", "search", "--columns=application,name,description,version", self.query],
                    text=True, timeout=20
                )
                for line in out.splitlines()[1:]:
                    if self._stop_requested:
                        break
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

        if not self._stop_requested:
            self.result.emit(results)
        self.finished.emit()

    def _apt_installed(self, name):
        try:
            r = subprocess.run(["dpkg-query", "-W", "-f=${Status}", name], capture_output=True, text=True, timeout=3)
            return r.returncode == 0 and "install ok installed" in r.stdout
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
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            if self._stop_requested:
                return
            if self.source == "APT":
                out = subprocess.check_output(
                    ["apt-cache", "show", self.name],
                    text=True, timeout=10
                )
            else:
                if not shutil.which("flatpak"):
                    self.done.emit("Flatpak is not installed.")
                    return
                try:
                    out = subprocess.check_output(
                        ["flatpak", "info", self.name],
                        text=True, stderr=subprocess.DEVNULL, timeout=10
                    )
                except subprocess.CalledProcessError:
                    out = ""
                if not out and not self._stop_requested:
                    out = subprocess.check_output(
                        ["flatpak", "search", "--columns=application,name,description,version", self.name],
                        text=True, timeout=10
                    )
            if not self._stop_requested:
                self.done.emit(out[:3000])
        except Exception as e:
            if not self._stop_requested:
                self.done.emit(f"Could not fetch details: {e}")


class InstallWorker(QThread):
    line_out = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, name, source, remove=False):
        super().__init__()
        self.name = name
        self.source = source
        self.remove = remove
        self._stop_requested = False
        self._proc = None

    def stop(self):
        self._stop_requested = True
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        if self.source == "APT":
            action = "remove" if self.remove else "install"
            cmd = _elevate_prefix() + ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", action, "-y", self.name]
        else:
            if not shutil.which("flatpak"):
                self.line_out.emit("Error: flatpak is not installed.")
                self.finished.emit(False)
                return
            if self.remove:
                cmd = ["flatpak", "uninstall", "-y", self.name]
            else:
                cmd = ["flatpak", "install", "-y", "flathub", self.name]

        self.line_out.emit(f"$ {' '.join(cmd)}\n")
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            if self._proc.stdout is not None:
                for line in self._proc.stdout:
                    if self._stop_requested:
                        break
                    self.line_out.emit(line.rstrip())
            rc = self._proc.wait()
            if not self._stop_requested:
                self.finished.emit(rc == 0)
        except Exception as e:
            self.line_out.emit(f"Error: {e}")
            if not self._stop_requested:
                self.finished.emit(False)


class PackageSearch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Package Search")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(820, 520)
        vt.apply_app_theme(self)
        self._results = []
        self._workers = []
        self._search_worker = None
        self._detail_worker = None
        self._install_worker = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(vt.make_header(
            "Package Search",
            "Browse and manage Debian APT and Flatpak packages",
            icon_name="system-software-install",
            badge_text="APT / Flatpak",
            badge_variant="aqua",
            parent=self,
        ))

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search packages...")
        self._search_edit.returnPressed.connect(self._search)
        search_row.addWidget(self._search_edit)

        search_row.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItems(["Both", "APT", "Flatpak"])
        search_row.addWidget(self._source_combo)

        self._search_btn = vt.make_button("Search", variant="primary", parent=self)
        self._search_btn.clicked.connect(self._search)
        search_row.addWidget(self._search_btn)
        root.addLayout(search_row)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

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
        self._table.currentCellChanged.connect(lambda row, _c, _pr, _pc: self._on_selected(row))
        ll.addWidget(self._table)

        act_row = QHBoxLayout()
        self._install_btn = vt.make_button("Install", variant="primary", parent=self)
        self._install_btn.clicked.connect(self._install)
        act_row.addWidget(self._install_btn)
        self._remove_btn = vt.make_button("Remove", variant="danger", parent=self)
        self._remove_btn.clicked.connect(self._remove)
        act_row.addWidget(self._remove_btn)
        act_row.addStretch()
        ll.addLayout(act_row)
        splitter.addWidget(left)

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
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _track_worker(self, w):
        self._workers.append(w)
        w.finished.connect(lambda wk=w: self._prune_worker(wk))

    def _prune_worker(self, w):
        if w in self._workers:
            self._workers.remove(w)

    def _search(self):
        query = self._search_edit.text().strip()
        if not query:
            return
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.stop()
        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._table.setRowCount(0)
        self._results.clear()
        self._status.setText(f"Searching for '{query}'...")

        w = SearchWorker(query, self._source_combo.currentText())
        self._search_worker = w
        w.result.connect(lambda res, wk=w: self._on_results(res, wk))
        w.finished.connect(lambda wk=w: self._search_done(wk))
        self._track_worker(w)
        w.start()

    def _on_results(self, results, worker=None):
        if worker is not None and worker is not self._search_worker:
            return
        self._results = results
        self._table.setRowCount(0)
        for pkg in results:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(pkg["name"]))

            src_item = QTableWidgetItem(pkg["source"])
            src_color = vt.COLORS["accent_aqua"] if pkg["source"] == "APT" else vt.COLORS["accent_peach"]
            src_item.setForeground(QBrush(QColor(src_color)))
            self._table.setItem(row, 1, src_item)

            inst_item = QTableWidgetItem("Yes" if pkg["installed"] else "No")
            inst_color = vt.COLORS["success"] if pkg["installed"] else vt.COLORS["text_muted"]
            inst_item.setForeground(QBrush(QColor(inst_color)))
            self._table.setItem(row, 2, inst_item)

            self._table.setItem(row, 3, QTableWidgetItem(pkg["desc"]))

    def _search_done(self, worker=None):
        if worker is not None and worker is not self._search_worker:
            return
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status.setText(f"{len(self._results)} result(s) found")

    def _on_selected(self, row):
        if row < 0 or row >= len(self._results):
            return
        if self._detail_worker and self._detail_worker.isRunning():
            self._detail_worker.stop()
        pkg = self._results[row]
        self._detail_view.setPlainText("Loading details...")
        w = DetailWorker(pkg["name"], pkg["source"])
        self._detail_worker = w
        w.done.connect(lambda txt, wk=w: self._set_detail_text(txt, wk))
        self._track_worker(w)
        w.start()

    def _set_detail_text(self, text, worker):
        if worker is self._detail_worker:
            self._detail_view.setPlainText(text)

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
        if self._install_worker and self._install_worker.isRunning():
            QMessageBox.information(self, "Busy", "A package operation is already running.")
            return
        self._install_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log_view.clear()
        op = "Removing" if remove else "Installing"
        self._status.setText(f"{op}: {pkg['name']}...")

        w = InstallWorker(pkg["name"], pkg["source"], remove)
        self._install_worker = w
        w.line_out.connect(self._log_view.append)
        w.finished.connect(lambda ok: self._op_done(ok, pkg, remove))
        self._track_worker(w)
        w.start()

    def _op_done(self, ok, pkg, remove):
        self._install_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)
        self._progress.setVisible(False)
        op = "Remove" if remove else "Install"
        c = vt.COLORS["success"] if ok else vt.COLORS["danger"]
        result = "succeeded" if ok else "failed"
        if ok:
            pkg["installed"] = not remove
            for row, item in enumerate(self._results):
                if item is pkg:
                    inst_item = QTableWidgetItem("Yes" if pkg["installed"] else "No")
                    inst_color = vt.COLORS["success"] if pkg["installed"] else vt.COLORS["text_muted"]
                    inst_item.setForeground(QBrush(QColor(inst_color)))
                    self._table.setItem(row, 2, inst_item)
                    break
        self._log_view.append(f'<span style="color:{c};">[{op} {result.upper()}] {pkg["name"]}</span>')
        self._status.setText(f"{op} {result}: {pkg['name']}")
        log_info(f"Package {op} {result}: {pkg['name']}")

    def closeEvent(self, event):
        for w in list(self._workers):
            if hasattr(w, "stop"):
                w.stop()
            if w.isRunning():
                w.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = PackageSearch()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
