#!/usr/bin/env python3
"""Vice OS — Keyboard Shortcuts Manager. View, search, edit, and save keybindings."""

import json
import os
import shutil
import sys

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QKeySequenceEdit,
    QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 660

SHORTCUTS_FILE = os.path.expanduser("~/.config/vice-os/keyboard_shortcuts.json")

DEFAULT_SHORTCUTS = [
    {"name": "Open Launcher", "category": "System", "key": "Super_L", "desc": "Open the app launcher"},
    {"name": "Open Terminal", "category": "System", "key": "Ctrl+Alt+T", "desc": "Open terminal emulator"},
    {"name": "Open Settings", "category": "System", "key": "Super+I", "desc": "Open settings center"},
    {"name": "Open File Manager", "category": "System", "key": "Super+E", "desc": "Open file manager"},
    {"name": "Lock Screen", "category": "System", "key": "Super+L", "desc": "Lock the screen"},
    {"name": "Log Out", "category": "System", "key": "Ctrl+Alt+Delete", "desc": "End session"},
    {"name": "Screenshot Full", "category": "Media", "key": "Print", "desc": "Capture entire screen"},
    {"name": "Screenshot Window", "category": "Media", "key": "Alt+Print", "desc": "Capture active window"},
    {"name": "Screenshot Region", "category": "Media", "key": "Shift+Print", "desc": "Select screen region"},
    {"name": "Volume Up", "category": "Media", "key": "XF86AudioRaiseVolume", "desc": "Increase volume"},
    {"name": "Volume Down", "category": "Media", "key": "XF86AudioLowerVolume", "desc": "Decrease volume"},
    {"name": "Volume Mute", "category": "Media", "key": "XF86AudioMute", "desc": "Toggle mute"},
    {"name": "Brightness Up", "category": "Display", "key": "XF86MonBrightnessUp", "desc": "Increase brightness"},
    {"name": "Brightness Down", "category": "Display", "key": "XF86MonBrightnessDown", "desc": "Decrease brightness"},
    {"name": "Switch Workspace", "category": "Window", "key": "Ctrl+Alt+Left", "desc": "Previous workspace"},
    {"name": "Close Window", "category": "Window", "key": "Alt+F4", "desc": "Close active window"},
    {"name": "Maximize Window", "category": "Window", "key": "Alt+F10", "desc": "Toggle maximize"},
    {"name": "Minimize Window", "category": "Window", "key": "Alt+F9", "desc": "Minimize window"},
]


