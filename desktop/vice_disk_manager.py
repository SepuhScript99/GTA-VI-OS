#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Disk Manager
Partition viewer, filesystem mount/unmount utility, and storage device health monitor.
"""

import sys
import os
import subprocess
import re

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QGroupBox, QAbstractItemView, QSplitter, QProgressBar, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
QLabel { color: #00ffff; }
"""


def run_cmd(cmd, sudo=False):
    full = (["sudo"] if sudo else []) + cmd
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def get_partitions():
    out, _ = run_cmd(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID", "-J"])
    if not out:
        out, _ = run_cmd(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL"])
    return out


def get_disk_usage():
    out, _ = run_cmd(["df", "-h", "--output=source,size,used,avail,pcent,target"])
    return out


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, sudo=False):
        super().__init__()
        self.cmd = cmd
        self.sudo = sudo

    def run(self):
        out, ok = run_cmd(self.cmd, self.sudo)
        self.done.emit(ok, out)


class DiskManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Disk Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Disk Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Tab 1: Partitions ---
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
        mount_btn = QPushButton("Mount Selected")
        mount_btn.clicked.connect(self._mount_selected)
        ml.addWidget(mount_btn)
        umount_btn = QPushButton("Unmount Selected")
        umount_btn.clicked.connect(self._umount_selected)
        ml.addWidget(umount_btn)
        pl.addWidget(mount_box)
        tabs.addTab(part_tab, "Partitions")

        # --- Tab 2: Disk Usage ---
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

        # Bottom bar
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _refresh(self):
        self._load_partitions()
        self._load_usage()

    def _load_partitions(self):
        self._part_table.setRowCount(0)
        out, ok = run_cmd(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID", "--noheadings"])
        if not ok or not out:
            self._status.setText("lsblk not available")
            return
        for line in out.splitlines():
            parts = line.split(None, 6)
            while len(parts) < 7:
                parts.append("")
            name, size, btype, fstype, mountpoint, label, uuid = parts[:7]
            row = self._part_table.rowCount()
            self._part_table.insertRow(row)
            vals = [name.lstrip("├─└─│"), size, btype, fstype, label, mountpoint, uuid]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if btype == "disk":
                    item.setForeground(QBrush(QColor("#ff00ff")))
                elif mountpoint:
                    item.setForeground(QBrush(QColor("#00ff88")))
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

        lines = out.splitlines()
        for line in lines[1:]:
            parts = line.split(None, 5)
            if len(parts) < 6:
                continue
            source, size, used, avail, pct, target = parts
            if any(x in source for x in ["tmpfs", "udev", "loop"]):
                continue

            row = self._usage_table.rowCount()
            self._usage_table.insertRow(row)
            for col, val in enumerate([source, size, used, avail, pct, target]):
                item = QTableWidgetItem(val)
                try:
                    pct_val = int(pct.replace("%", ""))
                    if col == 4:
                        if pct_val > 90:
                            item.setForeground(QBrush(QColor("#ff4444")))
                        elif pct_val > 70:
                            item.setForeground(QBrush(QColor("#ffaa00")))
                        else:
                            item.setForeground(QBrush(QColor("#00ff88")))
                except Exception:
                    pass
                self._usage_table.setItem(row, col, item)

            # Usage bar
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel(f"{target} ({source})")
            lbl.setFixedWidth(240)
            lbl.setStyleSheet("color: #888; font-size: 10px;")
            row_layout.addWidget(lbl)
            bar = QProgressBar()
            try:
                bar.setValue(int(pct.replace("%", "")))
            except Exception:
                bar.setValue(0)
            bar.setFormat(f"{used} / {size}  ({pct})")
            bar.setStyleSheet(
                "QProgressBar { border: 1px solid #333; background: #1a1a1a; text-align: center; color: #fff; font-size: 10px; }"
                "QProgressBar::chunk { background: #00ffff; }"
            )
            row_layout.addWidget(bar)
            self._bars_layout.addWidget(row_widget)

    def _selected_device(self):
        row = self._part_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a partition first.")
            return None
        item = self._part_table.item(row, 0)
        return f"/dev/{item.text()}" if item else None

    def _mount_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        mp = self._mount_edit.text().strip()
        if not mp:
            QMessageBox.warning(self, "No Mount Point", "Enter a mount point path.")
            return
        os.makedirs(mp, exist_ok=True)
        w = CmdWorker(["mount", dev, mp], sudo=True)
        w.done.connect(lambda ok, out: self._cmd_done(ok, out, f"Mount {dev} -> {mp}"))
        w.start()
        self._worker = w

    def _umount_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        if QMessageBox.question(self, "Unmount", f"Unmount {dev}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
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


def main():
    app = QApplication(sys.argv)
    win = DiskManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
