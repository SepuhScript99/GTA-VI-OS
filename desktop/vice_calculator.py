#!/usr/bin/env python3
"""Vice OS — Calculator. Basic + scientific modes with history tape."""

import sys
import os
import math

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTabWidget, QTextEdit, QLineEdit, QSplitter
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 560
WINDOW_HEIGHT = 560

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton {
    background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff;
    padding: 10px; font-size: 14px; font-family: monospace;
}
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:pressed { background: #ff00ff; color: #0a0a0a; }
QPushButton#opBtn { color: #ff00ff; border-color: #ff00ff; }
QPushButton#opBtn:hover { background: #ff00ff; color: #0a0a0a; }
QPushButton#eqBtn { background: #003333; border-color: #00ffff; font-weight: bold; }
QPushButton#eqBtn:hover { background: #00ffff; }
QLineEdit {
    background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff;
    padding: 8px; font-size: 18px; font-family: monospace;
}
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QLabel { color: #00ffff; }
"""

SAFE_NAMES = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log10, "ln": math.log, "log2": math.log2,
    "exp": math.exp, "abs": abs, "round": round,
    "pi": math.pi, "e": math.e,
    "floor": math.floor, "ceil": math.ceil,
    "factorial": math.factorial,
}


def safe_eval(expr):
    """Safely evaluate a mathematical expression."""
    if not expr:
        return 0
    # Disallow dangerous tokens
    lowered = expr.lower()
    for bad in ("__", "import", "open", "exec", "eval", "lambda", "os.", "sys."):
        if bad in lowered:
            raise ValueError("Disallowed token")
    result = eval(expr, {"__builtins__": {}}, SAFE_NAMES)
    if isinstance(result, float):
        if result == int(result) and abs(result) < 1e15:
            return int(result)
    return result


class BasicCalc(QWidget):
    def __init__(self, tape):
        super().__init__()
        self._tape = tape
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        self._display = QLineEdit("0")
        self._display.setFont(QFont("monospace", 20))
        self._display.setAlignment(Qt.AlignRight)
        root.addWidget(self._display)

        grid = QGridLayout()
        grid.setSpacing(4)

        buttons = [
            ("C", 0, 0, "clear"), ("±", 0, 1, "sign"), ("%", 0, 2, "op"), ("÷", 0, 3, "op"),
            ("7", 1, 0, "num"), ("8", 1, 1, "num"), ("9", 1, 2, "num"), ("×", 1, 3, "op"),
            ("4", 2, 0, "num"), ("5", 2, 1, "num"), ("6", 2, 2, "num"), ("−", 2, 3, "op"),
            ("1", 3, 0, "num"), ("2", 3, 1, "num"), ("3", 3, 2, "num"), ("+", 3, 3, "op"),
            ("0", 4, 0, "num"), (".", 4, 1, "num"), ("⌫", 4, 2, "back"), ("=", 4, 3, "eq"),
        ]

        for text, row, col, kind in buttons:
            btn = QPushButton(text)
            if kind == "op":
                btn.setObjectName("opBtn")
            if kind == "eq":
                btn.setObjectName("eqBtn")
            btn.clicked.connect(lambda _, t=text, k=kind: self._press(t, k))
            grid.addWidget(btn, row, col)

        root.addLayout(grid)
        root.addStretch()

    def _press(self, text, kind):
        current = self._display.text()

        if kind == "clear":
            self._display.setText("0")
        elif kind == "back":
            self._display.setText(current[:-1] or "0")
        elif kind == "sign":
            if current.startswith("-"):
                self._display.setText(current[1:])
            elif current != "0":
                self._display.setText("-" + current)
        elif kind == "eq":
            self._evaluate()
        else:
            # Translate display symbols to Python operators
            trans = {"÷": "/", "×": "*", "−": "-", "+": "+", "%": "%"}
            sym = trans.get(text, text)
            if current == "0" and sym not in (".", "+", "-", "*", "/", "%"):
                self._display.setText(sym)
            else:
                self._display.setText(current + sym)

    def _evaluate(self):
        expr = self._display.text()
        trans = str.maketrans({"÷": "/", "×": "*", "−": "-"})
        expr = expr.translate(trans)
        try:
            result = safe_eval(expr)
            self._tape.append(f"{expr} = {result}")
            self._display.setText(str(result))
        except Exception as e:
            self._display.setText("Error")
            self._tape.append(f"{expr} = ERROR ({e})")


class SciCalc(QWidget):
    def __init__(self, tape):
        super().__init__()
        self._tape = tape
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        self._display = QLineEdit("0")
        self._display.setFont(QFont("monospace", 18))
        self._display.setAlignment(Qt.AlignRight)
        root.addWidget(self._display)

        grid = QGridLayout()
        grid.setSpacing(3)

        buttons = [
            ("sqrt(", 0, 0, "fn"), ("sin(", 0, 1, "fn"), ("cos(", 0, 2, "fn"), ("tan(", 0, 3, "fn"), ("π", 0, 4, "const"),
            ("x^2", 1, 0, "sq"), ("x^3", 1, 1, "cube"), ("x^y", 1, 2, "pow"), ("e^x", 1, 3, "exp"), ("e", 1, 4, "const"),
            ("ln(", 2, 0, "fn"), ("log(", 2, 1, "fn"), ("log2(", 2, 2, "fn"), ("n!", 2, 3, "fact"), ("(", 2, 4, "paren"),
            ("7", 3, 0, "num"), ("8", 3, 1, "num"), ("9", 3, 2, "num"), ("÷", 3, 3, "op"), (")", 3, 4, "paren"),
            ("4", 4, 0, "num"), ("5", 4, 1, "num"), ("6", 4, 2, "num"), ("×", 4, 3, "op"), ("C", 4, 4, "clear"),
            ("1", 5, 0, "num"), ("2", 5, 1, "num"), ("3", 5, 2, "num"), ("−", 5, 3, "op"), ("⌫", 5, 4, "back"),
            ("0", 6, 0, "num"), (".", 6, 1, "num"), ("abs(", 6, 2, "fn"), ("+", 6, 3, "op"), ("=", 6, 4, "eq"),
        ]

        for text, row, col, kind in buttons:
            btn = QPushButton(text)
            if kind in ("op", "fn", "const", "sq", "cube", "pow", "exp", "fact"):
                btn.setObjectName("opBtn")
            if kind == "eq":
                btn.setObjectName("eqBtn")
            btn.clicked.connect(lambda _, t=text, k=kind: self._press(t, k))
            grid.addWidget(btn, row, col)

        root.addLayout(grid)
        root.addStretch()

    def _press(self, text, kind):
        current = self._display.text()

        if kind == "clear":
            self._display.setText("0")
        elif kind == "back":
            self._display.setText(current[:-1] or "0")
        elif kind == "eq":
            self._evaluate()
        elif kind == "sq":
            self._insert("**2")
        elif kind == "cube":
            self._insert("**3")
        elif kind == "pow":
            self._insert("**")
        elif kind == "exp":
            self._insert("exp(")
        elif kind == "fact":
            self._insert("factorial(")
        elif text == "π":
            self._insert("pi")
        elif text == "e":
            self._insert("e")
        else:
            trans = {"÷": "/", "×": "*", "−": "-"}
            sym = trans.get(text, text)
            if current == "0" and sym not in (".", "(", "+", "-", "*", "/", "sqrt(", "sin(", "cos(", "tan(", "ln(", "log(", "log2(", "abs(", "exp("):
                self._display.setText(sym)
            else:
                self._display.setText(current + sym)

    def _insert(self, text):
        current = self._display.text()
        self._display.setText(current + text)

    def _evaluate(self):
        expr = self._display.text()
        trans = str.maketrans({"÷": "/", "×": "*", "−": "-"})
        expr = expr.translate(trans)
        try:
            result = safe_eval(expr)
            self._tape.append(f"{expr} = {result}")
            self._display.setText(str(result))
        except Exception as e:
            self._display.setText("Error")
            self._tape.append(f"{expr} = ERROR ({e})")


class Calculator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Calculator")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        self._tape = QTextEdit()
        self._tape.setReadOnly(True)
        self._tape.setMaximumHeight(100)
        root.addWidget(self._tape)

        tabs.addTab(BasicCalc(self._tape), "Basic")
        tabs.addTab(SciCalc(self._tape), "Scientific")


def main():
    app = QApplication(sys.argv)
    win = Calculator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()