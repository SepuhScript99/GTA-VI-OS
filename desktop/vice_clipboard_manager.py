#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Clipboard Manager (CLI Backend)
Legacy clipboard viewer with xclip/xsel integration.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 680
WINDOW_HEIGHT = 580
HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/clipboard_history.json")
MAX_ITEMS = 200


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
    cb = QApplication.clipboard()
    if cb is not None:
        text = cb.text()
        if text:
            return text
    for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
        if shutil.which(cmd[0]):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    return r.stdout
            except Exception:
                pass
    return ""


def set_clipboard(text):
    cb = QApplication.clipboard()
    if cb is not None:
        cb.setText(text)
    for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]):
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                proc.communicate(text.encode(), timeout=2)
                return
            except Exception:
                pass


class ClipboardManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Clipboard Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(520, 440)
        vt.apply_app_theme(self)
        self._entries = load_history()
        self._last_clip = ""
        self._init_ui()
        self._populate()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_clipboard)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(vt.make_header(
            "Clipboard Manager",
            "Monitor and restore recent clipboard entries across X11 and Qt",
            icon_name="edit-paste",
            badge_text="Live",
            badge_variant="aqua",
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
        self._list.itemDoubleClicked.connect(self._paste_selected)
        root.addWidget(self._list, 1)

        self._preview = QLabel("")
        self._preview.setWordWrap(True)
        self._preview.setMaximumHeight(64)
        self._preview.setStyleSheet(
            f"color: {vt.COLORS['text_secondary']}; font-size: 11px; "
            f"border: 1px solid {vt.COLORS['border']}; border-radius: 6px; padding: 6px; "
            f"background: {vt.COLORS['bg_surface']};"
        )
        self._list.currentItemChanged.connect(self._update_preview)
        root.addWidget(self._preview)

        btn_row = QHBoxLayout()
        paste_btn = vt.make_button("Copy to Clipboard", variant="primary", parent=self)
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

    def _poll_clipboard(self):
        text = get_clipboard()
        if text and text != self._last_clip and text.strip():
            self._last_clip = text
            existing = [e.get("text") for e in self._entries]
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
        sorted_entries = sorted(
            self._entries,
            key=lambda e: (bool(e.get("pinned")), e.get("ts") or e.get("timestamp") or ""),
            reverse=True,
        )
        for entry in sorted_entries:
            text = entry.get("text", "")
            if search and search not in text.lower():
                continue
            preview = text.replace("\n", " ")[:80]
            pinned = "[PIN] " if entry.get("pinned") else ""
            ts = (entry.get("ts") or entry.get("timestamp") or "")[:16]
            item = QListWidgetItem(f"{pinned}[{ts}]  {preview}")
            item.setData(Qt.UserRole, entry)
            if entry.get("pinned"):
                item.setForeground(QColor(vt.COLORS["accent_peach"]))
            self._list.addItem(item)
        self._status.setText(f"{len(self._entries)} item(s)")

    def _update_preview(self, current, _prev):
        if not current:
            return
        entry = current.data(Qt.UserRole)
        if entry:
            self._preview.setText(entry.get("text", "")[:300])

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)

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
