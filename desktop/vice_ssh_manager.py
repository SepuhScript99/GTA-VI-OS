#!/usr/bin/env python3
"""Vice OS — SSH Sessions Manager. Saved hosts, quick connect, key management."""

import json
import os
import shlex
import shutil
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 980
WINDOW_HEIGHT = 620

SESSIONS_FILE = os.path.expanduser("~/.config/vice-os/ssh_sessions.json")
SSH_DIR = os.path.expanduser("~/.ssh")


def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def save_sessions(sessions):
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        log_error(f"Session save failed: {e}")


class SessionDialog(QDialog):
    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Session" + (" - Edit" if session else ""))
        self.setMinimumSize(480, 360)
        vt.apply_app_theme(self)
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
        self._key_combo.addItem("")
        if os.path.isdir(SSH_DIR):
            for fname in sorted(os.listdir(SSH_DIR)):
                if fname.startswith("id_") and not fname.endswith(".pub"):
                    self._key_combo.addItem(os.path.join(SSH_DIR, fname))
        layout.addRow("Identity Key:", self._key_combo)

        self._extra = QLineEdit()
        self._extra.setPlaceholderText("-X -o StrictHostKeyChecking=no")
        layout.addRow("Extra Options:", self._extra)

        if session:
            self._name.setText(session.get("name", ""))
            self._host.setText(session.get("host", ""))
            self._user.setText(session.get("user", ""))
            self._port.setValue(int(session.get("port", 22) or 22))
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


class InteractiveSshWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self._cmd = list(cmd)
        self._proc = None
        self._cancelled = False

    def send_input(self, text):
        if self._proc is not None and self._proc.poll() is None and self._proc.stdin:
            try:
                self._proc.stdin.write(text + "\n")
                self._proc.stdin.flush()
                return True, ""
            except Exception as e:
                return False, str(e)
        return False, "SSH process is not active"

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if self._proc.stdout:
                for line in self._proc.stdout:
                    if self._cancelled:
                        break
                    self.line.emit(line.rstrip())
            rc = self._proc.wait()
            if not self._cancelled:
                self.line.emit("[Disconnected]")
                self.finished.emit(rc)
        except FileNotFoundError:
            if not self._cancelled:
                self.line.emit("ssh client not found. Install: apt install openssh-client")
                self.finished.emit(1)
        except Exception as e:
            if not self._cancelled:
                self.line.emit(f"Error: {e}")
                self.finished.emit(1)


class SSHTerminalDialog(QDialog):
    """Interactive SSH output/command dialog using a Qt signal-safe QThread."""

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Session")
        self.resize(820, 560)
        vt.apply_app_theme(self)
        layout = QVBoxLayout(self)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command and press Enter")
        self._input.returnPressed.connect(self._send)
        layout.addWidget(self._input)

        self._worker = InteractiveSshWorker(cmd, parent=self)
        self._worker.line.connect(self._output.appendPlainText)

        close_btn = vt.make_button("Disconnect", "danger", parent=self)
        close_btn.clicked.connect(self._disconnect)
        layout.addWidget(close_btn)

        self._worker.start()

    def _send(self):
        ok, err = self._worker.send_input(self._input.text())
        if not ok:
            self._output.appendPlainText(f"Write failed: {err}")
        self._input.clear()

    def _disconnect(self):
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self.accept()

    def closeEvent(self, event):
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)


class SSHManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — SSH Sessions Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        vt.apply_app_theme(self)
        self._sessions = load_sessions()
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "SSH Sessions Manager",
            "Saved remote hosts, quick connect and ~/.ssh key management",
            icon_name="utilities-terminal",
            badge_text="SSH",
            badge_variant="aqua",
            parent=self,
        ))

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        sess_tab = QWidget()
        sl = QVBoxLayout(sess_tab)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Name", "Host", "User", "Port", "Auth"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in (2, 3, 4):
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.cellDoubleClicked.connect(lambda r, c: self._connect())
        sl.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = vt.make_button("+ Add Session", "secondary", parent=sess_tab)
        add_btn.clicked.connect(self._add_session)
        btn_row.addWidget(add_btn)
        edit_btn = vt.make_button("Edit", "secondary", parent=sess_tab)
        edit_btn.clicked.connect(self._edit_session)
        btn_row.addWidget(edit_btn)
        del_btn = vt.make_button("Delete", "danger", parent=sess_tab)
        del_btn.clicked.connect(self._delete_session)
        btn_row.addWidget(del_btn)

        connect_btn = vt.make_button("Connect", "primary", parent=sess_tab)
        connect_btn.clicked.connect(self._connect)
        btn_row.addWidget(connect_btn)

        term_btn = vt.make_button("Open in Terminal", "secondary", parent=sess_tab)
        term_btn.clicked.connect(self._connect_terminal)
        btn_row.addWidget(term_btn)
        btn_row.addStretch()
        sl.addLayout(btn_row)
        tabs.addTab(sess_tab, "Sessions")

        keys_tab = QWidget()
        kl = QVBoxLayout(keys_tab)

        kl.addWidget(QLabel("SSH Keys (~/.ssh):"))
        self._key_output = QPlainTextEdit()
        self._key_output.setReadOnly(True)
        kl.addWidget(self._key_output)

        key_btns = QHBoxLayout()
        gen_btn = vt.make_button("Generate New Key (ed25519)", "primary", parent=keys_tab)
        gen_btn.clicked.connect(self._gen_key)
        key_btns.addWidget(gen_btn)
        list_btn = vt.make_button("Refresh", "secondary", parent=keys_tab)
        list_btn.clicked.connect(self._list_keys)
        key_btns.addWidget(list_btn)
        key_btns.addStretch()
        kl.addLayout(key_btns)
        tabs.addTab(keys_tab, "Keys")

        self._status = QLabel("Ready — double-click a session to connect")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
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
            auth_item.setForeground(QBrush(QColor(
                vt.COLORS["accent_aqua"] if s.get("key") else vt.COLORS["text_muted"]
            )))
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
            user = vals["user"] or "vice"
            vals["user"] = user
            if not vals["name"]:
                vals["name"] = f"{user}@{vals['host']}"
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
            if not vals["host"]:
                QMessageBox.warning(self, "Missing Info", "Host is required.")
                return
            user = vals["user"] or "vice"
            vals["user"] = user
            if not vals["name"]:
                vals["name"] = f"{user}@{vals['host']}"
            idx = self._sessions.index(s)
            self._sessions[idx] = vals
            save_sessions(self._sessions)
            self._refresh()

    def _delete_session(self):
        s = self._selected_session()
        if not s:
            return
        if QMessageBox.question(
            self, "Delete", f"Delete session '{s.get('name')}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._sessions.remove(s)
        save_sessions(self._sessions)
        self._refresh()

    def _build_cmd(self, s):
        cmd = ["ssh", "-p", str(s.get("port", 22))]
        if s.get("key"):
            cmd += ["-i", s["key"]]
        if s.get("extra"):
            try:
                cmd += shlex.split(s["extra"])
            except ValueError:
                cmd += s["extra"].split()
        user = s.get("user") or "vice"
        cmd.append(f"{user}@{s['host']}")
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
        cmd = self._build_cmd(s)
        term = next(
            (t for t in ("x-terminal-emulator", "xfce4-terminal", "xterm") if shutil.which(t)),
            None,
        )
        if term:
            args = [term, "-e", shlex.join(cmd)] if term == "xfce4-terminal" else [term, "-e"] + cmd
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._status.setText(f"Opened terminal to {s['host']}")
        else:
            QMessageBox.information(
                self, "No Terminal",
                "No terminal emulator found.\nUse the built-in Connect instead.",
            )

    def _list_keys(self):
        if not os.path.isdir(SSH_DIR):
            self._key_output.setPlainText("~/.ssh does not exist")
            return
        lines = []
        for fname in sorted(os.listdir(SSH_DIR)):
            path = os.path.join(SSH_DIR, fname)
            ftype = "DIR " if os.path.isdir(path) else "KEY " if fname.endswith(".pub") else "PRIV"
            size = os.path.getsize(path) if os.path.isfile(path) else 0
            lines.append(f"[{ftype}] {fname}  ({size} bytes)")
        self._key_output.setPlainText("\n".join(lines) if lines else "No keys found")

    def _gen_key(self):
        reply = QMessageBox.question(
            self, "Generate Key",
            "Generate a new ed25519 key at ~/.ssh/id_ed25519?\n(Existing key will NOT be overwritten.)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        key_path = os.path.join(SSH_DIR, "id_ed25519")
        if os.path.exists(key_path):
            QMessageBox.warning(self, "Key Exists", f"{key_path} already exists. Not overwriting.")
            return
        try:
            os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
            r = subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-q"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                pub_text = ""
                try:
                    with open(key_path + ".pub", encoding="utf-8") as f:
                        pub_text = f.read()
                except OSError:
                    pass
                QMessageBox.information(
                    self, "Key Generated",
                    f"New key: {key_path}\nPublic key:\n{pub_text}",
                )
                log_info("SSH ed25519 key generated")
            else:
                QMessageBox.warning(self, "Failed", (r.stderr or "ssh-keygen failed")[:200])
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
