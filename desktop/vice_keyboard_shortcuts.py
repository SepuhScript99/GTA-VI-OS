#!/usr/bin/env python3
"""Vice OS — Keyboard Shortcuts Manager. View, search, edit, and save keybindings."""

import sys
import os
import subprocess
import json
import glob
import shutil

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QMessageBox,
    QComboBox, QGroupBox, QAbstractItemView, QKeySequenceEdit, QDialog,
    QDialogButtonBox, QFormLayout, QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QFont, QKeySequence

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 660

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""

SHORTCUTS_FILE = os.path.expanduser("~/.config/vice-os/keyboard_shortcuts.json")


DEFAULT_SHORTCUTS = [
    {"name": "Open Launcher",        "category": "System",  "key": "Super_L",       "desc": "Open the app launcher"},
    {"name": "Open Terminal",        "category": "System",  "key": "Ctrl+Alt+T",     "desc": "Open terminal emulator"},
    {"name": "Open Settings",        "category": "System",  "key": "Super+I",        "desc": "Open settings center"},
    {"name": "Open File Manager",    "category": "System",  "key": "Super+E",         "desc": "Open file manager"},
    {"name": "Lock Screen",          "category": "System",  "key": "Super+L",         "desc": "Lock the screen"},
    {"name": "Log Out",              "category": "System",  "key": "Ctrl+Alt+Delete", "desc": "End session"},
    {"name": "Screenshot Full",      "category": "Media",  "key": "Print",           "desc": "Capture entire screen"},
    {"name": "Screenshot Window",    "category": "Media",  "key": "Alt+Print",       "desc": "Capture active window"},
    {"name": "Screenshot Region",    "category": "Media",  "key": "Shift+Print",     "desc": "Select screen region"},
    {"name": "Volume Up",            "category": "Media",  "key": "XF86AudioRaiseVolume", "desc": "Increase volume"},
    {"name": "Volume Down",         "category": "Media",  "key": "XF86AudioLowerVolume", "desc": "Decrease volume"},
    {"name": "Volume Mute",          "category": "Media",  "key": "XF86AudioMute",    "desc": "Toggle mute"},
    {"name": "Brightness Up",        "category": "Display","key": "XF86MonBrightnessUp", "desc": "Increase brightness"},
    {"name": "Brightness Down",      "category": "Display","key": "XF86MonBrightnessDown", "desc": "Decrease brightness"},
    {"name": "Switch Workspace",     "category": "Window", "key": "Ctrl+Alt+ArrowLeft", "desc": "Previous workspace"},
    {"name": "Close Window",         "category": "Window", "key": "Alt+F4",          "desc": "Close active window"},
    {"name": "Maximize Window",      "category": "Window", "key": "Alt+F10",         "desc": "Toggle maximize"},
    {"name": "Minimize Window",      "category": "Window", "key": "Alt+F9",          "desc": "Minimize window"},
]


