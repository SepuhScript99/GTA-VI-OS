#!/usr/bin/env python3
"""Vice OS — SSH Sessions Manager. Saved hosts, quick connect, key management."""

import sys
import os
import subprocess
import json

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QSpinBox, QPlainTextEdit,
    QCheckBox, QTabWidget, QComboBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 980
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QPlainTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QCheckBox { color: #00ffff; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QLabel { color: #00ffff; }
"""

SESSIONS_FILE = os.path.expanduser("~/.config/vice-os/ssh_sessions.json")
SSH_DIR = os.path.expanduser("~/.ssh")


def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_sessions(sessions):
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        log_error(f"Session save failed: {e}")


class SessionDialog(QDialog):
    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Session" + (" - Edit" if session else ""))
        self.setFixedSize(480, 360)
        self.setStyleSheet(STYLE)
        layout = QFormLayout(self)

        self._name = QLineEdit()
        layout.addRow("Session Name:", self._name)

        self._host = QLineEdit()
        self._host.setPlaceholderText("192.168.1.10 or hostname")
        layout.addRow("Host:", self._host)

        self._user = QLineEdit()
        self._user.setPlaceholderText("root, vice, admin...")
        layout.addRow("Username:", self._user)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(22)
        layout.addRow("Port:", self._port)

        self._key_combo = QComboBox()
        self._key_combo.setEditable(True)
        self._key_combo.addItem("")  # none = password auth
        key_dir = SSH_DIR
        if os.path.isdir(key_dir):
            for f in sorted(os.listdir(key_dir)):
                if f.startswith("id_") and not f.endswith(".pub"):
                    self._key_combo.addItem(os.path.join(key_dir, f))
        layout.addRow("Identity Key:", self._key_combo)

        self._extra = QLineEdit()
        self._extra.setPlaceholderText("-X -o StrictHostKeyChecking=no")
        layout.addRow("Extra Options:", self._extra)

        if session:
            self._name.setText(session.get("name", ""))
            self._host.setText(session.get("host", ""))
            self._user.setText(session.get("user", ""))
            self._port.setValue(session.get("port", 22))
            self._key_combo.setCurrentText(session.get("key", ""))
            self._extra.setText(session.get("extra", ""))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def values(self):
        return {
            "name": self._name.text().strip(),
            "host": self._host.text().strip(),
            "user": self._user.text().strip(),
            "port": self._port.value(),
            "key": self._key_combo.currentText().strip(),
            "extra": self._extra.text().strip(),
        }


class SshWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, cmd):
        super().__init__()
        self._cmd = cmd

    def run(self):
        try:
            proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self.line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode)
        except FileNotFoundError:
            self.line.emit("ssh client not found. Install: apt install openssh-client")
            self.finished.emit(1)
        except Exception as e:
            self.line.emit(f"Error: {e}")
            self.finished.emit(1)


class SSHTerminalDialog(QDialog):
    """Simple interactive SSH terminal dialog (stdin wired via write)."""

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Session")
        self.resize(820, 560)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command and press Enter (password prompts also here)")
        self._input.returnPressed.connect(self._send)
        layout.addWidget(self._input)

        self._proc = None
        self._cmd = cmd

        close_btn = QPushButton("Disconnect")
        close_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        close_btn.clicked.connect(self._disconnect)
        layout.addWidget(close_btn)

        self._start()

    def _start(self):
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True,
                bufsize=1
            )
            import threading

            def reader():
                for line in self._proc.stdout:
                    self._output.appendPlainText(line.rstrip())
                self._output.appendPlainText("[Disconnected]")

            t = threading.Thread(target=reader, daemon=True)
            t.start()
        except Exception as e:
            self._output.appendPlainText(f"Failed to start SSH: {e}")

    def _send(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write(self._input.text() + "\n")
                self._proc.stdin.flush()
            except Exception as e:
                self._output.appendPlainText(f"Write failed: {e}")
        self._input.clear()

    def _disconnect(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.accept()

    def closeEvent(self, event):
        self._disconnect()
        super().closeEvent(event)


class SSHManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — SSH Sessions Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._sessions = load_sessions()
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — SSH Sessions Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # --- Sessions tab ---
        sess_tab = QWidget()
        sl = QVBoxLayout(sess_tab)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Name", "Host", "User", "Port", "Auth"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [2, 3, 4]:
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellDoubleClicked.connect(lambda r, c: self._connect())
        sl.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Session")
        add_btn.clicked.connect(self._add_session)
        btn_row.addWidget(add_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_session)
        btn_row.addWidget(edit_btn)
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_btn.clicked.connect(self._delete_session)
        btn_row.addWidget(del_btn)

        connect_btn = QPushButton("⌨ Connect")
        connect_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        connect_btn.clicked.connect(self._connect)
        btn_row.addWidget(connect_btn)

        term_btn = QPushButton("Open in Terminal")
        term_btn.clicked.connect(self._connect_terminal)
        btn_row.addWidget(term_btn)
        btn_row.addStretch()
        sl.addLayout(btn_row)
        tabs.addTab(sess_tab, "Sessions")

        # --- Keys tab ---
        keys_tab = QWidget()
        kl = QVBoxLayout(keys_tab)

        kl.addWidget(QLabel("SSH Keys (~/.ssh):"))
        self._key_output = QPlainTextEdit()
        self._key_output.setReadOnly(True)
        kl.addWidget(self._key_output)

        key_btns = QHBoxLayout()
        gen_btn = QPushButton("Generate New Key (ed25519)")
        gen_btn.clicked.connect(self._gen_key)
        key_btns.addWidget(gen_btn)
        list_btn = QPushButton("Refresh")
        list_btn.clicked.connect(self._list_keys)
        key_btns.addWidget(list_btn)
        key_btns.addStretch()
        kl.addLayout(key_btns)
        tabs.addTab(keys_tab, "Keys")

        self._status = QLabel("Ready — double-click a session to connect")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

        self._list_keys()

    def _refresh(self):
        self._sessions = load_sessions()
        self._table.setRowCount(0)
        for s in self._sessions:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(s.get("host", "")))
            self._table.setItem(row, 2, QTableWidgetItem(s.get("user", "")))
            self._table.setItem(row, 3, QTableWidgetItem(str(s.get("port", 22))))
            auth = "Key" if s.get("key") else "Password"
            auth_item = QTableWidgetItem(auth)
            auth_item.setForeground(QBrush(QColor("#ff00ff" if s.get("key") else "#888888")))
            self._table.setItem(row, 4, auth_item)
        self._status.setText(f"{len(self._sessions)} session(s) saved")

    def _selected_session(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._sessions):
            QMessageBox.warning(self, "No Selection", "Select a session first.")
            return None
        return self._sessions[row]

    def _add_session(self):
        dlg = SessionDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.values()
            if not vals["host"]:
                QMessageBox.warning(self, "Missing Info", "Host is required.")
                return
            if not vals["name"]:
                vals["name"] = f"{vals['user']}@{vals['host']}"
            self._sessions.append(vals)
            save_sessions(self._sessions)
            self._refresh()

    def _edit_session(self):
        s = self._selected_session()
        if not s:
            return
        dlg = SessionDialog(s, self)
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.values()
            idx = self._sessions.index(s)
            self._sessions[idx] = vals
            save_sessions(self._sessions)
            self._refresh()

    def _delete_session(self):
        s = self._selected_session()
        if not s:
            return
        if QMessageBox.question(self, "Delete", f"Delete session '{s.get('name')}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._sessions.remove(s)
        save_sessions(self._sessions)
        self._refresh()

    def _build_cmd(self, s):
        cmd = ["ssh"]
        cmd += ["-p", str(s.get("port", 22))]
        if s.get("key"):
            cmd += ["-i", s["key"]]
        if s.get("extra"):
            cmd += s["extra"].split()
        cmd.append(f"{s.get('user', 'root')}@{s['host']}")
        return cmd

    def _connect(self):
        s = self._selected_session()
        if not s:
            return
        dlg = SSHTerminalDialog(self._build_cmd(s), self)
        dlg.exec_()

    def _connect_terminal(self):
        s = self._selected_session()
        if not s:
            return
        cmd_str = " ".join(self._build_cmd(s))
        try:
            subprocess.Popen(
                ["x-terminal-emulator", "-e", cmd_str],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._status.setText(f"Opened terminal to {s['host']}")
        except FileNotFoundError:
            QMessageBox.information(
                self, "No Terminal",
                "x-terminal-emulator not found.\nUse the built-in Connect instead."
            )

    def _list_keys(self):
        if not os.path.isdir(SSH_DIR):
            self._key_output.setPlainText("~/.ssh does not exist")
            return
        lines = []
        for f in sorted(os.listdir(SSH_DIR)):
            path = os.path.join(SSH_DIR, f)
            ftype = "DIR " if os.path.isdir(path) else "KEY" if f.endswith(".pub") else "PRIV"
            size = os.path.getsize(path) if os.path.isfile(path) else 0
            lines.append(f"[{ftype}] {f}  ({size} bytes)")
        self._key_output.setPlainText("\n".join(lines) if lines else "No keys found")

    def _gen_key(self):
        name, ok = QMessageBox.question(
            self, "Generate Key",
            "Generate a new ed25519 key at ~/.ssh/id_ed25519?\n(Existing key will NOT be overwritten.)",
            QMessageBox.Yes | QMessageBox.No
        )
        if name != QMessageBox.Yes:
            return
        key_path = os.path.join(SSH_DIR, "id_ed25519")
        if os.path.exists(key_path):
            QMessageBox.warning(self, "Key Exists", f"{key_path} already exists. Not overwriting.")
            return
        try:
            os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
            r = subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-q"],
                capture_output=True, timeout=15
            )
            if r.returncode == 0:
                QMessageBox.information(self, "Key Generated",
                                        f"New key: {key_path}\nPublic key:\n"
                                        f"{open(key_path + '.pub').read()}")
                log_info("SSH ed25519 key generated")
            else:
                QMessageBox.warning(self, "Failed", r.stderr.decode()[:200])
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
        self._list_keys()


def main():
    app = QApplication(sys.argv)
    win = SSHManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()