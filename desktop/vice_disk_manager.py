#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Disk Manager.
Partition viewer, filesystem mount/unmount utility, and storage device health monitor.
"""

import json
import os
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QGroupBox, QAbstractItemView, QProgressBar, QTabWidget
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

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 680


def run_cmd(cmd, sudo=False):
    full = list(cmd)
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if sudo and not is_root and shutil.which("pkexec"):
        full = ["pkexec"] + full
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=15)
        return (r.stdout or "").strip() or (r.stderr or "").strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, sudo=False):
        super().__init__()
        self.cmd = cmd
        self.sudo = sudo
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        out, ok = run_cmd(self.cmd, self.sudo)
        if not self._stopped:
            self.done.emit(ok, out)


def _flatten_lsblk(nodes, out_list):
    for node in nodes:
        out_list.append(node)
        children = node.get("children") or []
        if children:
            _flatten_lsblk(children, out_list)


class DiskManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Disk Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        apply_app_theme(self)
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Disk & Partition Manager",
            subtitle="Inspect block devices, UUIDs, mount points, and filesystem space usage",
            icon_name="drive-harddisk",
            badge_text="STORAGE",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        part_tab = QWidget()
        pl = QVBoxLayout(part_tab)

        self._part_table = QTableWidget()
        self._part_table.setColumnCount(7)
        self._part_table.setHorizontalHeaderLabels(["Device", "Size", "Type", "FS Type", "Label", "Mountpoint", "UUID"])
        self._part_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._part_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._part_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._part_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._part_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._part_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self._part_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._part_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._part_table.setEditTriggers(QTableWidget.NoEditTriggers)
        pl.addWidget(self._part_table)

        mount_box = QGroupBox("Mount / Unmount")
        ml = QHBoxLayout(mount_box)
        ml.addWidget(QLabel("Mount point:"))
        self._mount_edit = QLineEdit()
        self._mount_edit.setPlaceholderText("/mnt/mydisk")
        ml.addWidget(self._mount_edit)
        mount_btn = make_button("Mount Selected", variant="primary", parent=self)
        mount_btn.clicked.connect(self._mount_selected)
        ml.addWidget(mount_btn)
        umount_btn = make_button("Unmount Selected", variant="danger", parent=self)
        umount_btn.clicked.connect(self._umount_selected)
        ml.addWidget(umount_btn)
        pl.addWidget(mount_box)
        tabs.addTab(part_tab, "Partitions")

        usage_tab = QWidget()
        ul = QVBoxLayout(usage_tab)

        self._usage_table = QTableWidget()
        self._usage_table.setColumnCount(6)
        self._usage_table.setHorizontalHeaderLabels(["Device", "Size", "Used", "Avail", "Use%", "Mounted on"])
        self._usage_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for i in range(5):
            self._usage_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._usage_table.setEditTriggers(QTableWidget.NoEditTriggers)
        ul.addWidget(self._usage_table)

        ul.addWidget(QLabel("Disk usage bars:"))
        self._bars_widget = QWidget()
        self._bars_layout = QVBoxLayout(self._bars_widget)
        ul.addWidget(self._bars_widget)
        tabs.addTab(usage_tab, "Disk Usage")

        btn_row = QHBoxLayout()
        refresh_btn = make_button("Refresh", variant="secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _refresh(self):
        self._load_partitions()
        self._load_usage()

    def _load_partitions(self):
        self._part_table.setRowCount(0)
        out, ok = run_cmd(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID"])
        if not ok or not out:
            self._status.setText("lsblk not available")
            return
        try:
            data = json.loads(out)
        except Exception:
            self._status.setText("Failed to parse lsblk output")
            return
        nodes = []
        _flatten_lsblk(data.get("blockdevices", []), nodes)
        for dev in nodes:
            row = self._part_table.rowCount()
            self._part_table.insertRow(row)
            name = str(dev.get("name") or "")
            size = str(dev.get("size") or "")
            btype = str(dev.get("type") or "")
            fstype = str(dev.get("fstype") or "")
            label = str(dev.get("label") or "")
            mountpoint = str(dev.get("mountpoint") or "")
            uuid = str(dev.get("uuid") or "")
            for col, val in enumerate((name, size, btype, fstype, label, mountpoint, uuid)):
                item = QTableWidgetItem(val)
                if btype == "disk":
                    item.setForeground(QBrush(QColor(COLORS["accent_peach"])))
                elif mountpoint:
                    item.setForeground(QBrush(QColor(COLORS["success"])))
                self._part_table.setItem(row, col, item)
        self._status.setText(f"{self._part_table.rowCount()} block devices found")

    def _load_usage(self):
        self._usage_table.setRowCount(0)
        while self._bars_layout.count():
            item = self._bars_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        out, _ = run_cmd(["df", "-h", "--output=source,size,used,avail,pcent,target"])
        if not out:
            return

        for line in out.splitlines()[1:]:
            parts = line.split(None, 5)
            if len(parts) < 6:
                continue
            source, size, used, avail, pct, target = parts
            if any(x in source for x in ("tmpfs", "udev", "loop")):
                continue

            row = self._usage_table.rowCount()
            self._usage_table.insertRow(row)
            for col, val in enumerate((source, size, used, avail, pct, target)):
                item = QTableWidgetItem(val)
                try:
                    pct_val = int(pct.replace("%", ""))
                    if col == 4:
                        col_hex = COLORS["danger"] if pct_val > 90 else COLORS["warning"] if pct_val > 70 else COLORS["success"]
                        item.setForeground(QBrush(QColor(col_hex)))
                except Exception:
                    pass
                self._usage_table.setItem(row, col, item)

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel(f"{target} ({source})")
            lbl.setFixedWidth(240)
            lbl.setObjectName("MutedLabel")
            row_layout.addWidget(lbl)
            bar = QProgressBar()
            try:
                bar.setValue(int(pct.replace("%", "")))
            except Exception:
                bar.setValue(0)
            bar.setFormat(f"{used} / {size}  ({pct})")
            row_layout.addWidget(bar)
            self._bars_layout.addWidget(row_widget)

    def _selected_device(self):
        row = self._part_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a partition first.")
            return None
        item = self._part_table.item(row, 0)
        return f"/dev/{item.text().strip()}" if item else None

    def _mount_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        mp = self._mount_edit.text().strip()
        if not mp or not os.path.isabs(mp):
            QMessageBox.warning(self, "Invalid Mount Point", "Enter an absolute mount point path (e.g. /mnt/mydisk).")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        w = CmdWorker(["bash", "-c", 'mkdir -p "$1" && mount "$2" "$1"', "vice-mount", mp, dev], sudo=True)
        w.done.connect(lambda ok, out: self._cmd_done(ok, out, f"Mount {dev} -> {mp}"))
        w.start()
        self._worker = w

    def _umount_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        if QMessageBox.question(
            self, "Unmount", f"Unmount {dev}?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        w = CmdWorker(["umount", dev], sudo=True)
        w.done.connect(lambda ok, out: self._cmd_done(ok, out, f"Unmount {dev}"))
        w.start()
        self._worker = w

    def _cmd_done(self, ok, out, op):
        if ok:
            self._status.setText(f"{op}: OK")
            log_info(f"Disk op: {op}")
        else:
            self._status.setText(f"{op}: FAILED")
            log_error(f"Disk op failed: {out}")
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
    win = DiskManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
