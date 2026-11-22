#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Firewall Manager
Graphical frontend for UFW: rule inspection, port opening/closing, and firewall enable/disable.
"""

import sys
import os
import subprocess
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QComboBox, QGroupBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""


def run_ufw(args, sudo=True):
    cmd = (["sudo"] if sudo else []) + ["ufw"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class UFWWorker(QThread):
    done = pyqtSignal(str, bool)

    def __init__(self, args):
        super().__init__()
        self.args = args

    def run(self):
        out, ok = run_ufw(self.args)
        self.done.emit(out, ok)


class FirewallManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Firewall Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Firewall Manager (UFW)")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Status row
        status_row = QHBoxLayout()
        self._fw_status = QLabel("Status: unknown")
        self._fw_status.setFont(QFont("monospace", 11, QFont.Bold))
        status_row.addWidget(self._fw_status)
        status_row.addStretch()

        self._enable_btn = QPushButton("Enable Firewall")
        self._enable_btn.clicked.connect(lambda: self._run_cmd(["--force", "enable"], "Enabling..."))
        status_row.addWidget(self._enable_btn)

        self._disable_btn = QPushButton("Disable Firewall")
        self._disable_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        self._disable_btn.clicked.connect(self._confirm_disable)
        status_row.addWidget(self._disable_btn)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh)
        status_row.addWidget(self._refresh_btn)
        root.addLayout(status_row)

        # Rules table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["#", "To", "Action", "From", "Protocol"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table)

        # Add rule form
        add_box = QGroupBox("Add Rule")
        add_layout = QHBoxLayout(add_box)

        add_layout.addWidget(QLabel("Action:"))
        self._action_combo = QComboBox()
        self._action_combo.addItems(["allow", "deny", "reject", "limit"])
        add_layout.addWidget(self._action_combo)

        add_layout.addWidget(QLabel("Direction:"))
        self._dir_combo = QComboBox()
        self._dir_combo.addItems(["in", "out"])
        add_layout.addWidget(self._dir_combo)

        add_layout.addWidget(QLabel("Proto:"))
        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["any", "tcp", "udp"])
        add_layout.addWidget(self._proto_combo)

        add_layout.addWidget(QLabel("Port/Service:"))
        self._port_edit = QLineEdit()
        self._port_edit.setPlaceholderText("e.g. 22, 80, ssh, http")
        self._port_edit.setFixedWidth(160)
        add_layout.addWidget(self._port_edit)

        add_layout.addWidget(QLabel("From:"))
        self._from_edit = QLineEdit()
        self._from_edit.setPlaceholderText("any or IP/CIDR")
        self._from_edit.setFixedWidth(140)
        add_layout.addWidget(self._from_edit)

        add_rule_btn = QPushButton("Add Rule")
        add_rule_btn.clicked.connect(self._add_rule)
        add_layout.addWidget(add_rule_btn)
        root.addWidget(add_box)

        # Delete row
        del_row = QHBoxLayout()
        del_btn = QPushButton("Delete Selected Rule")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_btn.clicked.connect(self._delete_selected)
        del_row.addWidget(del_btn)
        del_row.addStretch()
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        del_row.addWidget(self._status_lbl)
        root.addLayout(del_row)

    def _refresh(self):
        out, ok = run_ufw(["status", "numbered"])
        if not ok:
            self._fw_status.setText("Status: UFW not available")
            self._fw_status.setStyleSheet("color: #ff4444;")
            return

        if "inactive" in out.lower():
            self._fw_status.setText("Status: INACTIVE")
            self._fw_status.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self._fw_status.setText("Status: ACTIVE")
            self._fw_status.setStyleSheet("color: #00ff88; font-weight: bold;")

        self._parse_rules(out)

    def _parse_rules(self, output):
        self._table.setRowCount(0)
        for line in output.splitlines():
            m = re.match(r'^\[\s*(\d+)\]\s+(.+?)\s+(ALLOW|DENY|REJECT|LIMIT)\s+(?:IN|OUT)?\s*(.+?)(?:\s+(tcp|udp))?$', line, re.IGNORECASE)
            if not m:
                m = re.match(r'^\[\s*(\d+)\]\s+(.+?)\s+(ALLOW IN|DENY IN|ALLOW OUT|DENY OUT|ALLOW|DENY|REJECT|LIMIT)\s+(.+)', line, re.IGNORECASE)
            if m:
                num = m.group(1)
                parts = line.split()
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(num))
                self._table.setItem(row, 1, QTableWidgetItem(parts[1] if len(parts) > 1 else ""))
                action_text = next((p for p in parts if p.upper() in ("ALLOW", "DENY", "REJECT", "LIMIT", "ALLOW IN", "DENY IN", "ALLOW OUT", "DENY OUT")), "")
                item = QTableWidgetItem(action_text.upper())
                if "ALLOW" in action_text.upper():
                    item.setForeground(QBrush(QColor("#00ff88")))
                else:
                    item.setForeground(QBrush(QColor("#ff4444")))
                self._table.setItem(row, 2, item)
                self._table.setItem(row, 3, QTableWidgetItem(parts[-1] if len(parts) > 3 else "Anywhere"))
                proto = "tcp/udp"
                if "/tcp" in line:
                    proto = "tcp"
                elif "/udp" in line:
                    proto = "udp"
                self._table.setItem(row, 4, QTableWidgetItem(proto))

    def _add_rule(self):
        port = self._port_edit.text().strip()
        if not port:
            QMessageBox.warning(self, "Missing Port", "Enter a port or service name.")
            return

        action = self._action_combo.currentText()
        direction = self._dir_combo.currentText()
        proto = self._proto_combo.currentText()
        from_ip = self._from_edit.text().strip() or "any"

        args = [action, direction]
        if from_ip != "any":
            args += ["from", from_ip]
        if proto != "any":
            args += ["proto", proto]
        args += ["to", "any", "port", port]

        self._run_cmd(args, f"Adding rule: {action} {port}")

    def _delete_selected(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a rule to delete.")
            return
        num_item = self._table.item(row, 0)
        if not num_item:
            return
        num = num_item.text()
        if QMessageBox.question(
            self, "Delete Rule", f"Delete rule #{num}?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_cmd(["--force", "delete", num], f"Deleting rule #{num}")

    def _confirm_disable(self):
        if QMessageBox.question(
            self, "Disable Firewall",
            "Disable the firewall? This removes all protection.",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._run_cmd(["disable"], "Disabling firewall...")

    def _run_cmd(self, args, msg):
        self._status_lbl.setText(msg)
        self._enable_btn.setEnabled(False)
        self._disable_btn.setEnabled(False)
        w = UFWWorker(args)
        w.done.connect(self._cmd_done)
        w.start()
        self._worker = w

    def _cmd_done(self, out, ok):
        self._enable_btn.setEnabled(True)
        self._disable_btn.setEnabled(True)
        if ok:
            self._status_lbl.setText("Done")
            log_info(f"UFW: {out[:80]}")
        else:
            self._status_lbl.setText(f"Error: {out[:80]}")
            log_error(f"UFW error: {out}")
        self._refresh()


def main():
    app = QApplication(sys.argv)
    win = FirewallManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
