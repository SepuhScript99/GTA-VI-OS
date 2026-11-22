#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Terminal Emulator
Tabbed terminal emulator styled with Vice City cyberpunk themes and shell selection.
"""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QComboBox, QInputDialog, QMenuBar, QAction
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QIODevice, QProcess
from PyQt5.QtGui import QFont, QColor

from python.vice_utils import log_info, log_error

try:
    from PyQt5.QtWidgets import QPlainTextEdit
    HAS_QTE = True
except ImportError:
    HAS_QTE = False

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660

THEMES = {
    "Cyberpunk":  {"bg": "#0a0a0a", "fg": "#00ffff", "sel": "#ff00ff"},
    "Matrix":     {"bg": "#000a00", "fg": "#00ff41", "sel": "#003300"},
    "Dracula":    {"bg": "#282a36", "fg": "#f8f8f2", "sel": "#6272a4"},
    "Solarized":  {"bg": "#002b36", "fg": "#839496", "sel": "#073642"},
    "Nord":       {"bg": "#2e3440", "fg": "#d8dee9", "sel": "#4c566a"},
}

SHELLS = ["/bin/bash", "/bin/zsh", "/bin/sh", "/usr/bin/fish"]


def make_style(theme):
    t = THEMES[theme]
    return f"""
    QWidget {{ background-color: {t['bg']}; color: {t['fg']}; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }}
    QPushButton {{ background: #1a1a1a; color: {t['fg']}; border: 1px solid {t['fg']}; padding: 4px 12px; }}
    QPushButton:hover {{ background: {t['fg']}; color: {t['bg']}; }}
    QTabBar::tab {{ background: #1a1a1a; color: {t['fg']}; padding: 5px 14px; }}
    QTabBar::tab:selected {{ background: {t['fg']}; color: {t['bg']}; }}
    QTabWidget::pane {{ border: 1px solid {t['fg']}; }}
    QPlainTextEdit {{ background: {t['bg']}; color: {t['fg']}; border: none; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; font-size: 12px; }}
    QComboBox {{ background: #1a1a1a; color: {t['fg']}; border: 1px solid {t['fg']}; padding: 3px; }}
    QMenuBar {{ background: {t['bg']}; color: {t['fg']}; }}
    QMenuBar::item:selected {{ background: {t['fg']}; color: {t['bg']}; }}
    QMenu {{ background: #1a1a1a; color: {t['fg']}; border: 1px solid {t['fg']}; }}
    QMenu::item:selected {{ background: {t['fg']}; color: {t['bg']}; }}
    QLabel {{ color: {t['fg']}; }}
    """


class TerminalTab(QWidget):
    def __init__(self, shell="/bin/bash", cwd=None):
        super().__init__()
        self._shell = shell
        self._cwd = cwd or os.path.expanduser("~")
        self._process = QProcess(self)
        self._init_ui()
        self._start()

    def _init_ui(self):
        from PyQt5.QtWidgets import QPlainTextEdit, QLineEdit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("monospace", 11))
        layout.addWidget(self._output)

        input_row = QHBoxLayout()
        self._prompt = QLabel("$ ")
        self._prompt.setStyleSheet("padding: 4px; color: #ff00ff;")
        input_row.addWidget(self._prompt)

        self._input = QLineEdit()
        self._input.setFont(QFont("monospace", 11))
        self._input.setStyleSheet("background: #0a0a0a; border: none; border-top: 1px solid #1a1a1a; padding: 4px;")
        self._input.returnPressed.connect(self._send_input)
        input_row.addWidget(self._input)
        layout.addLayout(input_row)

        self._history = []
        self._hist_idx = -1
        self._input.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtCore import Qt
        if obj is self._input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Up:
                if self._history and self._hist_idx < len(self._history) - 1:
                    self._hist_idx += 1
                    self._input.setText(self._history[-(self._hist_idx + 1)])
                return True
            elif event.key() == Qt.Key_Down:
                if self._hist_idx > 0:
                    self._hist_idx -= 1
                    self._input.setText(self._history[-(self._hist_idx + 1)])
                elif self._hist_idx == 0:
                    self._hist_idx = -1
                    self._input.clear()
                return True
        return super().eventFilter(obj, event)

    def _start(self):
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        env = self._process.processEnvironment()
        env.insert("TERM", "xterm-256color")
        self._process.setProcessEnvironment(env)
        self._process.setWorkingDirectory(self._cwd)
        self._process.start(self._shell, ["-i"])
        self._output.appendPlainText(f"[Vice Terminal — {self._shell}]\n")

    def _read_output(self):
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self._output.moveCursor(self._output.textCursor().End)
        self._output.appendPlainText(data.rstrip("\n"))
        self._output.ensureCursorVisible()

    def _send_input(self):
        cmd = self._input.text()
        if cmd:
            self._history.append(cmd)
            self._hist_idx = -1
        self._process.write((cmd + "\n").encode())
        self._input.clear()

    def _on_finished(self):
        self._output.appendPlainText("\n[Process exited]")

    def terminate(self):
        self._process.terminate()


class TerminalEmulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Terminal")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._theme = "Cyberpunk"
        self._shell = "/bin/bash"
        self._apply_theme()
        self._init_ui()
        self._new_tab()

    def _apply_theme(self):
        self.setStyleSheet(make_style(self._theme))

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        bar = QHBoxLayout()
        new_btn = QPushButton("+ New Tab")
        new_btn.clicked.connect(self._new_tab)
        bar.addWidget(new_btn)

        bar.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(THEMES.keys()))
        self._theme_combo.setCurrentText(self._theme)
        self._theme_combo.currentTextChanged.connect(self._change_theme)
        bar.addWidget(self._theme_combo)

        bar.addWidget(QLabel("Shell:"))
        self._shell_combo = QComboBox()
        for sh in SHELLS:
            if os.path.exists(sh):
                self._shell_combo.addItem(sh)
        self._shell_combo.currentTextChanged.connect(lambda s: setattr(self, '_shell', s))
        bar.addWidget(self._shell_combo)

        bar.addStretch()
        top = QWidget()
        top.setLayout(bar)
        top.setStyleSheet("border-bottom: 1px solid #1a1a1a;")
        root.addWidget(top)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        root.addWidget(self._tabs)

        mb = self.menuBar()
        term_menu = mb.addMenu("Terminal")
        term_menu.addAction(QAction("New Tab", self, shortcut="Ctrl+T", triggered=self._new_tab))
        term_menu.addAction(QAction("Close Tab", self, shortcut="Ctrl+W",
                                    triggered=lambda: self._close_tab(self._tabs.currentIndex())))
        term_menu.addAction(QAction("Clear", self, shortcut="Ctrl+L", triggered=self._clear_current))

    def _new_tab(self):
        tab = TerminalTab(shell=self._shell)
        idx = self._tabs.addTab(tab, f"Terminal {self._tabs.count() + 1}")
        self._tabs.setCurrentIndex(idx)
        log_info(f"New terminal tab: {self._shell}")

    def _close_tab(self, idx):
        tab = self._tabs.widget(idx)
        if tab:
            tab.terminate()
        self._tabs.removeTab(idx)
        if self._tabs.count() == 0:
            self._new_tab()

    def _clear_current(self):
        tab = self._tabs.currentWidget()
        if tab:
            tab._output.clear()

    def _change_theme(self, theme):
        self._theme = theme
        self._apply_theme()


def main():
    app = QApplication(sys.argv)
    win = TerminalEmulator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
