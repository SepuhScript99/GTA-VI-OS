#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Clipboard History Manager
Tracks clipboard history with pinning, persistent storage, search, and context menu actions.
"""

import datetime
import json
import os
import sys

from PyQt5.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 600
HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/clipboard_history.json")
MAX_ENTRIES = 200


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
            json.dump(entries[-MAX_ENTRIES:], f, indent=2)
    except Exception as e:
        log_error(f"Clipboard save failed: {e}")


class ClipboardWatcher(QObject):
    """GUI-thread clipboard watcher using QTimer (X11-safe)."""
    new_content = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._last = ""
        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._check)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _check(self):
        cb = self._app.clipboard()
        if cb is None:
            return
        text = cb.text()
        if text and text != self._last:
            self._last = text
            self.new_content.emit(text)


class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Clipboard Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(480, 440)
        vt.apply_app_theme(self)
        self._entries = load_history()
        self._watcher = None
        self._init_ui()
        self._populate()
        self._start_watcher()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(vt.make_header(
            "Clipboard Manager",
            "Search, pin, and restore copied clipboard history",
            icon_name="edit-paste",
            badge_text="History",
            badge_variant="peach",
            parent=self,
        ))

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter clipboard history...")
        self._search.textChanged.connect(self._populate)
        search_row.addWidget(self._search)
        root.addLayout(search_row)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.itemDoubleClicked.connect(self._paste_item)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        root.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        paste_btn = vt.make_button("Paste Selected", variant="primary", parent=self)
        paste_btn.clicked.connect(self._paste_selected)
        btn_row.addWidget(paste_btn)

        pin_btn = vt.make_button("Pin / Unpin", variant="secondary", parent=self)
        pin_btn.clicked.connect(self._toggle_pin)
        btn_row.addWidget(pin_btn)

        del_btn = vt.make_button("Delete", variant="secondary", parent=self)
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)

        clear_btn = vt.make_button("Clear All", variant="danger", parent=self)
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)
        root.addLayout(btn_row)

        self._status = QLabel(f"{len(self._entries)} item(s)")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _populate(self):
        search = self._search.text().lower()
        self._list.clear()
        pinned = [e for e in self._entries if e.get("pinned")]
        unpinned = [e for e in self._entries if not e.get("pinned")]
        for entry in pinned + list(reversed(unpinned)):
            text = entry.get("text", "")
            if search and search not in text.lower():
                continue
            preview = text.replace("\n", " ").replace("\t", " ")[:80]
            label = f"[PIN] {preview}" if entry.get("pinned") else preview
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            if entry.get("pinned"):
                item.setForeground(QColor(vt.COLORS["accent_peach"]))
            self._list.addItem(item)
        self._status.setText(f"{self._list.count()} item(s) shown  |  {len(self._entries)} total")

    def _start_watcher(self):
        self._watcher = ClipboardWatcher(QApplication.instance())
        self._watcher.new_content.connect(self._on_new_clip)
        self._watcher.start()

    def _on_new_clip(self, text):
        if any(e.get("text") == text for e in self._entries):
            return
        self._entries.append({
            "text": text,
            "pinned": False,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        save_history(self._entries)
        self._populate()

    def _selected_entry(self):
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _paste_item(self, item):
        entry = item.data(Qt.UserRole)
        if entry:
            QApplication.clipboard().setText(entry["text"])
            self._status.setText("Copied to clipboard")

    def _paste_selected(self):
        entry = self._selected_entry()
        if entry:
            QApplication.clipboard().setText(entry["text"])
            self._status.setText("Copied to clipboard")

    def _toggle_pin(self):
        entry = self._selected_entry()
        if not entry:
            return
        for e in self._entries:
            if e.get("text") == entry.get("text"):
                e["pinned"] = not e.get("pinned", False)
                break
        save_history(self._entries)
        self._populate()

    def _delete_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        self._entries = [e for e in self._entries if e.get("text") != entry.get("text")]
        save_history(self._entries)
        self._populate()

    def _clear_all(self):
        pinned = [e for e in self._entries if e.get("pinned")]
        if QMessageBox.question(
            self, "Clear History",
            f"Clear all unpinned entries? ({len(self._entries) - len(pinned)} items)",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._entries = pinned
        save_history(self._entries)
        self._populate()

    def _context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        menu = QMenu(self)
        menu.addAction("Copy to Clipboard", lambda: QApplication.clipboard().setText(entry["text"]))
        menu.addAction("Pin / Unpin", self._toggle_pin)
        menu.addSeparator()
        menu.addAction("Delete", self._delete_selected)
        menu.exec_(self._list.viewport().mapToGlobal(pos))

    def closeEvent(self, event):
        if self._watcher is not None:
            self._watcher.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = ClipboardManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
