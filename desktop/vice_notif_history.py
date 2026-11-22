#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Notification History
Browse, filter, search, and clear past desktop notifications captured by the notification daemon.
"""

import sys
import os
import json
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/notification_history.json")
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 520
MAX_HISTORY = 200

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QLabel { color: #00ffff; }
"""

URGENCY_COLORS = {
    "critical": "#ff4444",
    "normal":   "#00ffff",
    "low":      "#888888",
}


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(entries):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(entries[-MAX_HISTORY:], f, indent=2)
    except Exception as e:
        log_error(f"Failed to save notification history: {e}")


def append_notification(summary, body, urgency="normal", app=""):
    entries = load_history()
    entries.append({
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "body": body,
        "urgency": urgency,
        "app": app,
        "dismissed": False,
    })
    save_history(entries)


class NotificationHistory(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Notification History")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._entries = []
        self._init_ui()
        self._load()

        self._timer = QTimer()
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self._load)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Notification History")
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff;")
        header.addWidget(title)
        header.addStretch()

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #888;")
        header.addWidget(self._count_label)
        root.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Time", "App", "Summary", "Body", "Urgency"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            self._table.styleSheet() +
            "QTableWidget { alternate-background-color: #111; }"
        )
        root.addWidget(self._table)

        btn_row = QHBoxLayout()
        dismiss_btn = QPushButton("Dismiss Selected")
        dismiss_btn.clicked.connect(self._dismiss_selected)
        btn_row.addWidget(dismiss_btn)

        dismiss_all_btn = QPushButton("Dismiss All")
        dismiss_all_btn.clicked.connect(self._dismiss_all)
        btn_row.addWidget(dismiss_all_btn)

        clear_btn = QPushButton("Clear All History")
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load)
        btn_row.addWidget(refresh_btn)

        root.addLayout(btn_row)

    def _load(self):
        self._entries = load_history()
        self._populate()

    def _populate(self):
        self._table.setRowCount(0)
        for entry in reversed(self._entries):
            row = self._table.rowCount()
            self._table.insertRow(row)

            ts = entry.get("timestamp", "")
            app = entry.get("app", "")
            summary = entry.get("summary", "")
            body = entry.get("body", "")
            urgency = entry.get("urgency", "normal")
            dismissed = entry.get("dismissed", False)

            color = URGENCY_COLORS.get(urgency, "#00ffff")
            if dismissed:
                color = "#444444"

            for col, val in enumerate([ts, app, summary, body, urgency]):
                item = QTableWidgetItem(val)
                item.setForeground(QBrush(QColor(color)))
                self._table.setItem(row, col, item)

        total = len(self._entries)
        dismissed = sum(1 for e in self._entries if e.get("dismissed"))
        self._count_label.setText(f"{total} total  |  {dismissed} dismissed")

    def _dismiss_selected(self):
        rows = set(i.row() for i in self._table.selectedItems())
        if not rows:
            return
        visible_indices = list(range(len(self._entries) - 1, -1, -1))
        for row in rows:
            if row < len(visible_indices):
                self._entries[visible_indices[row]]["dismissed"] = True
        save_history(self._entries)
        self._populate()
        log_info(f"Dismissed {len(rows)} notification(s)")

    def _dismiss_all(self):
        for entry in self._entries:
            entry["dismissed"] = True
        save_history(self._entries)
        self._populate()
        log_info("Dismissed all notifications")

    def _clear_all(self):
        if QMessageBox.question(
            self, "Clear History",
            "Delete all notification history?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._entries = []
        save_history([])
        self._populate()
        log_info("Notification history cleared")


def main():
    app = QApplication(sys.argv)
    win = NotificationHistory()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
