#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) User & Group Manager
User account creation, password resets, sudo privilege management, and group membership.
"""

import sys
import os
import subprocess
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QComboBox, QGroupBox, QAbstractItemView, QCheckBox, QDialog,
    QDialogButtonBox, QFormLayout, QSplitter, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 660

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 13px; height: 13px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QDialog { background-color: #0a0a0a; color: #00ffff; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
"""


def run_cmd(cmd, sudo=False):
    full = (["sudo"] if sudo else []) + cmd
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_users():
    users = []
    try:
        with open("/etc/passwd") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) < 7:
                    continue
                uid = int(parts[2])
                if uid >= 1000 and parts[6] not in ("/usr/sbin/nologin", "/bin/false", "/sbin/nologin"):
                    groups_out, _ = run_cmd(["id", "-Gn", parts[0]])
                    groups = groups_out.split()
                    users.append({
                        "username": parts[0],
                        "uid": uid,
                        "gid": parts[3],
                        "gecos": parts[4],
                        "home": parts[5],
                        "shell": parts[6],
                        "groups": groups,
                        "sudo": "sudo" in groups or "wheel" in groups,
                    })
    except Exception as e:
        log_error(f"get_users: {e}")
    return users


def get_all_groups():
    groups = []
    try:
        with open("/etc/group") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 1:
                    groups.append(parts[0])
    except Exception:
        pass
    return sorted(groups)


class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add User")
        self.setFixedSize(420, 300)
        self.setStyleSheet(STYLE)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._username = QLineEdit()
        self._username.setPlaceholderText("lowercase, no spaces")
        form.addRow("Username:", self._username)

        self._fullname = QLineEdit()
        self._fullname.setPlaceholderText("Full Name")
        form.addRow("Full Name:", self._fullname)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("Password")
        form.addRow("Password:", self._password)

        self._shell_combo = QComboBox()
        self._shell_combo.addItems(["/bin/bash", "/bin/zsh", "/bin/sh", "/usr/bin/fish"])
        form.addRow("Shell:", self._shell_combo)

        self._sudo_cb = QCheckBox("Add to sudo group")
        form.addRow("", self._sudo_cb)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet("QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px 12px; } QPushButton:hover { background: #00ffff; color: #0a0a0a; }")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self):
        return {
            "username": self._username.text().strip(),
            "fullname": self._fullname.text().strip(),
            "password": self._password.text(),
            "shell": self._shell_combo.currentText(),
            "sudo": self._sudo_cb.isChecked(),
        }


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmds):
        super().__init__()
        self.cmds = cmds

    def run(self):
        for cmd, sudo in self.cmds:
            out, ok = run_cmd(cmd, sudo)
            if not ok:
                self.done.emit(False, out)
                return
        self.done.emit(True, "Done")


class UserManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — User Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._users = []
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — User Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: user table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Username", "UID", "Full Name", "Shell", "Sudo"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_user_selected)
        ll.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add User")
        add_btn.clicked.connect(self._add_user)
        btn_row.addWidget(add_btn)

        self._del_btn = QPushButton("Delete User")
        self._del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        self._del_btn.clicked.connect(self._delete_user)
        btn_row.addWidget(self._del_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # Right: user detail / group editor
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self._detail_box = QGroupBox("User Details")
        dl = QVBoxLayout(self._detail_box)

        self._detail_label = QLabel("Select a user to view details.")
        self._detail_label.setStyleSheet("color: #888;")
        dl.addWidget(self._detail_label)

        self._sudo_cb = QCheckBox("Member of sudo group")
        self._sudo_cb.toggled.connect(self._toggle_sudo)
        dl.addWidget(self._sudo_cb)

        groups_box = QGroupBox("Groups")
        gl = QVBoxLayout(groups_box)
        self._groups_list = QListWidget()
        self._groups_list.setMaximumHeight(160)
        gl.addWidget(self._groups_list)

        grp_btns = QHBoxLayout()
        self._grp_combo = QComboBox()
        grp_btns.addWidget(self._grp_combo)
        add_grp_btn = QPushButton("Add to Group")
        add_grp_btn.clicked.connect(self._add_to_group)
        grp_btns.addWidget(add_grp_btn)
        rm_grp_btn = QPushButton("Remove")
        rm_grp_btn.clicked.connect(self._remove_from_group)
        grp_btns.addWidget(rm_grp_btn)
        gl.addLayout(grp_btns)
        dl.addWidget(groups_box)

        passwd_box = QGroupBox("Change Password")
        pl = QHBoxLayout(passwd_box)
        self._passwd_edit = QLineEdit()
        self._passwd_edit.setEchoMode(QLineEdit.Password)
        self._passwd_edit.setPlaceholderText("New password")
        pl.addWidget(self._passwd_edit)
        passwd_btn = QPushButton("Set Password")
        passwd_btn.clicked.connect(self._set_password)
        pl.addWidget(passwd_btn)
        dl.addWidget(passwd_box)

        rl.addWidget(self._detail_box)
        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([500, 440])

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

        all_groups = get_all_groups()
        self._grp_combo.addItems(all_groups)

    def _refresh(self):
        self._users = get_users()
        self._table.setRowCount(0)
        for u in self._users:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(u["username"]))
            self._table.setItem(row, 1, QTableWidgetItem(str(u["uid"])))
            self._table.setItem(row, 2, QTableWidgetItem(u["gecos"]))
            self._table.setItem(row, 3, QTableWidgetItem(u["shell"]))
            sudo_item = QTableWidgetItem("Yes" if u["sudo"] else "No")
            sudo_item.setForeground(QBrush(QColor("#00ff88" if u["sudo"] else "#888888")))
            self._table.setItem(row, 4, sudo_item)
        self._status.setText(f"{len(self._users)} user(s) found")

    def _selected_user(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._users):
            return None
        return self._users[row]

    def _on_user_selected(self, row):
        if row < 0 or row >= len(self._users):
            return
        u = self._users[row]
        self._detail_label.setText(
            f"Username: {u['username']}  |  UID: {u['uid']}\n"
            f"Home: {u['home']}  |  Shell: {u['shell']}"
        )
        self._sudo_cb.blockSignals(True)
        self._sudo_cb.setChecked(u["sudo"])
        self._sudo_cb.blockSignals(False)

        self._groups_list.clear()
        for g in sorted(u["groups"]):
            self._groups_list.addItem(QListWidgetItem(g))

    def _add_user(self):
        dlg = AddUserDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        vals = dlg.get_values()
        if not vals["username"]:
            QMessageBox.warning(self, "Missing Username", "Username is required.")
            return

        cmds = [
            (["useradd", "-m", "-s", vals["shell"],
              "-c", vals["fullname"], vals["username"]], True),
        ]
        if vals["password"]:
            cmds.append((["bash", "-c",
                f"echo '{vals['username']}:{vals['password']}' | chpasswd"], True))
        if vals["sudo"]:
            cmds.append((["usermod", "-aG", "sudo", vals["username"]], True))

        self._run_cmds(cmds, f"Adding user: {vals['username']}")

    def _delete_user(self):
        u = self._selected_user()
        if not u:
            QMessageBox.warning(self, "No Selection", "Select a user first.")
            return
        if QMessageBox.question(
            self, "Delete User",
            f"Delete user '{u['username']}' and their home directory?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run_cmds(
            [(["userdel", "-r", u["username"]], True)],
            f"Deleting user: {u['username']}"
        )

    def _toggle_sudo(self, enabled):
        u = self._selected_user()
        if not u:
            return
        if enabled:
            cmd = ["usermod", "-aG", "sudo", u["username"]]
            msg = f"Adding {u['username']} to sudo"
        else:
            cmd = ["gpasswd", "-d", u["username"], "sudo"]
            msg = f"Removing {u['username']} from sudo"
        self._run_cmds([(cmd, True)], msg)

    def _add_to_group(self):
        u = self._selected_user()
        if not u:
            return
        grp = self._grp_combo.currentText()
        if not grp:
            return
        self._run_cmds(
            [(["usermod", "-aG", grp, u["username"]], True)],
            f"Adding {u['username']} to {grp}"
        )

    def _remove_from_group(self):
        u = self._selected_user()
        if not u:
            return
        item = self._groups_list.currentItem()
        if not item:
            QMessageBox.warning(self, "No Group", "Select a group from the list.")
            return
        grp = item.text()
        self._run_cmds(
            [(["gpasswd", "-d", u["username"], grp], True)],
            f"Removing {u['username']} from {grp}"
        )

    def _set_password(self):
        u = self._selected_user()
        if not u:
            return
        pw = self._passwd_edit.text()
        if not pw:
            QMessageBox.warning(self, "Empty Password", "Enter a new password.")
            return
        self._run_cmds(
            [(["bash", "-c", f"echo '{u['username']}:{pw}' | chpasswd"], True)],
            f"Setting password for {u['username']}"
        )
        self._passwd_edit.clear()

    def _run_cmds(self, cmds, msg):
        self._status.setText(msg)
        w = CmdWorker(cmds)
        w.done.connect(self._cmd_done)
        w.start()
        self._worker = w

    def _cmd_done(self, ok, out):
        if ok:
            self._status.setText("Done")
            log_info(f"User operation succeeded")
        else:
            self._status.setText(f"Error: {out[:80]}")
            log_error(f"User operation failed: {out}")
            QMessageBox.warning(self, "Error", out)
        self._refresh()


def main():
    app = QApplication(sys.argv)
    win = UserManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
