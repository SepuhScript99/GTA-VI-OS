#!/usr/bin/env python3
"""Vice OS — Help Viewer. Browse docs, app reference, and keyboard shortcuts."""

import sys
import os
import glob
import subprocess
import json

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextBrowser, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; font-size: 12px; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QTextBrowser { background: #0d0d0d; color: #ccffff; border: 1px solid #1a4a4a; font-size: 12px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""

DOC_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs"),
    "/opt/vice-os/docs",
    "/usr/share/doc/vice-os",
]

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SHORTCUTS_FILE = os.path.expanduser("~/.config/vice-os/keyboard_shortcuts.json")


def md_to_html(text):
    """Minimal Markdown -> HTML conversion for the built-in docs."""
    import html as html_mod
    lines = html_mod.escape(text).splitlines()
    out = []
    in_code = False
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            close_list()
            if in_code:
                out.append("</pre></code>")
                in_code = False
            else:
                out.append("<code><pre>")
                in_code = True
            continue
        if in_code:
            out.append(line)
            continue

        if not stripped:
            close_list()
            continue
        if stripped.startswith("# "):
            close_list()
            out.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            close_list()
            out.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            close_list()
            out.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{stripped[2:]}</li>")
        elif stripped.startswith("|"):
            out.append(f"<code>{stripped}</code><br>")
        else:
            close_list()
            out.append(f"<p>{stripped}</p>")
    close_list()
    if in_code:
        out.append("</pre></code>")
    body = "\n".join(out)
    return f"""
    <html><head><style>
        body {{ font-family: 'monospace'; color: #ccffff; background: #0d0d0d; padding: 16px; }}
        h1 {{ color: #ff00ff; border-bottom: 1px solid #ff00ff; padding-bottom: 6px; }}
        h2 {{ color: #00ffff; margin-top: 18px; }}
        h3 {{ color: #aaffff; }}
        code {{ color: #00ff88; }}
        pre {{ background: #111; padding: 8px; border: 1px solid #1a4a4a; }}
        ul {{ margin-left: 18px; }}
        li {{ margin: 4px 0; }}
    </style></head><body>{body}</body></html>
    """


class HelpViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Help")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._docs = self._find_docs()
        self._init_ui()

    @staticmethod
    def _find_docs():
        """Find available documentation files."""
        docs = {}
        for d in DOC_DIRS:
            if not os.path.isdir(d):
                continue
            for path in sorted(glob.glob(os.path.join(d, "*.md"))):
                name = os.path.basename(path)
                docs.setdefault(name, path)
        return docs

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Help & Documentation")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # --- Docs tab ---
        docs_tab = QWidget()
        dl = QVBoxLayout(docs_tab)
        splitter = QSplitter(Qt.Horizontal)
        dl.addWidget(splitter)

        self._doc_list = QListWidget()
        for name in self._docs:
            self._doc_list.addItem(QListWidgetItem(name))
        self._doc_list.currentRowChanged.connect(self._show_doc)
        splitter.addWidget(self._doc_list)

        self._doc_view = QTextBrowser()
        self._doc_view.setOpenExternalLinks(True)
        splitter.addWidget(self._doc_view)
        splitter.setSizes([240, 840])
        tabs.addTab(docs_tab, "Documentation")

        # --- Apps tab ---
        apps_tab = QWidget()
        al = QVBoxLayout(apps_tab)
        self._apps_table = QTableWidget()
        self._apps_table.setColumnCount(2)
        self._apps_table.setHorizontalHeaderLabels(["Application", "Launch Command"])
        self._apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._apps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        al.addWidget(self._apps_table)
        tabs.addTab(apps_tab, "Applications")

        # --- Shortcuts tab ---
        keys_tab = QWidget()
        kl = QVBoxLayout(keys_tab)
        self._keys_table = QTableWidget()
        self._keys_table.setColumnCount(3)
        self._keys_table.setHorizontalHeaderLabels(["Action", "Shortcut", "Description"])
        self._keys_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._keys_table.setEditTriggers(QTableWidget.NoEditTriggers)
        kl.addWidget(self._keys_table)
        tabs.addTab(keys_tab, "Keyboard Shortcuts")

        # --- About tab ---
        about_tab = QWidget()
        bl = QVBoxLayout(about_tab)
        bl.setAlignment(Qt.AlignCenter)
        logo = QLabel("VICE OS")
        logo.setStyleSheet("color: #ff00ff; font-size: 48px; font-weight: bold; letter-spacing: 10px; border: none;")
        bl.addWidget(logo)
        sub = QLabel("Cyberpunk Linux — Help Center")
        sub.setStyleSheet("color: #888; font-size: 14px; border: none;")
        bl.addWidget(sub)
        bl.addSpacing(20)
        hint = QLabel("Press Win+Space for the Run Menu • Click 'vice' on the panel for all apps")
        hint.setStyleSheet("color: #555; font-size: 11px; border: none;")
        bl.addWidget(hint)
        tabs.addTab(about_tab, "About")

        # Initial content
        if self._doc_list.count() > 0:
            self._doc_list.setCurrentRow(0)
        else:
            self._doc_view.setHtml("<p>No documentation files found in docs/ directories.</p>")
        self._load_apps_table()
        self._load_shortcuts_table()

    def _show_doc(self, row):
        if row < 0:
            return
        name = self._doc_list.item(row).text()
        path = self._docs.get(name)
        if not path or not os.path.isfile(path):
            self._doc_view.setHtml(f"<p>Cannot read {name}.</p>")
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            if name.lower().endswith(".md"):
                self._doc_view.setHtml(md_to_html(text))
            else:
                self._doc_view.setPlainText(text)
        except Exception as e:
            self._doc_view.setHtml(f"<p>Error reading {name}: {e}</p>")

    def _load_apps_table(self):
        """List all Vice OS apps with their launch commands."""
        self._apps_table.setRowCount(0)
        apps = sorted(glob.glob(os.path.join(APP_DIR, "vice_*.py")))
        for path in apps:
            name = os.path.basename(path).replace("vice_", "").replace(".py", "").replace("_", " ").title()
            row = self._apps_table.rowCount()
            self._apps_table.insertRow(row)
            self._apps_table.setItem(row, 0, QTableWidgetItem(name))
            self._apps_table.setItem(row, 1, QTableWidgetItem(f"python3 {os.path.basename(path)}"))
        log_info(f"Help viewer: {len(apps)} apps listed")

    def _load_shortcuts_table(self):
        """Load keyboard shortcuts (defaults or user-customized)."""
        self._keys_table.setRowCount(0)
        shortcuts = None
        if os.path.exists(SHORTCUTS_FILE):
            try:
                with open(SHORTCUTS_FILE) as f:
                    shortcuts = json.load(f)
            except Exception:
                shortcuts = None

        if not shortcuts:
            # Fallback: show reference defaults
            shortcuts = [
                {"name": "Open Launcher", "key": "Super_L", "desc": "Open the app launcher"},
                {"name": "Open Terminal", "key": "Ctrl+Alt+T", "desc": "Open terminal emulator"},
                {"name": "Run Menu", "key": "Win+Space", "desc": "Quick command runner"},
                {"name": "Lock Screen", "key": "Super+L", "desc": "Lock the screen"},
                {"name": "Screenshot", "key": "Print", "desc": "Capture entire screen"},
            ]

        for s in shortcuts:
            row = self._keys_table.rowCount()
            self._keys_table.insertRow(row)
            self._keys_table.setItem(row, 0, QTableWidgetItem(s.get("name", "")))
            key_item = QTableWidgetItem(s.get("key", ""))
            from PyQt5.QtGui import QColor, QBrush
            key_item.setForeground(QBrush(QColor("#ff00ff")))
            self._keys_table.setItem(row, 1, key_item)
            self._keys_table.setItem(row, 2, QTableWidgetItem(s.get("desc", "")))


def main():
    app = QApplication(sys.argv)
    win = HelpViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()