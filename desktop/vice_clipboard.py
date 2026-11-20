#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Clipboard History Manager
Tracks clipboard history with pinning, persistent storage, search, and context menu actions.
"""

import sys
import os
import json
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QAbstractItemView,
    QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QClipboard

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 620
WINDOW_HEIGHT = 600
HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/clipboard_history.json")
MAX_ENTRIES = 200

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; font-size: 11px; }
QListWidget::item { padding: 4px; border-bottom: 1px solid #1a1a1a; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QLabel { color: #00ffff; }
QMenu { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; }
QMenu::item:selected { background: #00ffff; color: #0a0a0a; }
"""


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


class ClipboardWatcher(QThread):
    new_content = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._last = ""

    def run(self):
        import time
        while True:
            text = self._app.clipboard().text()
            if text and text != self._last:
                self._last = text
                self.new_content.emit(text)
            time.sleep(0.8)


class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Clipboard Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._entries = load_history()
        self._watcher = None
        self._init_ui()
        self._populate()
        self._start_watcher()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Clipboard Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

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
        root.addWidget(self._list)

        btn_row = QHBoxLayout()
        paste_btn = QPushButton("Paste Selected")
        paste_btn.clicked.connect(self._paste_selected)
        btn_row.addWidget(paste_btn)

        pin_btn = QPushButton("Pin / Unpin")
        pin_btn.clicked.connect(self._toggle_pin)
        btn_row.addWidget(pin_btn)

        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)
        root.addLayout(btn_row)

        self._status = QLabel(f"{len(self._entries)} item(s)")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
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
            label = f"📌 {preview}" if entry.get("pinned") else preview
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            if entry.get("pinned"):
                item.setForeground(QColor("#ff00ff"))
            self._list.addItem(item)
        self._status.setText(f"{self._list.count()} item(s) shown  |  {len(self._entries)} total")

    def _start_watcher(self):
        self._watcher = ClipboardWatcher(QApplication.instance())
        self._watcher.new_content.connect(self._on_new_clip)
        self._watcher.start()

    def _on_new_clip(self, text):
        if any(e["text"] == text for e in self._entries):
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
            if e["text"] == entry["text"]:
                e["pinned"] = not e.get("pinned", False)
                break
        save_history(self._entries)
        self._populate()

    def _delete_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        self._entries = [e for e in self._entries if e["text"] != entry["text"]]
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
        menu = QMenu(self)
        menu.addAction("Copy to Clipboard", lambda: QApplication.clipboard().setText(entry["text"]))
        menu.addAction("Pin / Unpin", self._toggle_pin)
        menu.addSeparator()
        menu.addAction("Delete", self._delete_selected)
        menu.exec_(self._list.viewport().mapToGlobal(pos))


def main():
    app = QApplication(sys.argv)
    win = ClipboardManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
