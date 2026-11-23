#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) User & Group Manager.
User account creation, password resets, sudo privilege management, and group membership.
"""

import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QComboBox, QGroupBox, QAbstractItemView, QCheckBox, QDialog,
    QDialogButtonBox, QFormLayout, QSplitter, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
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

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 660
_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def run_cmd(cmd, sudo=False, input_data=None):
    full = list(cmd)
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if sudo and not is_root and shutil.which("pkexec"):
        full = ["pkexec"] + full
    try:
        r = subprocess.run(
            full, input=input_data, capture_output=True, text=True, timeout=15
        )
        return (r.stdout or "").strip() or (r.stderr or "").strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_users():
    users = []
    try:
        with open("/etc/passwd", encoding="utf-8", errors="replace") as f:
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
        with open("/etc/group", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 1 and parts[0]:
                    groups.append(parts[0])
    except Exception:
        pass
    return sorted(groups)


class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add User")
        self.setFixedSize(420, 300)
        apply_app_theme(self)

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
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        for entry in self.cmds:
            if self._stopped:
                return
            if len(entry) == 3:
                cmd, sudo, stdin_data = entry
            else:
                cmd, sudo = entry
                stdin_data = None
            out, ok = run_cmd(cmd, sudo=sudo, input_data=stdin_data)
            if not ok:
                if not self._stopped:
                    self.done.emit(False, out)
                return
        if not self._stopped:
            self.done.emit(True, "Done")


class UserManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — User Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 500)
        apply_app_theme(self)
        self._users = []
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="User & Group Manager",
            subtitle="Manage local user accounts, passwords, sudo access, and group membership",
            icon_name="system-users",
            badge_text="USERS",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

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
        self._table.currentCellChanged.connect(lambda row, _c, _pr, _pc: self._on_user_selected(row))
        ll.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = make_button("Add User", variant="primary", parent=self)
        add_btn.clicked.connect(self._add_user)
        btn_row.addWidget(add_btn)

        self._del_btn = make_button("Delete User", variant="danger", parent=self)
        self._del_btn.clicked.connect(self._delete_user)
        btn_row.addWidget(self._del_btn)

        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self._detail_box = QGroupBox("User Details")
        dl = QVBoxLayout(self._detail_box)

        self._detail_label = QLabel("Select a user to view details.")
        self._detail_label.setObjectName("MutedLabel")
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
        add_grp_btn = make_button("Add to Group", variant="secondary", parent=self)
        add_grp_btn.clicked.connect(self._add_to_group)
        grp_btns.addWidget(add_grp_btn)
        rm_grp_btn = make_button("Remove", variant="danger", parent=self)
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
        passwd_btn = make_button("Set Password", variant="primary", parent=self)
        passwd_btn.clicked.connect(self._set_password)
        pl.addWidget(passwd_btn)
        dl.addWidget(passwd_box)

        rl.addWidget(self._detail_box)
        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([500, 440])

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
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
            sudo_item.setForeground(QBrush(QColor(COLORS["success"] if u["sudo"] else COLORS["text_muted"])))
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
        uname = vals["username"]
        if not uname or not _USERNAME_RE.match(uname):
            QMessageBox.warning(self, "Invalid Username", "Enter a valid lowercase UNIX username.")
            return

        cmds = [
            (["useradd", "-m", "-s", vals["shell"], "-c", vals["fullname"], uname], True, None),
        ]
        if vals["password"]:
            cmds.append((["chpasswd"], True, f"{uname}:{vals['password']}\n"))
        if vals["sudo"]:
            cmds.append((["usermod", "-aG", "sudo", uname], True, None))

        self._run_cmds(cmds, f"Adding user: {uname}")

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
            [(["userdel", "-r", u["username"]], True, None)],
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
        self._run_cmds([(cmd, True, None)], msg)

    def _add_to_group(self):
        u = self._selected_user()
        if not u:
            return
        grp = self._grp_combo.currentText()
        if not grp:
            return
        self._run_cmds(
            [(["usermod", "-aG", grp, u["username"]], True, None)],
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
            [(["gpasswd", "-d", u["username"], grp], True, None)],
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
            [(["chpasswd"], True, f"{u['username']}:{pw}\n")],
            f"Setting password for {u['username']}"
        )
        self._passwd_edit.clear()

    def _run_cmds(self, cmds, msg):
        if self._worker is not None and self._worker.isRunning():
            self._status.setText("Another user operation is already running...")
            return
        self._status.setText(msg)
        w = CmdWorker(cmds)
        w.done.connect(self._cmd_done)
        w.start()
        self._worker = w

    def _cmd_done(self, ok, out):
        if ok:
            self._status.setText("Done")
            log_info("User operation succeeded")
        else:
            self._status.setText(f"Error: {out[:80]}")
            log_error(f"User operation failed: {out}")
            QMessageBox.warning(self, "Error", out)
        self._refresh()

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = UserManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
