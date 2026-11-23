#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Log Viewer
System log explorer for systemd journald and /var/log with real-time tail and regex filtering.
"""

import datetime
import os
import re
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700

LOG_SOURCES = {
    "Journal (all)": ["journalctl", "-n", "500", "--no-pager", "--output=short"],
    "Journal (errors)": ["journalctl", "-p", "err", "-n", "200", "--no-pager", "--output=short"],
    "Journal (kernel)": ["journalctl", "-k", "-n", "200", "--no-pager", "--output=short"],
    "Journal (boot)": ["journalctl", "-b", "-n", "300", "--no-pager", "--output=short"],
    "syslog": ["tail", "-n", "500", "/var/log/syslog"],
    "auth.log": ["tail", "-n", "300", "/var/log/auth.log"],
    "dpkg.log": ["tail", "-n", "300", "/var/log/dpkg.log"],
    "Xorg.0.log": ["tail", "-n", "300", "/var/log/Xorg.0.log"],
    "dmesg": ["dmesg", "--human", "-T"],
}


def _level_colors():
    return {
        "error": vt.COLORS["danger"],
        "err": vt.COLORS["danger"],
        "crit": "#FF3D5A",
        "alert": "#FF3D5A",
        "emerg": "#FF3D5A",
        "warn": vt.COLORS["warning"],
        "warning": vt.COLORS["warning"],
        "notice": vt.COLORS["accent_gold"],
        "info": vt.COLORS["accent_aqua"],
        "debug": vt.COLORS["text_muted"],
    }


class LogWorker(QThread):
    lines_ready = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self.cmd = list(cmd)
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            lines = []
            if self._proc.stdout:
                for line in self._proc.stdout:
                    if self._cancelled:
                        break
                    lines.append(line.rstrip())
            self._proc.wait()
            if not self._cancelled:
                self.lines_ready.emit(lines)
        except Exception as e:
            if not self._cancelled:
                self.lines_ready.emit([f"Error: {e}"])
        if not self._cancelled:
            self.finished.emit()


class LogViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Log Viewer")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(820, 540)
        vt.apply_app_theme(self)
        self._all_lines = []
        self._worker = None
        self._sources = dict(LOG_SOURCES)
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(5000)
        self._follow_timer.timeout.connect(self._load_log)
        self._init_ui()
        self._load_log()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Log Viewer",
            "Explore systemd journald and /var/log streams with regex & severity filters",
            icon_name="utilities-log-viewer",
            badge_text="LOGS",
            badge_variant="aqua",
            parent=self,
        ))

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        for name in self._sources:
            self._source_combo.addItem(name)
        self._source_combo.currentIndexChanged.connect(self._load_log)
        ctrl.addWidget(self._source_combo)

        self._open_btn = vt.make_button("Open File", "secondary", parent=self)
        self._open_btn.clicked.connect(self._open_file)
        ctrl.addWidget(self._open_btn)

        ctrl.addStretch()

        self._follow_cb = QCheckBox("Follow")
        self._follow_cb.toggled.connect(self._toggle_follow)
        ctrl.addWidget(self._follow_cb)

        self._wrap_cb = QCheckBox("Wrap")
        self._wrap_cb.toggled.connect(
            lambda on: self._log_view.setLineWrapMode(
                QTextEdit.WidgetWidth if on else QTextEdit.NoWrap
            )
        )
        ctrl.addWidget(self._wrap_cb)
        root.addLayout(ctrl)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter lines (regex supported)...")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search)

        self._case_cb = QCheckBox("Case sensitive")
        self._case_cb.toggled.connect(self._apply_filter)
        search_row.addWidget(self._case_cb)

        self._level_combo = QComboBox()
        self._level_combo.addItems(["All levels", "error/crit", "warning", "info", "debug"])
        self._level_combo.currentIndexChanged.connect(self._apply_filter)
        search_row.addWidget(self._level_combo)
        root.addLayout(search_row)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QTextEdit.NoWrap)
        root.addWidget(self._log_view)

        bottom = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        bottom.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        bottom.addWidget(self._status)

        bottom.addStretch()

        clear_btn = vt.make_button("Clear", "secondary", parent=self)
        clear_btn.clicked.connect(self._log_view.clear)
        bottom.addWidget(clear_btn)

        export_btn = vt.make_button("Export", "primary", parent=self)
        export_btn.clicked.connect(self._export)
        bottom.addWidget(export_btn)
        root.addLayout(bottom)

    def _load_log(self):
        name = self._source_combo.currentText()
        cmd = self._sources.get(name)
        if not cmd:
            return
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        self._progress.setVisible(True)
        self._status.setText(f"Loading: {name}")
        w = LogWorker(cmd, parent=self)
        w.lines_ready.connect(self._on_lines)
        w.finished.connect(lambda: self._progress.setVisible(False))
        self._worker = w
        w.start()

    def _on_lines(self, lines):
        self._all_lines = lines
        self._apply_filter()
        self._status.setText(f"{len(lines)} lines loaded")

    def _apply_filter(self):
        search = self._search.text()
        level_filter = self._level_combo.currentText()
        flags = 0 if self._case_cb.isChecked() else re.IGNORECASE

        level_keywords = {
            "error/crit": ["error", "err", "crit", "alert", "emerg"],
            "warning": ["warn", "warning"],
            "info": ["info", "notice"],
            "debug": ["debug"],
        }

        filtered = self._all_lines
        if level_filter != "All levels":
            keywords = level_keywords.get(level_filter, [])
            filtered = [line for line in filtered if any(k in line.lower() for k in keywords)]

        if search:
            try:
                pat = re.compile(search, flags)
                filtered = [line for line in filtered if pat.search(line)]
            except re.error:
                filtered = [
                    line for line in filtered
                    if (search in line if self._case_cb.isChecked() else search.lower() in line.lower())
                ]

        self._render(filtered)

    def _render(self, lines):
        self._log_view.clear()
        cursor = self._log_view.textCursor()
        fmt_default = QTextCharFormat()
        fmt_default.setForeground(QColor(vt.COLORS["text_primary"]))
        colors = _level_colors()

        for line in lines:
            fmt = QTextCharFormat(fmt_default)
            lower = line.lower()
            for keyword, color in colors.items():
                if keyword in lower:
                    fmt.setForeground(QColor(color))
                    break
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(line + "\n", fmt)

        if self._follow_cb.isChecked():
            self._log_view.moveCursor(QTextCursor.End)

        self._status.setText(f"Showing {len(lines)} lines")

    def _toggle_follow(self, on):
        if on:
            self._follow_timer.start()
        else:
            self._follow_timer.stop()

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Log File", "/var/log", "Log files (*.log *.txt *);;All files (*)"
        )
        if not path:
            return
        name = f"File: {os.path.basename(path)}"
        self._sources[name] = ["tail", "-n", "1000", path]
        if self._source_combo.findText(name) < 0:
            self._source_combo.addItem(name)
        self._source_combo.setCurrentText(name)

    def _export(self):
        path = os.path.expanduser(
            f"~/vice_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._log_view.toPlainText())
            log_info(f"Log exported to {path}")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")

    def closeEvent(self, event):
        self._follow_timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = LogViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
