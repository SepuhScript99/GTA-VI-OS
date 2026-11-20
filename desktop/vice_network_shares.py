#!/usr/bin/env python3
"""Vice OS — Network Shares. Browse, mount/unmount Samba (SMB/CIFS) and NFS shares."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QInputDialog, QDialog, QFormLayout, QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""

MOUNT_BASE = "/mnt/shares"


def run_cmd(cmd):
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class AddShareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Network Share")
        self.setFixedSize(480, 340)
        self.setStyleSheet(STYLE)
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
        from PyQt5.QtWidgets import QDialogButtonBox, QPushButton
        ok = QPushButton("Add")
        ok.clicked.connect(self.accept)
        opts.addWidget(ok)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        opts.addWidget(cancel)
        layout.addRow(opts)

    def values(self):
        return {
            "type": self._type.currentText(),
            "host": self._host.text().strip(),
            "share": self._share.text().strip(),
            "mount": self._mount.text().strip() or f"{MOUNT_BASE}/{self._share.text().strip()}",
            "user": self._user.text().strip(),
            "pass": self._pass.text(),
        }


class NetworkShares(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Network Shares")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Network Shares (SMB/CIFS & NFS)")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Shares table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Share", "Host", "Type", "Mount Point", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        for i in [1, 2, 4]:
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table)

        # Buttons
        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Browse Network")
        browse_btn.clicked.connect(self._browse_network)
        btn_row.addWidget(browse_btn)

        add_btn = QPushButton("Add Share")
        add_btn.clicked.connect(self._add_share)
        btn_row.addWidget(add_btn)

        mount_btn = QPushButton("Mount Selected")
        mount_btn.clicked.connect(self._mount_selected)
        btn_row.addWidget(mount_btn)

        umount_btn = QPushButton("Unmount Selected")
        umount_btn.clicked.connect(self._unmount_selected)
        btn_row.addWidget(umount_btn)

        remove_btn = QPushButton("Remove Entry")
        remove_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        remove_btn.clicked.connect(self._remove_share)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        root.addLayout(btn_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _refresh(self):
        self._table.setRowCount(0)

        # Get currently mounted shares
        out, _ = run_cmd("mount | grep -E 'cifs|nfs|smb'")
        mounted = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                mp = parts[2]
                mounted[mp] = True

        # Show mount table entries
        from pathlib import Path
        for mp in Path(MOUNT_BASE).iterdir() if Path(MOUNT_BASE).exists() else []:
            if mp.is_dir():
                share_name = mp.name
                host = ""
                sh_type = "?"

                # Check fstab for info
                fstab_out, _ = run_cmd(f"grep '{mp}' /etc/fstab")
                if fstab_out:
                    parts = fstab_out.split()
                    if len(parts) >= 2:
                        src = parts[0]
                        if "//" in src:
                            host = src.split("//")[1].split("/")[0]
                            sh_type = "SMB"
                        elif ":" in src:
                            host = src.split(":")[0]
                            sh_type = "NFS"

                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(share_name))
                self._table.setItem(row, 1, QTableWidgetItem(host))
                self._table.setItem(row, 2, QTableWidgetItem(sh_type))
                self._table.setItem(row, 3, QTableWidgetItem(str(mp)))
                status_item = QTableWidgetItem("Mounted" if str(mp) in mounted else "Unmounted")
                status_item.setForeground(QBrush(QColor("#00ff88" if str(mp) in mounted else "#888")))
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
        out, _ = run_cmd("smbtree -NS 2>/dev/null || smbclient -L localhost 2>/dev/null | grep -v 'Disk\\|IPC'")
        if not out:
            out = "No shares found or smbclient not available."
        QMessageBox.information(self, "Network Browse", out[:2000])

    def _add_share(self):
        dlg = AddShareDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["host"] or not v["share"]:
            QMessageBox.warning(self, "Missing Info", "Host and share name are required.")
            return

        # Create mount point
        mp = v["mount"]
        os.makedirs(mp, exist_ok=True)

        # Build mount command
        if v["type"] == "SMB":
            cmd = (f"sudo mount -t cifs //{v['host']}/{v['share']} {mp} "
                    f"-o username={v['user']},password={v['pass']},uid=1000,gid=1000")
        else:
            cmd = f"sudo mount -t nfs {v['host']}:{v['share']} {mp}"

        out, ok = run_cmd(cmd)
        if ok:
            self._status.setText(f"Mounted {v['share']} at {mp}")
            log_info(f"Network share mounted: {mp}")
            self._refresh()
        else:
            self._status.setText(f"Mount failed: {out[:80]}")
            log_error(f"Share mount failed: {out}")
            QMessageBox.warning(self, "Mount Failed", f"Command:\n{cmd}\n\nError:\n{out}")

    def _mount_selected(self):
        mp = self._selected_mount()
        if not mp:
            QMessageBox.warning(self, "No Selection", "Select a share first.")
            return
        out, ok = run_cmd(f"sudo mount {mp}")
        if ok:
            self._status.setText(f"Mounted: {mp}")
            self._refresh()
        else:
            self._status.setText(f"Mount failed: {out[:80]}")
            log_error(f"Mount failed {mp}: {out}")

    def _unmount_selected(self):
        mp = self._selected_mount()
        if not mp:
            QMessageBox.warning(self, "No Selection", "Select a share first.")
            return
        out, ok = run_cmd(f"sudo umount {mp}")
        if ok:
            self._status.setText(f"Unmounted: {mp}")
            log_info(f"Network share unmounted: {mp}")
            self._refresh()
        else:
            self._status.setText(f"Unmount failed: {out[:80]}")
            log_error(f"Unmount failed {mp}: {out}")

    def _remove_share(self):
        mp = self._selected_mount()
        if not mp:
            QMessageBox.warning(self, "No Selection", "Select a share first.")
            return
        if QMessageBox.question(
            self, "Remove",
            f"Remove mount point {mp}?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        run_cmd(f"sudo umount {mp}")
        import shutil
        try:
            shutil.rmtree(mp)
        except Exception:
            pass
        self._status.setText(f"Removed: {mp}")
        self._refresh()


def main():
    app = QApplication(sys.argv)
    win = NetworkShares()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()