def load_shortcuts():
    if os.path.exists(SHORTCUTS_FILE):
        try:
            with open(SHORTCUTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return [dict(item) for item in DEFAULT_SHORTCUTS]


def save_shortcuts(shortcuts):
    os.makedirs(os.path.dirname(SHORTCUTS_FILE), exist_ok=True)
    try:
        with open(SHORTCUTS_FILE, "w", encoding="utf-8") as f:
            json.dump(shortcuts, f, indent=2)
        return True
    except Exception as e:
        log_error(f"Save shortcuts failed: {e}")
        return False


class ShortcutEditDialog(QDialog):
    def __init__(self, shortcut, editable_meta=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit: {shortcut['name']}")
        self.setMinimumSize(480, 290)
        vt.apply_app_theme(self)

        layout = QFormLayout(self)
        self._name_edit = QLineEdit(shortcut["name"])
        self._name_edit.setReadOnly(not editable_meta)
        layout.addRow("Name:", self._name_edit)

        self._cat_combo = QComboBox()
        self._cat_combo.addItems(["System", "Media", "Display", "Window"])
        self._cat_combo.setCurrentText(shortcut.get("category", "System"))
        self._cat_combo.setEnabled(editable_meta)
        layout.addRow("Category:", self._cat_combo)

        self._desc_edit = QLineEdit(shortcut.get("desc", ""))
        self._desc_edit.setReadOnly(not editable_meta)
        layout.addRow("Description:", self._desc_edit)

        self._manual_edit = QLineEdit(shortcut.get("key", ""))
        self._key_edit = QKeySequenceEdit()
        seq = QKeySequence(shortcut.get("key", ""))
        if not seq.isEmpty():
            self._key_edit.setKeySequence(seq)
        self._key_edit.keySequenceChanged.connect(self._on_seq_changed)
        layout.addRow("Capture Key:", self._key_edit)
        layout.addRow("Shortcut Text:", self._manual_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_seq_changed(self, seq):
        text = seq.toString()
        if text:
            self._manual_edit.setText(text)

    def values(self):
        manual = self._manual_edit.text().strip()
        seq = self._key_edit.keySequence().toString().strip()
        return {
            "name": self._name_edit.text().strip() or "New Shortcut",
            "category": self._cat_combo.currentText(),
            "desc": self._desc_edit.text().strip(),
            "key": manual or seq,
        }


class KeyboardShortcutsManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Keyboard Shortcuts")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(820, 520)
        vt.apply_app_theme(self)
        self._shortcuts = load_shortcuts()
        self._init_ui()
        self._populate()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Keyboard Shortcuts Manager",
            "View, search, customize and export system & window keybindings",
            icon_name="preferences-desktop-keyboard",
            badge_text="KEYBINDS",
            badge_variant="coral",
            parent=self,
        ))

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

        reset_btn = vt.make_button("Reset to Defaults", "secondary", parent=self)
        reset_btn.clicked.connect(self._reset)
        row.addWidget(reset_btn)
        root.addLayout(row)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Category", "Shortcut", "Description"])
        for col in (0, 1, 2):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._edit_shortcut)
        root.addWidget(self._table)

        btn_row = QHBoxLayout()
        edit_btn = vt.make_button("Edit Selected", "primary", parent=self)
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)

        add_btn = vt.make_button("Add Shortcut", "secondary", parent=self)
        add_btn.clicked.connect(self._add_shortcut)
        btn_row.addWidget(add_btn)

        remove_btn = vt.make_button("Remove Selected", "danger", parent=self)
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        save_btn = vt.make_button("Save", "primary", parent=self)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        export_btn = vt.make_button("Export", "secondary", parent=self)
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _populate(self):
        search = self._search.text().lower()
        cat = self._cat_filter.currentText()

        self._table.setRowCount(0)
        for s in self._shortcuts:
            if cat != "All" and s.get("category") != cat:
                continue
            if search and search not in s.get("name", "").lower() and search not in s.get("desc", "").lower():
                continue

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(s.get("category", "")))
            self._table.setItem(row, 2, QTableWidgetItem(s.get("key", "")))
            self._table.setItem(row, 3, QTableWidgetItem(s.get("desc", "")))

        self._status.setText(f"{self._table.rowCount()} shortcut(s)")

    def _selected_index(self):
        row = self._table.currentRow()
        if row < 0:
            return -1
        search = self._search.text().lower()
        cat = self._cat_filter.currentText()
        matches = [
            (i, s) for i, s in enumerate(self._shortcuts)
            if (cat == "All" or s.get("category") == cat) and (
                not search or search in s.get("name", "").lower() or search in s.get("desc", "").lower()
            )
        ]
        return matches[row][0] if row < len(matches) else -1

    def _edit_shortcut(self, row, col):
        idx = self._selected_index()
        if idx < 0:
            return
        dlg = ShortcutEditDialog(self._shortcuts[idx], editable_meta=False, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.values()
            if vals["key"]:
                self._shortcuts[idx]["key"] = vals["key"]
                self._populate()
                self._status.setText(f"Updated: {self._shortcuts[idx]['name']}")

    def _edit_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a shortcut first.")
            return
        self._edit_shortcut(row, 0)

    def _add_shortcut(self):
        dlg = ShortcutEditDialog(
            {"name": "", "category": "System", "key": "", "desc": ""},
            editable_meta=True,
            parent=self,
        )
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.values()
            if vals["key"]:
                self._shortcuts.append(vals)
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
            self, "Reset", "Reset all shortcuts to defaults?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._shortcuts = [dict(item) for item in DEFAULT_SHORTCUTS]
        save_shortcuts(self._shortcuts)
        self._populate()
        self._status.setText("Reset to defaults")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Shortcuts", os.path.expanduser("~/vice_shortcuts.json"), "JSON (*.json)"
        )
        if path and save_shortcuts(self._shortcuts):
            try:
                shutil.copy2(SHORTCUTS_FILE, path)
                self._status.setText(f"Exported to {path}")
            except OSError as e:
                QMessageBox.warning(self, "Export Failed", str(e))


def main():
    app = QApplication(sys.argv)
    win = KeyboardShortcutsManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
