#!/usr/bin/env python3
"""Vice OS — Trash Manager. View, restore, and empty the XDG trash."""

import configparser
import datetime
import os
import shutil
import sys
from urllib.parse import unquote

from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 580

TRASH_FILES = os.path.expanduser("~/.local/share/Trash/files")
TRASH_INFO = os.path.expanduser("~/.local/share/Trash/info")


def fmt_size(n):
    for unit, factor in [("B", 1), ("KB", 1024), ("MB", 1024**2), ("GB", 1024**3)]:
        if n < factor * 1024:
            return f"{n / factor:.1f} {unit}"
    return f"{n / 1024**3:.1f} GB"


def path_size(path):
    if os.path.isfile(path) or os.path.islink(path):
        try:
            return os.path.getsize(path) if not os.path.islink(path) else 0
        except OSError:
            return 0
    total = 0
    for dirpath, _dirs, files in os.walk(path, onerror=lambda e: None):
        for fname in files:
            try:
                fp = os.path.join(dirpath, fname)
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def load_trash_entries():
    """Parse all .trashinfo files. Returns list of dicts."""
    entries = []
    if not os.path.isdir(TRASH_INFO):
        return entries
    for info_file in os.listdir(TRASH_INFO):
        if not info_file.endswith(".trashinfo"):
            continue
        info_path = os.path.join(TRASH_INFO, info_file)
        data_file = os.path.join(TRASH_FILES, info_file[:-len(".trashinfo")])

        cp = configparser.RawConfigParser(interpolation=None)
        try:
            cp.read(info_path, encoding="utf-8")
            original = cp.get("Trash Info", "Path", fallback="")
            deletion_date = cp.get("Trash Info", "DeletionDate", fallback="")
        except Exception:
            original, deletion_date = "", ""

        if original:
            original = unquote(original)

        exists = os.path.exists(data_file) or os.path.islink(data_file)
        entries.append({
            "name": os.path.basename(data_file) if exists else info_file[:-len(".trashinfo")],
            "data_path": data_file,
            "info_path": info_path,
            "original": original or "(unknown)",
            "deleted": deletion_date,
            "exists": exists,
            "size": path_size(data_file) if exists else 0,
        })
    entries.sort(key=lambda e: e["deleted"], reverse=True)
    return entries


class TrashManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Trash Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 460)
        vt.apply_app_theme(self)
        self._entries = []
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Trash Manager",
            "Inspect, search, restore or permanently empty XDG Trash items",
            icon_name="user-trash",
            badge_text="TRASH",
            badge_variant="gold",
            parent=self,
        ))

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by name or original path...")
        self._search.textChanged.connect(self._populate)
        search_row.addWidget(self._search)
        root.addLayout(search_row)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Original Location", "Deleted", "Size"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()

        restore_btn = vt.make_button("Restore Selected", "primary", parent=self)
        restore_btn.clicked.connect(self._restore_selected)
        btn_row.addWidget(restore_btn)

        delete_btn = vt.make_button("Delete Permanently", "danger", parent=self)
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)

        empty_btn = vt.make_button("Empty Trash", "danger", parent=self)
        empty_btn.clicked.connect(self._empty_trash)
        btn_row.addWidget(empty_btn)

        btn_row.addStretch()

        refresh_btn = vt.make_button("Refresh", "secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._entries = load_trash_entries()
        self._populate()

    def _populate(self):
        search = self._search.text().lower()
        self._table.setRowCount(0)

        total_size = 0
        for entry in self._entries:
            total_size += entry["size"]
            if search and search not in entry["name"].lower() and search not in entry["original"].lower():
                continue

            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = QTableWidgetItem(entry["name"])
            if not entry["exists"]:
                name_item.setForeground(QBrush(QColor(vt.COLORS["text_muted"])))
                name_item.setText(entry["name"] + " (missing)")
            self._table.setItem(row, 0, name_item)

            orig_item = QTableWidgetItem(entry["original"])
            orig_item.setForeground(QBrush(QColor(vt.COLORS["accent_aqua"])))
            self._table.setItem(row, 1, orig_item)

            deleted = entry["deleted"]
            try:
                dt = datetime.datetime.fromisoformat(deleted)
                deleted = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
            self._table.setItem(row, 2, QTableWidgetItem(deleted))
            self._table.setItem(row, 3, QTableWidgetItem(fmt_size(entry["size"])))

        self._status.setText(f"{len(self._entries)} item(s) — {fmt_size(total_size)} total")

    def _selected_entries(self):
        rows = sorted({i.row() for i in self._table.selectedItems()}, reverse=True)
        search = self._search.text().lower()
        visible = [
            e for e in self._entries
            if not search or search in e["name"].lower() or search in e["original"].lower()
        ]
        return [visible[r] for r in rows if r < len(visible)]

    def _restore_selected(self):
        selected = self._selected_entries()
        if not selected:
            QMessageBox.information(self, "No Selection", "Select item(s) to restore.")
            return

        restored = 0
        conflicts = 0
        for entry in selected:
            if not entry["exists"] or entry["original"] == "(unknown)":
                continue
            original = entry["original"]
            dest_dir = os.path.dirname(original)
            try:
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                if os.path.exists(original):
                    stem, ext = os.path.splitext(original)
                    shutil.move(entry["data_path"], f"{stem}.restored{ext}")
                    conflicts += 1
                else:
                    shutil.move(entry["data_path"], original)
                if os.path.exists(entry["info_path"]):
                    os.remove(entry["info_path"])
                restored += 1
                log_info(f"Restored: {entry['data_path']} -> {original}")
            except Exception as e:
                log_error(f"Restore failed {entry['data_path']}: {e}")
                QMessageBox.warning(self, "Restore Failed", f"{entry['name']}\n{e}")

        msg = f"Restored {restored} item(s)."
        if conflicts:
            msg += f"\n{conflicts} had name conflicts (saved with .restored suffix)."
        QMessageBox.information(self, "Restore Complete", msg)
        self._refresh()

    def _delete_selected(self):
        selected = self._selected_entries()
        if not selected:
            QMessageBox.information(self, "No Selection", "Select item(s) to delete.")
            return
        if QMessageBox.question(
            self, "Delete Permanently",
            f"Permanently delete {len(selected)} item(s)?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        for entry in selected:
            try:
                if os.path.isdir(entry["data_path"]) and not os.path.islink(entry["data_path"]):
                    shutil.rmtree(entry["data_path"])
                elif os.path.exists(entry["data_path"]) or os.path.islink(entry["data_path"]):
                    os.remove(entry["data_path"])
                if os.path.exists(entry["info_path"]):
                    os.remove(entry["info_path"])
                log_info(f"Permanent delete: {entry['data_path']}")
            except Exception as e:
                log_error(f"Delete failed {entry['data_path']}: {e}")
        self._refresh()

    def _empty_trash(self):
        if not self._entries:
            QMessageBox.information(self, "Empty", "Trash is already empty.")
            return
        total = sum(e["size"] for e in self._entries)
        if QMessageBox.question(
            self, "Empty Trash",
            f"Permanently delete ALL {len(self._entries)} item(s) ({fmt_size(total)})?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            for entry in self._entries:
                if os.path.isdir(entry["data_path"]) and not os.path.islink(entry["data_path"]):
                    shutil.rmtree(entry["data_path"], ignore_errors=True)
                elif os.path.exists(entry["data_path"]) or os.path.islink(entry["data_path"]):
                    os.remove(entry["data_path"])
                if os.path.exists(entry["info_path"]):
                    os.remove(entry["info_path"])
            log_info("Trash emptied")
            self._refresh()
        except Exception as e:
            log_error(f"Empty trash failed: {e}")
            QMessageBox.warning(self, "Error", str(e))


def main():
    app = QApplication(sys.argv)
    win = TrashManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
