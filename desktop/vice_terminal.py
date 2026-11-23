#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Terminal Emulator.
Tabbed terminal emulator styled with Leonida Coastal Dusk and selectable shells.
"""

import os
import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QComboBox, QAction, QPlainTextEdit, QLineEdit
)
from PyQt5.QtCore import Qt, QEvent, QProcess
from PyQt5.QtGui import QFont

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info  # noqa: E402
from vice_theme import COLORS, CJK_FONT_FAMILIES, MONO_STACK, configure_cjk_fonts  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 660

THEMES = {
    "Leonida Dusk": {
        "bg": COLORS["bg_canvas"],
        "surface": COLORS["bg_surface"],
        "fg": COLORS["text_primary"],
        "accent": COLORS["accent_coral"],
        "border": COLORS["border"],
    },
    "Matrix": {"bg": "#08100b", "surface": "#101a14", "fg": "#a7f3d0", "accent": "#34d399", "border": "#1f3a2a"},
    "Dracula": {"bg": "#282a36", "surface": "#1e2029", "fg": "#f8f8f2", "accent": "#bd93f9", "border": "#44475a"},
    "Solarized": {"bg": "#002b36", "surface": "#073642", "fg": "#eee8d5", "accent": "#2aa198", "border": "#586e75"},
    "Nord": {"bg": "#2e3440", "surface": "#252a34", "fg": "#eceff4", "accent": "#88c0d0", "border": "#4c566a"},
}

SHELLS = ["/bin/bash", "/bin/zsh", "/bin/sh", "/usr/bin/fish"]


def make_style(theme):
    t = THEMES[theme]
    font_list = ", ".join(f'"{f}"' for f in CJK_FONT_FAMILIES)
    return (
        f"QWidget {{ background-color: {t['bg']}; color: {t['fg']}; font-family: {font_list}; }}"
        f"QPushButton {{ background: {t['surface']}; color: {t['fg']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 5px 12px; }}"
        f"QPushButton:hover {{ border-color: {t['accent']}; background: {t['surface']}; }}"
        f"QTabBar::tab {{ background: {t['surface']}; color: {t['fg']}; padding: 6px 14px; border: 1px solid {t['border']}; border-bottom: none; }}"
        f"QTabBar::tab:selected {{ border-bottom: 2px solid {t['accent']}; color: {t['accent']}; font-weight: 600; }}"
        f"QTabWidget::pane {{ border: 1px solid {t['border']}; }}"
        f"QPlainTextEdit {{ background: {t['bg']}; color: {t['fg']}; border: none; font-family: {MONO_STACK}; font-size: 12px; }}"
        f"QLineEdit {{ background: {t['surface']}; color: {t['fg']}; border: none; border-top: 1px solid {t['border']}; font-family: {MONO_STACK}; font-size: 12px; padding: 6px; }}"
        f"QComboBox {{ background: {t['surface']}; color: {t['fg']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 4px 8px; }}"
        f"QMenuBar {{ background: {t['surface']}; color: {t['fg']}; border-bottom: 1px solid {t['border']}; }}"
        f"QMenuBar::item:selected {{ background: {t['accent']}; color: {t['bg']}; }}"
        f"QMenu {{ background: {t['surface']}; color: {t['fg']}; border: 1px solid {t['border']}; }}"
        f"QMenu::item:selected {{ background: {t['accent']}; color: {t['bg']}; }}"
        f"QLabel {{ color: {t['fg']}; }}"
    )


class TerminalTab(QWidget):
    def __init__(self, shell="/bin/bash", cwd=None):
        super().__init__()
        self._shell = shell
        self._cwd = cwd or os.path.expanduser("~")
        self._process = QProcess(self)
        self._init_ui()
        self._start()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("DejaVu Sans Mono", 11))
        layout.addWidget(self._output)

        input_row = QHBoxLayout()
        self._prompt = QLabel("$ ")
        self._prompt.setStyleSheet(f"padding: 4px 6px; color: {COLORS['accent_aqua']}; font-weight: bold;")
        input_row.addWidget(self._prompt)

        self._input = QLineEdit()
        self._input.setFont(QFont("DejaVu Sans Mono", 11))
        self._input.returnPressed.connect(self._send_input)
        input_row.addWidget(self._input)
        layout.addLayout(input_row)

        self._history = []
        self._hist_idx = -1
        self._input.installEventFilter(self)

    def eventFilter(self, obj, event):
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
        if self._process.state() != QProcess.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(500):
                self._process.kill()
                self._process.waitForFinished(300)


class TerminalEmulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Terminal")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._theme = "Leonida Dusk"
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

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(8)
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
        if self._shell_combo.count() == 0:
            self._shell_combo.addItem("/bin/sh")
        self._shell = self._shell_combo.currentText()
        self._shell_combo.currentTextChanged.connect(lambda s: setattr(self, "_shell", s))
        bar.addWidget(self._shell_combo)

        bar.addStretch()
        top = QWidget()
        top.setLayout(bar)
        top.setStyleSheet(f"border-bottom: 1px solid {COLORS['border']};")
        root.addWidget(top)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        root.addWidget(self._tabs)

        mb = self.menuBar()
        term_menu = mb.addMenu("Terminal")
        term_menu.addAction(QAction("New Tab", self, shortcut="Ctrl+T", triggered=self._new_tab))
        term_menu.addAction(
            QAction("Close Tab", self, shortcut="Ctrl+W", triggered=lambda: self._close_tab(self._tabs.currentIndex()))
        )
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

    def closeEvent(self, event):
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            if tab is not None:
                tab.terminate()
        event.accept()


def main():
    app = QApplication(sys.argv)
    configure_cjk_fonts(app)
    win = TerminalEmulator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
