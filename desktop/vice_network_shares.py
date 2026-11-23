#!/usr/bin/env python3
"""Vice OS — Network Shares. Browse, mount/unmount Samba (SMB/CIFS) and NFS shares."""

import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 580

MOUNT_BASE = "/mnt/shares"


def run_cmd(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        err = (r.stderr or "").strip()
        out = (r.stdout or "").strip()
        return out or err, r.returncode == 0
    except Exception as e:
        return str(e), False


def _priv_cmd(cmd):
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    return list(cmd) if is_root else ["pkexec"] + list(cmd)


def _sanitize_mount_name(share_text):
    leaf = os.path.basename(share_text.strip().rstrip("/")) or "share"
    return re.sub(r"[^A-Za-z0-9._-]", "_", leaf)


def _read_fstab_entries():
    entries = {}
    try:
        with open("/etc/fstab", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    entries[parts[1]] = parts[0]
    except OSError:
        pass
    return entries


class AddShareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Network Share")
        self.setMinimumSize(480, 340)
        vt.apply_app_theme(self)
        layout = QFormLayout(self)
        self._type = QComboBox()
        self._type.addItems(["SMB/CIFS", "NFS"])
        layout.addRow("Share Type:", self._type)

        self._host = QLineEdit()
        self._host.setPlaceholderText("e.g. 192.168.1.100 or server.local")
        layout.addRow("Host/IP:", self._host)

        self._share = QLineEdit()
        self._share.setPlaceholderText("e.g. shared or /nfs/share")
        layout.addRow("Share Name/Path:", self._share)

        self._mount = QLineEdit()
        self._mount.setPlaceholderText("/mnt/shares/myshare")
        layout.addRow("Mount Point:", self._mount)

        self._user = QLineEdit()
        self._user.setPlaceholderText("username (for SMB)")
        layout.addRow("Username:", self._user)

        self._pass = QLineEdit()
        self._pass.setEchoMode(QLineEdit.Password)
        self._pass.setPlaceholderText("password (for SMB)")
        layout.addRow("Password:", self._pass)

        opts = QHBoxLayout()
        opts.addStretch()
        ok = vt.make_button("Add", "primary", parent=self)
        ok.clicked.connect(self.accept)
        opts.addWidget(ok)
        cancel = vt.make_button("Cancel", "secondary", parent=self)
        cancel.clicked.connect(self.reject)
        opts.addWidget(cancel)
        layout.addRow(opts)

    def values(self):
        share = self._share.text().strip()
        default_mp = os.path.join(MOUNT_BASE, _sanitize_mount_name(share))
        return {
            "type": self._type.currentText(),
            "host": self._host.text().strip(),
            "share": share,
            "mount": self._mount.text().strip() or default_mp,
            "user": self._user.text().strip(),
            "pass": self._pass.text(),
        }


class NetworkShares(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Network Shares")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 480)
        vt.apply_app_theme(self)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Network Shares",
            "Browse, mount and unmount SMB/CIFS and NFS network shares",
            icon_name="network-workgroup",
            badge_text="SHARES",
            badge_variant="aqua",
            parent=self,
        ))

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Share", "Host", "Type", "Mount Point", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        for i in (1, 2, 4):
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table)

        btn_row = QHBoxLayout()
        browse_btn = vt.make_button("Browse Network", "secondary", parent=self)
        browse_btn.clicked.connect(self._browse_network)
        btn_row.addWidget(browse_btn)

        add_btn = vt.make_button("Add Share", "primary", parent=self)
        add_btn.clicked.connect(self._add_share)
        btn_row.addWidget(add_btn)

        mount_btn = vt.make_button("Mount Selected", "secondary", parent=self)
        mount_btn.clicked.connect(self._mount_selected)
        btn_row.addWidget(mount_btn)

        umount_btn = vt.make_button("Unmount Selected", "secondary", parent=self)
        umount_btn.clicked.connect(self._unmount_selected)
        btn_row.addWidget(umount_btn)

        remove_btn = vt.make_button("Remove Entry", "danger", parent=self)
        remove_btn.clicked.connect(self._remove_share)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        refresh_btn = vt.make_button("Refresh", "secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._table.setRowCount(0)

        out, _ = run_cmd(["mount"])
        mounted = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[4] in ("cifs", "nfs", "nfs4", "smb3", "smbfs"):
                mounted[parts[2]] = (parts[0], parts[4].upper())

        fstab = _read_fstab_entries()
        paths = []
        if os.path.isdir(MOUNT_BASE):
            try:
                paths = sorted(
                    os.path.join(MOUNT_BASE, name)
                    for name in os.listdir(MOUNT_BASE)
                    if os.path.isdir(os.path.join(MOUNT_BASE, name))
                )
            except OSError:
                paths = []
        for mp in sorted(set(paths) | set(mounted.keys())):
            if not mp.startswith(MOUNT_BASE) and mp not in mounted:
                continue
            share_name = os.path.basename(mp.rstrip("/")) or mp
            host = ""
            sh_type = "?"
            src = mounted.get(mp, ("", ""))[0] or fstab.get(mp, "")
            if src:
                if "//" in src:
                    host = src.split("//", 1)[1].split("/", 1)[0]
                    sh_type = "SMB"
                elif ":" in src:
                    host = src.split(":", 1)[0]
                    sh_type = "NFS"

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(share_name))
            self._table.setItem(row, 1, QTableWidgetItem(host))
            self._table.setItem(row, 2, QTableWidgetItem(sh_type))
            self._table.setItem(row, 3, QTableWidgetItem(mp))
            is_mounted = mp in mounted
            status_item = QTableWidgetItem("Mounted" if is_mounted else "Unmounted")
            status_item.setForeground(QBrush(QColor(
                vt.COLORS["success"] if is_mounted else vt.COLORS["text_muted"]
            )))
            self._table.setItem(row, 4, status_item)

        self._status.setText(f"{self._table.rowCount()} share(s)")

    def _selected_mount(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 3)
        return item.text() if item else None

    def _browse_network(self):
        self._status.setText("Scanning network for SMB shares...")
        out = ""
        if shutil.which("smbtree"):
            out, ok = run_cmd(["smbtree", "-NS"], timeout=10)
            if not ok:
                out = ""
        if not out and shutil.which("smbclient"):
            raw, ok = run_cmd(["smbclient", "-L", "localhost", "-N"], timeout=10)
            if ok and raw:
                out = "\n".join(
                    line for line in raw.splitlines()
                    if "Disk" not in line and "IPC" not in line
                )
        if not out:
            out = "No shares found or smbclient/smbtree not available."
        QMessageBox.information(self, "Network Browse", out[:2000])
        self._status.setText("Ready")

    def _ensure_mountpoint(self, mp):
        try:
            os.makedirs(mp, exist_ok=True)
            return True, ""
        except PermissionError:
            out, ok = run_cmd(_priv_cmd(["mkdir", "-p", mp]))
            return ok, out
        except OSError as e:
            return False, str(e)

    def _add_share(self):
        dlg = AddShareDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["host"] or not v["share"]:
            QMessageBox.warning(self, "Missing Info", "Host and share name are required.")
            return

        mp = v["mount"]
        ok_dir, err_dir = self._ensure_mountpoint(mp)
        if not ok_dir:
            QMessageBox.warning(self, "Directory Error", f"Could not create {mp}:\n{err_dir}")
            return

        if v["type"].startswith("SMB"):
            share_path = v["share"].lstrip("/")
            uid = str(os.getuid()) if hasattr(os, "getuid") else "1000"
            gid = str(os.getgid()) if hasattr(os, "getgid") else "1000"
            if v["user"]:
                opts = f"username={v['user']},password={v['pass']},uid={uid},gid={gid}"
            else:
                opts = f"guest,uid={uid},gid={gid}"
            cmd = _priv_cmd([
                "mount", "-t", "cifs", f"//{v['host']}/{share_path}", mp, "-o", opts
            ])
            display_cmd = f"mount -t cifs //{v['host']}/{share_path} {mp} -o ..."
        else:
            nfs_path = v["share"] if v["share"].startswith("/") else f"/{v['share']}"
            cmd = _priv_cmd(["mount", "-t", "nfs", f"{v['host']}:{nfs_path}", mp])
            display_cmd = " ".join(cmd)

        out, ok = run_cmd(cmd)
        if ok:
            self._status.setText(f"Mounted {v['share']} at {mp}")
            log_info(f"Network share mounted: {mp}")
            self._refresh()
        else:
            self._status.setText(f"Mount failed: {out[:80]}")
            log_error(f"Share mount failed: {out}")
            QMessageBox.warning(self, "Mount Failed", f"Command:\n{display_cmd}\n\nError:\n{out}")

    def _mount_selected(self):
        mp = self._selected_mount()
        if not mp:
            QMessageBox.warning(self, "No Selection", "Select a share first.")
            return
        out, ok = run_cmd(_priv_cmd(["mount", mp]))
        if ok:
            self._status.setText(f"Mounted: {mp}")
            self._refresh()
        else:
            self._status.setText(f"Mount failed: {out[:80]}")
            log_error(f"Mount failed {mp}: {out}")
            QMessageBox.warning(self, "Mount Failed", out or f"Failed to mount {mp}")

    def _unmount_selected(self):
        mp = self._selected_mount()
        if not mp:
            QMessageBox.warning(self, "No Selection", "Select a share first.")
            return
        out, ok = run_cmd(_priv_cmd(["umount", mp]))
        if ok:
            self._status.setText(f"Unmounted: {mp}")
            log_info(f"Network share unmounted: {mp}")
            self._refresh()
        else:
            self._status.setText(f"Unmount failed: {out[:80]}")
            log_error(f"Unmount failed {mp}: {out}")
            QMessageBox.warning(self, "Unmount Failed", out or f"Failed to unmount {mp}")

    def _remove_share(self):
        mp = self._selected_mount()
        if not mp:
            QMessageBox.warning(self, "No Selection", "Select a share first.")
            return
        if QMessageBox.question(
            self, "Remove",
            f"Unmount and remove empty mount point {mp}?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        mount_out, _ = run_cmd(["mountpoint", "-q", mp])
        _ = mount_out
        is_mp = subprocess.run(["mountpoint", "-q", mp], capture_output=True).returncode == 0
        if is_mp:
            out, ok = run_cmd(_priv_cmd(["umount", mp]))
            if not ok:
                QMessageBox.warning(self, "Unmount Failed", f"Cannot remove {mp} while mounted:\n{out}")
                return
        try:
            os.rmdir(mp)
        except PermissionError:
            run_cmd(_priv_cmd(["rmdir", mp]))
        except OSError as e:
            QMessageBox.warning(self, "Remove Failed", f"Could not remove directory {mp}:\n{e}")
            return
        self._status.setText(f"Removed: {mp}")
        self._refresh()


def main():
    app = QApplication(sys.argv)
    win = NetworkShares()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
