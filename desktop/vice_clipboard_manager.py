#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Clipboard Manager (CLI Backend)
Legacy clipboard viewer with xclip/xsel integration.
"""

import sys
import os
import json
import datetime
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 680
WINDOW_HEIGHT = 560
HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/clipboard_history.json")
MAX_ITEMS = 200

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; font-size: 11px; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QListWidget::item:hover { background: #1a1a1a; }
QLabel { color: #00ffff; }
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
            json.dump(entries[-MAX_ITEMS:], f, indent=2)
    except Exception as e:
        log_error(f"Clipboard save failed: {e}")


def get_clipboard():
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                           capture_output=True, text=True, timeout=2)
        return r.stdout
    except Exception:
        try:
            r = subprocess.run(["xsel", "--clipboard", "--output"],
                               capture_output=True, text=True, timeout=2)
            return r.stdout
        except Exception:
            cb = QApplication.clipboard()
            return cb.text() if cb is not None else ""


def set_clipboard(text):
    try:
        proc = subprocess.Popen(["xclip", "-selection", "clipboard"],
                                stdin=subprocess.PIPE)
        proc.communicate(text.encode())
    except Exception:
        try:
            proc = subprocess.Popen(["xsel", "--clipboard", "--input"],
                                    stdin=subprocess.PIPE)
            proc.communicate(text.encode())
        except Exception:
            cb = QApplication.clipboard()
            if cb is not None:
                cb.setText(text)


class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Clipboard Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._entries = load_history()
        self._last_clip = ""
        self._init_ui()
        self._populate()
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_clipboard)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Clipboard Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 4px;")
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
        self._list.itemDoubleClicked.connect(self._paste_selected)
        root.addWidget(self._list)

        # Preview
        self._preview = QLabel("")
        self._preview.setWordWrap(True)
        self._preview.setMaximumHeight(60)
        self._preview.setStyleSheet("color: #888; font-size: 10px; border: 1px solid #333; padding: 4px;")
        self._list.currentItemChanged.connect(self._update_preview)
        root.addWidget(self._preview)

        btn_row = QHBoxLayout()
        paste_btn = QPushButton("Copy to Clipboard")
        paste_btn.clicked.connect(self._paste_selected)
        btn_row.addWidget(paste_btn)

        pin_btn = QPushButton("Pin / Unpin")
        pin_btn.clicked.connect(self._toggle_pin)
        btn_row.addWidget(pin_btn)

        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
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

    def _poll_clipboard(self):
        text = get_clipboard()
        if text and text != self._last_clip and text.strip():
            self._last_clip = text
            # Don't duplicate
            existing = [e["text"] for e in self._entries]
            if text not in existing:
                self._entries.append({
                    "text": text,
                    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                    "pinned": False,
                })
                save_history(self._entries)
                self._populate()

    def _populate(self):
        search = self._search.text().lower()
        self._list.clear()
        # Pinned first
        sorted_entries = sorted(self._entries, key=lambda e: (not e.get("pinned"), e.get("ts", "")), reverse=False)
        sorted_entries = list(reversed(sorted_entries))
        for entry in sorted_entries:
            text = entry["text"]
            if search and search not in text.lower():
                continue
            preview = text.replace("\n", " ")[:80]
            pinned = "📌 " if entry.get("pinned") else ""
            ts = entry.get("ts", "")[:16]
            item = QListWidgetItem(f"{pinned}[{ts}]  {preview}")
            item.setData(Qt.UserRole, entry)
            if entry.get("pinned"):
                item.setForeground(QColor("#ff00ff"))
            self._list.addItem(item)
        self._status.setText(f"{len(self._entries)} item(s)")

    def _update_preview(self, current, _prev):
        if not current:
            return
        entry = current.data(Qt.UserRole)
        if entry:
            self._preview.setText(entry["text"][:300])

    def _selected_entry(self):
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection", "Select an item first.")
            return None, None
        return item, item.data(Qt.UserRole)

    def _paste_selected(self):
        _, entry = self._selected_entry()
        if entry:
            set_clipboard(entry["text"])
            self._last_clip = entry["text"]
            self._status.setText("Copied to clipboard")
            log_info("Clipboard item restored")

    def _toggle_pin(self):
        _, entry = self._selected_entry()
        if not entry:
            return
        for e in self._entries:
            if e["text"] == entry["text"] and e.get("ts") == entry.get("ts"):
                e["pinned"] = not e.get("pinned", False)
                break
        save_history(self._entries)
        self._populate()

    def _delete_selected(self):
        _, entry = self._selected_entry()
        if not entry:
            return
        self._entries = [e for e in self._entries
                         if not (e["text"] == entry["text"] and e.get("ts") == entry.get("ts"))]
        save_history(self._entries)
        self._populate()

    def _clear_all(self):
        pinned = [e for e in self._entries if e.get("pinned")]
        if QMessageBox.question(
            self, "Clear History",
            f"Clear all unpinned items? ({len(self._entries) - len(pinned)} items)",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._entries = pinned
        save_history(self._entries)
        self._populate()
        log_info("Clipboard history cleared")


def main():
    app = QApplication(sys.argv)
    win = ClipboardManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
