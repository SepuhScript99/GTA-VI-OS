#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) File Manager
Dual-pane file browser with bookmarks, file operations (copy/cut/paste), and mime-type handling.
"""

import datetime
import os
import shutil
import subprocess
import sys
from urllib.parse import quote

from PyQt5.QtCore import QDir, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileSystemModel, QInputDialog,
    QLabel, QLineEdit, QListView, QMenu, QMessageBox, QPushButton, QSplitter,
    QStatusBar, QToolBar, QTreeView, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700


class CopyWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, srcs, dest, move=False, parent=None):
        super().__init__(parent)
        self.srcs = list(srcs)
        self.dest = dest
        self.move = move
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        try:
            for src in self.srcs:
                if self._cancelled:
                    return
                if os.path.isdir(src):
                    dest_path = os.path.join(self.dest, os.path.basename(src))
                    if self.move:
                        shutil.move(src, dest_path)
                    else:
                        shutil.copytree(src, dest_path)
                else:
                    if self.move:
                        shutil.move(src, self.dest)
                    else:
                        shutil.copy2(src, self.dest)
            if not self._cancelled:
                self.done.emit(True, "")
        except Exception as e:
            if not self._cancelled:
                self.done.emit(False, str(e))


class FileManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — File Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        vt.apply_app_theme(self)
        self._clipboard = None
        self._clipboard_cut = False
        self._worker = None
        self._history = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 4)
        root.setSpacing(6)

        root.addWidget(vt.make_header(
            "File Manager",
            "Browse local files, manage bookmarks and copy, move or trash items",
            icon_name="system-file-manager",
            badge_text="FILES",
            badge_variant="aqua",
            parent=self,
        ))

        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))

        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._go_back)
        toolbar.addWidget(self._back_btn)

        self._up_btn = QPushButton("Up")
        self._up_btn.clicked.connect(self._go_up)
        toolbar.addWidget(self._up_btn)

        self._home_btn = QPushButton("Home")
        self._home_btn.clicked.connect(lambda: self._navigate(os.path.expanduser("~")))
        toolbar.addWidget(self._home_btn)

        self._path_edit = QLineEdit(os.path.expanduser("~"))
        self._path_edit.returnPressed.connect(lambda: self._navigate(self._path_edit.text()))
        toolbar.addWidget(self._path_edit)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter...")
        self._search_edit.setFixedWidth(180)
        self._search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search_edit)

        self._view_combo = QComboBox()
        self._view_combo.addItems(["List", "Icons"])
        self._view_combo.setFixedWidth(90)
        self._view_combo.currentTextChanged.connect(self._switch_view)
        toolbar.addWidget(self._view_combo)
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        bm_widget = QWidget()
        bm_widget.setFixedWidth(170)
        bm_layout = QVBoxLayout(bm_widget)
        bm_layout.setContentsMargins(4, 4, 4, 4)
        bm_label = QLabel("Bookmarks")
        bm_label.setStyleSheet(f"color: {vt.COLORS['accent_coral']}; font-weight: bold;")
        bm_layout.addWidget(bm_label)

        self._bookmarks = {
            "Home": os.path.expanduser("~"),
            "Desktop": os.path.expanduser("~/Desktop"),
            "Documents": os.path.expanduser("~/Documents"),
            "Downloads": os.path.expanduser("~/Downloads"),
            "Pictures": os.path.expanduser("~/Pictures"),
            "Music": os.path.expanduser("~/Music"),
            "Videos": os.path.expanduser("~/Videos"),
            "Trash": os.path.join(os.path.expanduser("~"), ".local/share/Trash/files"),
            "/": "/",
            "/etc": "/etc",
            "/var/log": "/var/log",
        }
        for name, path in self._bookmarks.items():
            btn = QPushButton(name)
            btn.setStyleSheet("text-align: left; padding-left: 8px;")
            btn.clicked.connect(lambda _, p=path: self._navigate(p))
            bm_layout.addWidget(btn)
        bm_layout.addStretch()
        splitter.addWidget(bm_widget)

        self._model = QFileSystemModel()
        self._model.setRootPath(QDir.rootPath())
        self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.Hidden)

        self._list_view = QListView()
        self._list_view.setModel(self._model)
        self._list_view.setViewMode(QListView.ListMode)
        self._list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list_view.doubleClicked.connect(self._on_double_click)
        self._list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._context_menu)

        self._tree_view = QTreeView()
        self._tree_view.setModel(self._model)
        self._tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree_view.doubleClicked.connect(self._on_double_click)
        self._tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._context_menu)
        self._tree_view.header().resizeSection(0, 260)

        self._current_view = self._tree_view
        self._tree_view.setVisible(True)
        self._list_view.setVisible(False)
        splitter.addWidget(self._tree_view)
        splitter.addWidget(self._list_view)
        splitter.setSizes([170, 910])

        self._status = QStatusBar()
        root.addWidget(self._status)

        self._navigate(os.path.expanduser("~"))

    def _navigate(self, path, record_history=True):
        if not os.path.isdir(path):
            return
        self._path_edit.setText(path)
        idx = self._model.index(path)
        self._tree_view.setRootIndex(idx)
        self._list_view.setRootIndex(idx)
        if record_history and (not self._history or self._history[-1] != path):
            self._history.append(path)
        self._status.showMessage(f"{path}  —  {self._model.rowCount(idx)} items")

    def _go_back(self):
        if len(self._history) > 1:
            self._history.pop()
            self._navigate(self._history[-1], record_history=False)

    def _go_up(self):
        cur = self._path_edit.text()
        parent = os.path.dirname(cur)
        if parent != cur:
            self._navigate(parent)

    def _apply_filter(self, text):
        self._model.setNameFilters([f"*{text}*"] if text else [])
        self._model.setNameFilterDisables(False)

    def _switch_view(self, mode):
        if mode == "Icons":
            self._tree_view.setVisible(False)
            self._list_view.setVisible(True)
            self._list_view.setViewMode(QListView.IconMode)
            self._list_view.setGridSize(QSize(80, 80))
            self._current_view = self._list_view
        else:
            self._list_view.setVisible(False)
            self._tree_view.setVisible(True)
            self._current_view = self._tree_view

    def _on_double_click(self, index):
        path = self._model.filePath(index)
        if os.path.isdir(path):
            self._navigate(path)
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _selected_paths(self):
        return [
            self._model.filePath(i)
            for i in self._current_view.selectedIndexes()
            if i.column() == 0
        ]

    def _context_menu(self, pos):
        paths = self._selected_paths()
        menu = QMenu(self)

        if paths:
            menu.addAction(
                "Open",
                lambda: [subprocess.Popen(["xdg-open", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for p in paths],
            )
            menu.addSeparator()
            menu.addAction("Copy", lambda: self._copy(paths, cut=False))
            menu.addAction("Cut", lambda: self._copy(paths, cut=True))
        if self._clipboard:
            menu.addAction("Paste", self._paste)
        menu.addSeparator()
        if paths:
            menu.addAction("Rename", lambda: self._rename(paths[0]))
            menu.addAction("Move to Trash", lambda: self._trash(paths))
            menu.addAction("Delete Permanently", lambda: self._delete(paths))
            menu.addSeparator()
            menu.addAction("Properties", lambda: self._properties(paths[0]))
        menu.addAction("New Folder", self._new_folder)
        menu.addAction("New File", self._new_file)
        menu.exec_(self._current_view.viewport().mapToGlobal(pos))

    def _copy(self, paths, cut):
        self._clipboard = list(paths)
        self._clipboard_cut = cut
        self._status.showMessage(f"{'Cut' if cut else 'Copied'} {len(paths)} item(s)")

    def _paste(self):
        if not self._clipboard:
            return
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "A file transfer is already running.")
            return
        dest = self._path_edit.text()
        was_cut = self._clipboard_cut
        w = CopyWorker(self._clipboard, dest, move=was_cut, parent=self)
        w.done.connect(lambda ok, err: self._op_done(ok, err, "Paste", clear_clip=ok and was_cut))
        self._worker = w
        w.start()

    def _trash(self, paths):
        """Move files to the XDG trash (~/.local/share/Trash)."""
        if QMessageBox.question(
            self, "Move to Trash", f"Move {len(paths)} item(s) to the Trash?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        trashed = 0
        for p in paths:
            try:
                self._move_to_trash(p)
                trashed += 1
                log_info(f"Trashed: {p}")
            except Exception as e:
                log_error(f"Trash failed {p}: {e}")
                QMessageBox.warning(self, "Trash Error", f"{p}\n{e}")
        if trashed:
            self._status.showMessage(f"Moved {trashed} item(s) to Trash")

    @staticmethod
    def _move_to_trash(path):
        """Move a single file/dir to the XDG trash, avoiding name collisions."""
        trash_files = os.path.join(os.path.expanduser("~"), ".local", "share", "Trash", "files")
        trash_info = os.path.join(os.path.expanduser("~"), ".local", "share", "Trash", "info")
        os.makedirs(trash_files, exist_ok=True)
        os.makedirs(trash_info, exist_ok=True)

        basename = os.path.basename(path)
        dest = os.path.join(trash_files, basename)
        counter = 1
        while os.path.exists(dest):
            stem, ext = os.path.splitext(basename)
            dest = os.path.join(trash_files, f"{stem}.{counter}{ext}")
            counter += 1

        shutil.move(path, dest)

        info_name = os.path.basename(dest) + ".trashinfo"
        info_path = os.path.join(trash_info, info_name)
        with open(info_path, "w", encoding="utf-8") as f:
            f.write("[Trash Info]\n")
            f.write(f"Path={quote(os.path.abspath(path))}\n")
            f.write(f"DeletionDate={datetime.datetime.now().isoformat(timespec='seconds')}\n")

    def _delete(self, paths):
        if QMessageBox.question(
            self, "Delete Permanently",
            f"Permanently delete {len(paths)} item(s)? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        for p in paths:
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                log_info(f"Deleted: {p}")
            except Exception as e:
                log_error(f"Delete failed {p}: {e}")
                QMessageBox.warning(self, "Error", str(e))

    def _rename(self, path):
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=os.path.basename(path))
        if ok and name:
            new_path = os.path.join(os.path.dirname(path), name)
            try:
                os.rename(path, new_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _new_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            try:
                os.makedirs(os.path.join(self._path_edit.text(), name))
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _new_file(self):
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            try:
                with open(os.path.join(self._path_edit.text(), name), "w", encoding="utf-8"):
                    pass
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _properties(self, path):
        try:
            stat = os.stat(path)
            size = stat.st_size
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            ftype = "Directory" if os.path.isdir(path) else "File"
            QMessageBox.information(
                self, "Properties",
                f"Path: {path}\nType: {ftype}\nSize: {size:,} bytes\nModified: {mtime}\nPermissions: {oct(stat.st_mode)[-3:]}",
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _op_done(self, ok, err, op, clear_clip=False):
        if ok:
            if clear_clip:
                self._clipboard = None
                self._clipboard_cut = False
            self._status.showMessage(f"{op} complete")
        else:
            QMessageBox.warning(self, f"{op} failed", err)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2500)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = FileManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
