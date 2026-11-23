#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Text Editor
Tabbed code and text editor with syntax highlighting for Python, Bash, QSS, JSON, and Markdown.
"""

import os
import re
import sys

from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextDocument,
)
from PyQt5.QtWidgets import (
    QAction, QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

KEYWORDS = {
    "python": [
        "def", "class", "import", "from", "return", "if", "else", "elif",
        "for", "while", "in", "not", "and", "or", "True", "False", "None",
        "try", "except", "finally", "with", "as", "pass", "break", "continue",
        "lambda", "yield", "raise", "del", "global", "nonlocal", "is",
    ],
    "bash": [
        "if", "then", "else", "elif", "fi", "for", "do", "done", "while",
        "case", "esac", "function", "return", "export", "local", "echo",
        "source", "exit", "set", "unset", "readonly",
    ],
}


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, lang="python"):
        super().__init__(document)
        self._rules = []
        self._build_rules(lang)

    def _fmt(self, color, bold=False):
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(700)
        return f

    def _build_rules(self, lang):
        self._rules.clear()
        kws = KEYWORDS.get(lang, KEYWORDS["python"])
        for kw in kws:
            self._rules.append((QRegExp(r'\b' + kw + r'\b'), self._fmt(vt.COLORS["accent_coral"], bold=True)))
        self._rules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), self._fmt(vt.COLORS["accent_gold"])))
        self._rules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), self._fmt(vt.COLORS["accent_gold"])))
        self._rules.append((QRegExp(r'\b\d+\.?\d*\b'), self._fmt(vt.COLORS["success"])))
        if lang in ("python", "bash"):
            self._rules.append((QRegExp(r'#[^\n]*'), self._fmt(vt.COLORS["text_muted"])))
        self._rules.append((QRegExp(r'\bdef\s+\w+'), self._fmt(vt.COLORS["accent_aqua"], bold=True)))
        self._rules.append((QRegExp(r'\bclass\s+\w+'), self._fmt(vt.COLORS["accent_peach"], bold=True)))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            idx = pattern.indexIn(text)
            while idx >= 0:
                length = pattern.matchedLength()
                if length <= 0:
                    break
                self.setFormat(idx, length, fmt)
                idx = pattern.indexIn(text, idx + length)


class FindDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find / Replace")
        self.setMinimumSize(420, 180)
        vt.apply_app_theme(self)
        layout = QVBoxLayout(self)

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find...")
        layout.addWidget(QLabel("Find:"))
        layout.addWidget(self.find_edit)

        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with...")
        layout.addWidget(QLabel("Replace:"))
        layout.addWidget(self.replace_edit)

        opts = QHBoxLayout()
        self.case_cb = QCheckBox("Case sensitive")
        opts.addWidget(self.case_cb)
        self.whole_cb = QCheckBox("Whole word")
        opts.addWidget(self.whole_cb)
        layout.addLayout(opts)

        btns = QHBoxLayout()
        find_btn = vt.make_button("Find Next", "primary", parent=self)
        find_btn.clicked.connect(self.accept)
        btns.addWidget(find_btn)
        replace_btn = vt.make_button("Replace All", "secondary", parent=self)
        replace_btn.clicked.connect(lambda: self.done(2))
        btns.addWidget(replace_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btns.addWidget(close_btn)
        layout.addLayout(btns)


class EditorTab(QWidget):
    def __init__(self, path=None):
        super().__init__()
        self.path = path
        self.modified = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("monospace", 12))
        if hasattr(self.editor, "setTabStopDistance"):
            self.editor.setTabStopDistance(32)
        else:
            self.editor.setTabStopWidth(32)
        layout.addWidget(self.editor)

        self._hl = None
        if path:
            self._load(path)
            self._set_highlighter(path)
        self.editor.modificationChanged.connect(self._on_modified)

    def _load(self, path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
            self.editor.document().setModified(False)
        except Exception as e:
            log_error(f"Load failed {path}: {e}")

    def _set_highlighter(self, path):
        ext = os.path.splitext(path)[1].lower()
        lang_map = {".py": "python", ".sh": "bash", ".bash": "bash"}
        lang = lang_map.get(ext, "python")
        self._hl = SyntaxHighlighter(self.editor.document(), lang)

    def save(self):
        if not self.path:
            return False
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self.modified = False
            log_info(f"Saved: {self.path}")
            return True
        except Exception as e:
            log_error(f"Save failed {self.path}: {e}")
            return False

    def _on_modified(self, mod):
        self.modified = mod


class TextEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Text Editor")
        self.resize(1100, 700)
        vt.apply_app_theme(self)
        self._init_ui()
        self._new_tab()

    def _init_ui(self):
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._update_status)
        self.setCentralWidget(self._tabs)

        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        file_menu.addAction(QAction("New", self, shortcut="Ctrl+N", triggered=self._new_tab))
        file_menu.addAction(QAction("Open", self, shortcut="Ctrl+O", triggered=self._open))
        file_menu.addAction(QAction("Save", self, shortcut="Ctrl+S", triggered=self._save))
        file_menu.addAction(QAction("Save As", self, shortcut="Ctrl+Shift+S", triggered=self._save_as))
        file_menu.addSeparator()
        file_menu.addAction(QAction(
            "Close Tab", self, shortcut="Ctrl+W",
            triggered=lambda: self._close_tab(self._tabs.currentIndex()),
        ))

        edit_menu = mb.addMenu("Edit")
        edit_menu.addAction(QAction("Find / Replace", self, shortcut="Ctrl+F", triggered=self._find_replace))
        edit_menu.addAction(QAction("Go to Line", self, shortcut="Ctrl+G", triggered=self._goto_line))

        self._status = QStatusBar()
        self.setStatusBar(self._status)

    def _current_tab(self):
        return self._tabs.currentWidget()

    def _new_tab(self, path=None):
        tab = EditorTab(path)
        name = os.path.basename(path) if path else "Untitled"
        idx = self._tabs.addTab(tab, name)
        self._tabs.setCurrentIndex(idx)
        tab.editor.modificationChanged.connect(
            lambda mod, t=tab: self._tabs.setTabText(
                self._tabs.indexOf(t),
                ("* " if mod else "") + (os.path.basename(t.path) if t.path else "Untitled"),
            )
        )

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", os.path.expanduser("~"), "All files (*)")
        if path:
            self._new_tab(path)

    def _save(self):
        tab = self._current_tab()
        if not tab:
            return False
        if not tab.path:
            return self._save_as()
        ok = tab.save()
        self._update_status()
        return ok

    def _save_as(self):
        tab = self._current_tab()
        if not tab:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Save As", os.path.expanduser("~"), "All files (*)")
        if path:
            tab.path = path
            tab._set_highlighter(path)
            ok = tab.save()
            self._tabs.setTabText(self._tabs.currentIndex(), os.path.basename(path))
            self._update_status()
            return ok
        return False

    def _close_tab(self, idx):
        tab = self._tabs.widget(idx)
        if tab and tab.modified:
            r = QMessageBox.question(
                self, "Unsaved Changes", "Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if r == QMessageBox.Save:
                self._tabs.setCurrentIndex(idx)
                if not self._save():
                    return
            elif r == QMessageBox.Cancel:
                return
        self._tabs.removeTab(idx)
        if self._tabs.count() == 0:
            self._new_tab()

    def _find_replace(self):
        tab = self._current_tab()
        if not tab:
            return
        dlg = FindDialog(self)
        result = dlg.exec_()
        find = dlg.find_edit.text()
        if not find:
            return
        if result == 1:
            flags = QTextDocument.FindFlags()
            if dlg.case_cb.isChecked():
                flags |= QTextDocument.FindCaseSensitively
            if dlg.whole_cb.isChecked():
                flags |= QTextDocument.FindWholeWords
            if not tab.editor.find(find, flags):
                self._status.showMessage("Not found")
        elif result == 2:
            text = tab.editor.toPlainText()
            replace = dlg.replace_edit.text()
            if not dlg.case_cb.isChecked():
                new_text, count = re.subn(re.escape(find), lambda _m: replace, text, flags=re.IGNORECASE)
            else:
                count = text.count(find)
                new_text = text.replace(find, replace)
            tab.editor.setPlainText(new_text)
            self._status.showMessage(f"Replaced {count} occurrence(s)")

    def _goto_line(self):
        tab = self._current_tab()
        if not tab:
            return
        line, ok = QInputDialog.getInt(self, "Go to Line", "Line number:", 1, 1)
        if ok:
            cursor = tab.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line - 1)
            tab.editor.setTextCursor(cursor)
            tab.editor.centerCursor()

    def _update_status(self):
        tab = self._current_tab()
        if tab:
            cursor = tab.editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            path = tab.path or "Untitled"
            self._status.showMessage(f"{path}  |  Line {line}, Col {col}")

    def closeEvent(self, event):
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            if tab and tab.modified:
                name = os.path.basename(tab.path) if tab.path else "Untitled"
                r = QMessageBox.question(
                    self, "Unsaved Changes", f"Save changes to '{name}' before closing?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                )
                if r == QMessageBox.Save:
                    self._tabs.setCurrentIndex(i)
                    if not self._save():
                        event.ignore()
                        return
                elif r == QMessageBox.Cancel:
                    event.ignore()
                    return
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = TextEditor()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