def load_shortcuts():
    if os.path.exists(SHORTCUTS_FILE):
        try:
            with open(SHORTCUTS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return list(DEFAULT_SHORTCUTS)


def save_shortcuts(shortcuts):
    os.makedirs(os.path.dirname(SHORTCUTS_FILE), exist_ok=True)
    try:
        with open(SHORTCUTS_FILE, "w") as f:
            json.dump(shortcuts, f, indent=2)
        return True
    except Exception as e:
        log_error(f"Save shortcuts failed: {e}")
        return False


class ShortcutEditDialog(QDialog):
    def __init__(self, shortcut, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit: {shortcut['name']}")
        self.setFixedSize(480, 260)
        self.setStyleSheet("""
            QWidget { background: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
            QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px; }
            QLabel { color: #00ffff; }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Name: {shortcut['name']}"))
        layout.addWidget(QLabel(f"Description: {shortcut['desc']}"))
        layout.addWidget(QLabel(f"Category: {shortcut['category']}"))

        layout.addWidget(QLabel("Shortcut:"))
        self._key_edit = QKeySequenceEdit()
        seq = QKeySequence(shortcut["key"])
        self._key_edit.setKeySequence(seq)
        layout.addWidget(self._key_edit)

        layout.addWidget(QLabel("Or type manually:"))
        self._manual_edit = QLineEdit(shortcut["key"])
        layout.addWidget(self._manual_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_key(self):
        seq = self._key_edit.keySequence()
        if not seq.isEmpty():
            return seq.toString()
        return self._manual_edit.text().strip()


class KeyboardShortcutsManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Keyboard Shortcuts")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._shortcuts = load_shortcuts()
        self._init_ui()
        self._populate()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Keyboard Shortcuts Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Search + filter
        row = QHBoxLayout()
        row.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter shortcuts...")
        self._search.textChanged.connect(self._populate)
        row.addWidget(self._search)

        row.addWidget(QLabel("Category:"))
        self._cat_filter = QComboBox()
        self._cat_filter.addItems(["All", "System", "Media", "Display", "Window"])
        self._cat_filter.currentTextChanged.connect(self._populate)
        row.addWidget(self._cat_filter)
        row.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset)
        row.addWidget(reset_btn)

        root.addLayout(row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Category", "Shortcut", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._edit_shortcut)
        root.addWidget(self._table)

        # Buttons
        btn_row = QHBoxLayout()

        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)

        add_btn = QPushButton("Add Shortcut")
        add_btn.clicked.connect(self._add_shortcut)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)

        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _populate(self):
        search = self._search.text().lower()
        cat = self._cat_filter.currentText()

        self._table.setRowCount(0)
        for s in self._shortcuts:
            if cat != "All" and s["category"] != cat:
                continue
            if search and search not in s["name"].lower() and search not in s["desc"].lower():
                continue

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(s["category"]))
            self._table.setItem(row, 2, QTableWidgetItem(s["key"]))
            self._table.setItem(row, 3, QTableWidgetItem(s["desc"]))

        self._status.setText(f"{self._table.rowCount()} shortcut(s)")

    def _selected_index(self):
        row = self._table.currentRow()
        if row < 0:
            return -1
        search = self._search.text().lower()
        cat = self._cat_filter.currentText()
        matches = [
            (i, s) for i, s in enumerate(self._shortcuts)
            if (cat == "All" or s["category"] == cat)
            and (not search or search in s["name"].lower() or search in s["desc"].lower())
        ]
        return matches[row][0] if row < len(matches) else -1

    def _edit_shortcut(self, row, col):
        idx = self._selected_index()
        if idx < 0:
            return
        dlg = ShortcutEditDialog(self._shortcuts[idx], self)
        if dlg.exec_() == QDialog.Accepted:
            key = dlg.get_key()
            if key:
                self._shortcuts[idx]["key"] = key
                self._populate()
                self._status.setText(f"Updated: {self._shortcuts[idx]['name']}")

    def _edit_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a shortcut first.")
            return
        self._edit_shortcut(row, 0)

    def _add_shortcut(self):
        dlg = ShortcutEditDialog({"name": "New Shortcut", "category": "System", "key": "", "desc": ""}, self)
        if dlg.exec_() == QDialog.Accepted:
            key = dlg.get_key()
            if key:
                self._shortcuts.append({"name": "New Shortcut", "category": "System", "key": key, "desc": ""})
                self._populate()

    def _remove_selected(self):
        idx = self._selected_index()
        if idx < 0:
            QMessageBox.warning(self, "No Selection", "Select a shortcut first.")
            return
        self._shortcuts.pop(idx)
        self._populate()

    def _save(self):
        if save_shortcuts(self._shortcuts):
            self._status.setText("Saved successfully")
            log_info(f"Saved {len(self._shortcuts)} keyboard shortcuts")
        else:
            self._status.setText("Save failed")

    def _reset(self):
        if QMessageBox.question(
            self, "Reset",
            "Reset all shortcuts to defaults?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._shortcuts = list(DEFAULT_SHORTCUTS)
        save_shortcuts(self._shortcuts)
        self._populate()
        self._status.setText("Reset to defaults")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Shortcuts",
                                              os.path.expanduser("~/vice_shortcuts.json"),
                                              "JSON (*.json)")
        if path:
            save_shortcuts(self._shortcuts)
            shutil.copy2(SHORTCUTS_FILE, path)
            self._status.setText(f"Exported to {path}")


def main():
    app = QApplication(sys.argv)
    win = KeyboardShortcutsManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()