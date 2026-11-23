#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Notification History
Browse, filter, search, and clear past desktop notifications captured by the notification daemon.
"""

import datetime
import json
import os
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/notification_history.json")
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 540
MAX_HISTORY = 200

URGENCY_COLORS = {
    "critical": vt.COLORS["danger"],
    "normal": vt.COLORS["accent_aqua"],
    "low": vt.COLORS["text_muted"],
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
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(640, 400)
        vt.apply_app_theme(self)
        self._entries = []
        self._init_ui()
        self._load()

        self._timer = QTimer(self)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self._load)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = vt.make_header(
            "Notification History",
            "Review and dismiss recent desktop notifications",
            icon_name="preferences-desktop-notification",
            badge_text="0 total",
            badge_variant="aqua",
            parent=self,
        )
        self._header = header
        root.addWidget(header)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._count_label)

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
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        dismiss_btn = vt.make_button("Dismiss Selected", variant="secondary", parent=self)
        dismiss_btn.clicked.connect(self._dismiss_selected)
        btn_row.addWidget(dismiss_btn)

        dismiss_all_btn = vt.make_button("Dismiss All", variant="secondary", parent=self)
        dismiss_all_btn.clicked.connect(self._dismiss_all)
        btn_row.addWidget(dismiss_all_btn)

        clear_btn = vt.make_button("Clear All History", variant="danger", parent=self)
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        refresh_btn = vt.make_button("Refresh", variant="primary", parent=self)
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

            color = URGENCY_COLORS.get(urgency, vt.COLORS["accent_aqua"])
            if dismissed:
                color = vt.COLORS["text_muted"]

            for col, val in enumerate([ts, app, summary, body, urgency]):
                item = QTableWidgetItem(str(val))
                item.setForeground(QBrush(QColor(color)))
                self._table.setItem(row, col, item)

        total = len(self._entries)
        dismissed = sum(1 for e in self._entries if e.get("dismissed"))
        self._count_label.setText(f"{total} total  |  {dismissed} dismissed")
        self._header.set_badge(f"{total} total", "aqua")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)

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
