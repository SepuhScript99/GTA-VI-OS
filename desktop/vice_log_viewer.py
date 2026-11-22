#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Log Viewer
System log explorer for systemd journald and /var/log with real-time tail and regex filtering.
"""

import sys
import os
import subprocess
import glob

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QSplitter, QListWidget,
    QListWidgetItem, QFileDialog, QProgressBar, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700

LOG_SOURCES = {
    "Journal (all)":     ["journalctl", "-n", "500", "--no-pager", "--output=short"],
    "Journal (errors)":  ["journalctl", "-p", "err", "-n", "200", "--no-pager", "--output=short"],
    "Journal (kernel)":  ["journalctl", "-k", "-n", "200", "--no-pager", "--output=short"],
    "Journal (boot)":    ["journalctl", "-b", "-n", "300", "--no-pager", "--output=short"],
    "syslog":            ["tail", "-n", "500", "/var/log/syslog"],
    "auth.log":          ["tail", "-n", "300", "/var/log/auth.log"],
    "dpkg.log":          ["tail", "-n", "300", "/var/log/dpkg.log"],
    "Xorg.0.log":        ["tail", "-n", "300", "/var/log/Xorg.0.log"],
    "dmesg":             ["dmesg", "--human", "-T"],
}

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #333; margin-top: 8px; padding: 4px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 13px; height: 13px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""

LEVEL_COLORS = {
    "error":   "#ff4444",
    "err":     "#ff4444",
    "crit":    "#ff0000",
    "alert":   "#ff0000",
    "emerg":   "#ff0000",
    "warn":    "#ffaa00",
    "warning": "#ffaa00",
    "notice":  "#ffff00",
    "info":    "#00ffff",
    "debug":   "#888888",
}


class LogWorker(QThread):
    lines_ready = pyqtSignal(list)
    finished    = pyqtSignal()

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            lines = []
            for line in proc.stdout:
                lines.append(line.rstrip())
            proc.wait()
            self.lines_ready.emit(lines)
        except Exception as e:
            self.lines_ready.emit([f"Error: {e}"])
        self.finished.emit()


class LogViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Log Viewer")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._all_lines = []
        self._worker = None
        self._follow_timer = QTimer()
        self._follow_timer.setInterval(5000)
        self._follow_timer.timeout.connect(self._load_log)
        self._init_ui()
        self._load_log()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Log Viewer")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 4px;")
        root.addWidget(title)

        # Controls
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        for name in LOG_SOURCES:
            self._source_combo.addItem(name)
        self._source_combo.currentIndexChanged.connect(self._load_log)
        ctrl.addWidget(self._source_combo)

        self._open_btn = QPushButton("Open File")
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

        # Search bar
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

        # Log view
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QTextEdit.NoWrap)
        root.addWidget(self._log_view)

        # Bottom bar
        bottom = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        bottom.addWidget(self._progress)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        bottom.addWidget(self._status)

        bottom.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._log_view.clear)
        bottom.addWidget(clear_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        bottom.addWidget(export_btn)

        root.addLayout(bottom)

    def _load_log(self):
        name = self._source_combo.currentText()
        cmd = LOG_SOURCES.get(name)
        if not cmd:
            return
        self._progress.setVisible(True)
        self._status.setText(f"Loading: {name}")
        w = LogWorker(cmd)
        w.lines_ready.connect(self._on_lines)
        w.finished.connect(lambda: self._progress.setVisible(False))
        w.start()
        self._worker = w

    def _on_lines(self, lines):
        self._all_lines = lines
        self._apply_filter()
        self._status.setText(f"{len(lines)} lines loaded")

    def _apply_filter(self):
        import re
        search = self._search.text()
        level_filter = self._level_combo.currentText()
        flags = 0 if self._case_cb.isChecked() else re.IGNORECASE

        level_keywords = {
            "error/crit": ["error", "err", "crit", "alert", "emerg"],
            "warning":    ["warn", "warning"],
            "info":       ["info", "notice"],
            "debug":      ["debug"],
        }

        filtered = self._all_lines

        if level_filter != "All levels":
            keywords = level_keywords.get(level_filter, [])
            filtered = [l for l in filtered
                        if any(k in l.lower() for k in keywords)]

        if search:
            try:
                pat = re.compile(search, flags)
                filtered = [l for l in filtered if pat.search(l)]
            except re.error:
                filtered = [l for l in filtered
                            if (search in l if self._case_cb.isChecked()
                                else search.lower() in l.lower())]

        self._render(filtered)

    def _render(self, lines):
        self._log_view.clear()
        cursor = self._log_view.textCursor()
        fmt_default = QTextCharFormat()
        fmt_default.setForeground(QColor("#aaffff"))

        for line in lines:
            fmt = QTextCharFormat(fmt_default)
            lower = line.lower()
            for keyword, color in LEVEL_COLORS.items():
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
        path, _ = QFileDialog.getOpenFileName(self, "Open Log File", "/var/log", "Log files (*.log *.txt *);;All files (*)")
        if not path:
            return
        name = os.path.basename(path)
        LOG_SOURCES[f"File: {name}"] = ["tail", "-n", "1000", path]
        self._source_combo.addItem(f"File: {name}")
        self._source_combo.setCurrentText(f"File: {name}")

    def _export(self):
        import datetime
        path = os.path.expanduser(
            f"~/vice_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        try:
            with open(path, "w") as f:
                f.write(self._log_view.toPlainText())
            log_info(f"Log exported to {path}")
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            log_error(f"Export failed: {e}")


def main():
    app = QApplication(sys.argv)
    win = LogViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
