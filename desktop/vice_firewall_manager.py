#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Firewall Manager.
Graphical frontend for UFW: rule inspection, port opening/closing, and firewall enable/disable.
"""

import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QComboBox, QGroupBox, QAbstractItemView
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info, log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 920
WINDOW_HEIGHT = 640
_PORT_RE = re.compile(r"^[A-Za-z0-9:_-]+$")
_FROM_RE = re.compile(r"^[A-Za-z0-9.:/]+$")


def read_ufw_conf_enabled():
    conf = "/etc/ufw/ufw.conf"
    if not os.path.isfile(conf):
        return None
    try:
        with open(conf, encoding="utf-8", errors="replace") as fp:
            for line in fp:
                line = line.strip()
                if line.startswith("ENABLED="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                    return val == "yes"
    except OSError:
        pass
    return None


class UFWWorker(QThread):
    done = pyqtSignal(str, bool)

    def __init__(self, args, use_priv=True):
        super().__init__()
        self.args = list(args)
        self.use_priv = use_priv
        self._stopped = False
        self._proc = None

    def stop(self):
        self._stopped = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.3)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass

    def run(self):
        ufw_bin = shutil.which("ufw") or "/usr/sbin/ufw"
        cmd = [ufw_bin] + self.args
        is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
        if self.use_priv and not is_root and shutil.which("pkexec"):
            cmd = ["pkexec"] + cmd
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = self._proc.communicate(timeout=20)
            if self._stopped:
                return
            out = (stdout or "").strip() or (stderr or "").strip()
            self.done.emit(out, self._proc.returncode == 0)
        except Exception as e:
            if not self._stopped:
                self.done.emit(str(e), False)
        finally:
            self._proc = None


class FirewallManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Firewall Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 520)
        apply_app_theme(self)
        self._worker = None
        self._init_ui()
        self._load_passive_status()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Firewall Manager (UFW)",
            subtitle="Inspect packet filter status, add allow/deny rules, and manage active rules",
            icon_name="security-high",
            badge_text="UFW",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        status_row = QHBoxLayout()
        self._fw_status = QLabel("Status: checking...")
        self._fw_status.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self._fw_status)
        status_row.addStretch()

        self._enable_btn = make_button("Enable Firewall", variant="primary", parent=self)
        self._enable_btn.clicked.connect(lambda: self._run_cmd(["--force", "enable"], "Enabling..."))
        status_row.addWidget(self._enable_btn)

        self._disable_btn = make_button("Disable Firewall", variant="danger", parent=self)
        self._disable_btn.clicked.connect(self._confirm_disable)
        status_row.addWidget(self._disable_btn)

        self._refresh_btn = make_button("Inspect Rules", variant="secondary", parent=self)
        self._refresh_btn.clicked.connect(self._refresh)
        status_row.addWidget(self._refresh_btn)
        root.addLayout(status_row)

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
        root.addWidget(self._table, 1)

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
        self._port_edit.setPlaceholderText("e.g. 22, 80, ssh")
        self._port_edit.setMinimumWidth(130)
        add_layout.addWidget(self._port_edit)

        add_layout.addWidget(QLabel("From:"))
        self._from_edit = QLineEdit()
        self._from_edit.setPlaceholderText("any or IP/CIDR")
        self._from_edit.setMinimumWidth(120)
        add_layout.addWidget(self._from_edit)

        add_rule_btn = make_button("Add Rule", variant="primary", parent=self)
        add_rule_btn.clicked.connect(self._add_rule)
        add_layout.addWidget(add_rule_btn)
        root.addWidget(add_box)

        del_row = QHBoxLayout()
        del_btn = make_button("Delete Selected Rule", variant="danger", parent=self)
        del_btn.clicked.connect(self._delete_selected)
        del_row.addWidget(del_btn)
        del_row.addStretch()
        self._status_lbl = QLabel("Ready (click Inspect Rules to authenticate & list UFW rules)")
        self._status_lbl.setObjectName("MutedLabel")
        del_row.addWidget(self._status_lbl)
        root.addLayout(del_row)

    def _load_passive_status(self):
        enabled = read_ufw_conf_enabled()
        if enabled is True:
            self._fw_status.setText("Status: CONFIGURED ACTIVE")
            self._fw_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        elif enabled is False:
            self._fw_status.setText("Status: INACTIVE (from ufw.conf)")
            self._fw_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
        else:
            self._fw_status.setText("Status: Click 'Inspect Rules' to query UFW")
            self._fw_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")

    def _refresh(self):
        self._start_worker(["status", "numbered"], "Inspecting UFW rules...", self._on_status_done)

    def _on_status_done(self, out, ok):
        if not ok:
            self._fw_status.setText("Status: UFW unavailable or cancelled")
            self._fw_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
            self._status_lbl.setText(out[:80] if out else "Cancelled")
            return
        if "inactive" in out.lower():
            self._fw_status.setText("Status: INACTIVE")
            self._fw_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
        else:
            self._fw_status.setText("Status: ACTIVE")
            self._fw_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self._parse_rules(out)
        self._status_lbl.setText(f"Loaded {self._table.rowCount()} rule(s)")

    def _parse_rules(self, output):
        self._table.setRowCount(0)
        for line in output.splitlines():
            m = re.match(
                r"^\[\s*(\d+)\]\s+(.+?)\s+(ALLOW IN|DENY IN|REJECT IN|LIMIT IN|ALLOW OUT|DENY OUT|ALLOW|DENY|REJECT|LIMIT)\s+(.*)$",
                line.strip(),
                re.IGNORECASE,
            )
            if m:
                num = m.group(1)
                to_col = m.group(2).strip()
                action_text = m.group(3).upper()
                from_col = m.group(4).strip() or "Anywhere"
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(num))
                self._table.setItem(row, 1, QTableWidgetItem(to_col))
                item = QTableWidgetItem(action_text)
                col_hex = COLORS["success"] if "ALLOW" in action_text else COLORS["danger"]
                item.setForeground(QBrush(QColor(col_hex)))
                self._table.setItem(row, 2, item)
                self._table.setItem(row, 3, QTableWidgetItem(from_col))
                proto = "tcp" if "/tcp" in to_col.lower() else "udp" if "/udp" in to_col.lower() else "tcp/udp"
                self._table.setItem(row, 4, QTableWidgetItem(proto))

    def _add_rule(self):
        port = self._port_edit.text().strip()
        if not port or not _PORT_RE.match(port):
            QMessageBox.warning(self, "Invalid Port", "Enter a valid port number, range, or service name.")
            return

        from_ip = self._from_edit.text().strip() or "any"
        if from_ip != "any" and not _FROM_RE.match(from_ip):
            QMessageBox.warning(self, "Invalid Source", "Enter 'any' or a valid IP/CIDR.")
            return

        action = self._action_combo.currentText()
        direction = self._dir_combo.currentText()
        proto = self._proto_combo.currentText()

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

    def _start_worker(self, args, msg, slot):
        if self._worker is not None and self._worker.isRunning():
            self._status_lbl.setText("Another UFW operation is already running...")
            return
        self._status_lbl.setText(msg)
        self._enable_btn.setEnabled(False)
        self._disable_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        w = UFWWorker(args)
        w.done.connect(lambda out, ok: self._finish_worker(out, ok, slot))
        w.start()
        self._worker = w

    def _finish_worker(self, out, ok, slot):
        self._enable_btn.setEnabled(True)
        self._disable_btn.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        slot(out, ok)

    def _run_cmd(self, args, msg):
        self._start_worker(args, msg, self._cmd_done)

    def _cmd_done(self, out, ok):
        if ok:
            self._status_lbl.setText("Done")
            log_info(f"UFW: {out[:80]}")
            self._refresh()
        else:
            self._status_lbl.setText(f"Error: {out[:80]}")
            log_error(f"UFW error: {out}")

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = FirewallManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
