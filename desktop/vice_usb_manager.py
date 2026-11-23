#!/usr/bin/env python3
"""Vice OS — USB Auto-Mount GUI. View, mount, unmount USB drives."""

import json
import os
import subprocess
import sys

from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 860
WINDOW_HEIGHT = 520

CONFIG_PATH = os.path.expanduser("~/.config/vice-os/usb_automount.json")


def _find_daemon_script():
    base = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(base, "system_utils", "vice_usb_automount.py"),
        os.path.join(os.path.dirname(base), "system_utils", "vice_usb_automount.py"),
        "/opt/vice-os/system_utils/vice_usb_automount.py",
        "/usr/local/system_utils/vice_usb_automount.py",
    ):
        if os.path.exists(candidate):
            return candidate
    return "/opt/vice-os/system_utils/vice_usb_automount.py"


DAEMON_SCRIPT = _find_daemon_script()


class UsbWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self.cmd = list(cmd)
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = self._proc.communicate(timeout=15)
            if not self._cancelled:
                out = (stdout or "").strip() or (stderr or "").strip()
                self.done.emit(self._proc.returncode == 0, out)
        except Exception as e:
            if not self._cancelled:
                self.done.emit(False, str(e))


def _collect_usb_partitions(devices, parent_tran=""):
    found = []
    for dev in devices or []:
        tran = dev.get("tran") or parent_tran
        children = dev.get("children") or []
        if children:
            found.extend(_collect_usb_partitions(children, tran))
        elif tran == "usb" and (dev.get("type") == "part" or dev.get("fstype")):
            found.append(dev)
    return found


class USBManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — USB Auto-Mount Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(720, 440)
        vt.apply_app_theme(self)
        self._worker = None
        self._init_ui()
        self._load_config()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "USB Auto-Mount Manager",
            "View, mount, unmount and safely eject removable USB storage",
            icon_name="drive-removable-media",
            badge_text="USB",
            badge_variant="peach",
            parent=self,
        ))

        status_box = QGroupBox("Daemon Status")
        sl = QHBoxLayout(status_box)
        self._daemon_status = QLabel("Checking...")
        sl.addWidget(self._daemon_status)
        sl.addStretch()
        self._start_btn = vt.make_button("Start Daemon", "primary", parent=status_box)
        self._start_btn.clicked.connect(self._start_daemon)
        sl.addWidget(self._start_btn)
        self._stop_btn = vt.make_button("Stop Daemon", "danger", parent=status_box)
        self._stop_btn.clicked.connect(self._stop_daemon)
        sl.addWidget(self._stop_btn)
        root.addWidget(status_box)

        cfg_box = QGroupBox("Auto-Mount Settings")
        cl = QVBoxLayout(cfg_box)

        self._auto_mount_cb = QCheckBox("Auto-mount USB drives on connect")
        self._auto_mount_cb.toggled.connect(self._save_config)
        cl.addWidget(self._auto_mount_cb)

        self._notify_cb = QCheckBox("Show desktop notifications")
        self._notify_cb.toggled.connect(self._save_config)
        cl.addWidget(self._notify_cb)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Poll interval (sec):"))
        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(1, 60)
        self._poll_spin.setValue(3)
        self._poll_spin.valueChanged.connect(self._save_config)
        opts_row.addWidget(self._poll_spin)
        opts_row.addStretch()
        cl.addLayout(opts_row)
        root.addWidget(cfg_box)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Device", "FS Type", "Size", "Mount Point", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table)

        act_row = QHBoxLayout()
        self._mount_btn = vt.make_button("Mount Selected", "primary", parent=self)
        self._mount_btn.clicked.connect(self._mount_selected)
        act_row.addWidget(self._mount_btn)

        self._unmount_btn = vt.make_button("Unmount Selected", "secondary", parent=self)
        self._unmount_btn.clicked.connect(self._unmount_selected)
        act_row.addWidget(self._unmount_btn)

        self._eject_btn = vt.make_button("Eject", "danger", parent=self)
        self._eject_btn.clicked.connect(self._eject_selected)
        act_row.addWidget(self._eject_btn)

        act_row.addStretch()
        refresh_btn = vt.make_button("Refresh", "secondary", parent=self)
        refresh_btn.clicked.connect(self._refresh)
        act_row.addWidget(refresh_btn)
        root.addLayout(act_row)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            self._auto_mount_cb.setChecked(bool(cfg.get("auto_mount", False)))
            self._notify_cb.setChecked(bool(cfg.get("notify", True)))
            self._poll_spin.setValue(int(cfg.get("poll_interval", 3)))
        except Exception:
            pass

    def _refresh(self):
        self._update_daemon_status()
        self._load_devices()

    def _update_daemon_status(self):
        pid_file = "/tmp/vice_usb_automount.pid"
        running = False
        if os.path.exists(pid_file):
            try:
                with open(pid_file, encoding="utf-8") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                running = os.path.isdir(f"/proc/{pid}")
            except Exception:
                running = False

        if running:
            self._daemon_status.setText("Daemon: RUNNING")
            self._daemon_status.setStyleSheet(f"color: {vt.COLORS['success']}; font-weight: bold;")
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
        else:
            self._daemon_status.setText("Daemon: STOPPED")
            self._daemon_status.setStyleSheet(f"color: {vt.COLORS['danger']}; font-weight: bold;")
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)

    def _load_devices(self):
        self._table.setRowCount(0)
        try:
            r = subprocess.run(
                ["lsblk", "-o", "NAME,TYPE,FSTYPE,SIZE,TRAN,MOUNTPOINT", "-J"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0 or not r.stdout:
                return
            data = json.loads(r.stdout)
            for dev in _collect_usb_partitions(data.get("blockdevices", [])):
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(dev.get("name", "") or ""))
                self._table.setItem(row, 1, QTableWidgetItem(dev.get("fstype", "") or ""))
                self._table.setItem(row, 2, QTableWidgetItem(dev.get("size", "") or ""))
                mp = dev.get("mountpoint") or ""
                self._table.setItem(row, 3, QTableWidgetItem(mp))
                status = "Mounted" if mp else "Unmounted"
                item = QTableWidgetItem(status)
                item.setForeground(QBrush(QColor(
                    vt.COLORS["success"] if mp else vt.COLORS["danger"]
                )))
                self._table.setItem(row, 4, item)
        except Exception as e:
            log_error(f"USB list failed: {e}")

    def _start_daemon(self):
        if not os.path.exists(DAEMON_SCRIPT):
            QMessageBox.warning(self, "Missing Daemon", f"Not found:\n{DAEMON_SCRIPT}")
            return
        try:
            subprocess.Popen(
                [sys.executable, DAEMON_SCRIPT],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._status.setText("Daemon start requested")
            QTimer.singleShot(500, self._update_daemon_status)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _stop_daemon(self):
        if not os.path.exists(DAEMON_SCRIPT):
            return
        self._run_cmd([sys.executable, DAEMON_SCRIPT, "stop"], "Stopping daemon...")

    def _selected_device(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a device first.")
            return None, None
        dev_item = self._table.item(row, 0)
        mp_item = self._table.item(row, 3)
        return (dev_item.text() if dev_item else None), (mp_item.text() if mp_item else "")

    def _mount_selected(self):
        dev, _ = self._selected_device()
        if not dev:
            return
        self._run_cmd(["udisksctl", "mount", "-b", f"/dev/{dev}"], f"Mounting {dev}...")

    def _unmount_selected(self):
        dev, mp = self._selected_device()
        if not dev:
            return
        if not mp:
            QMessageBox.information(self, "Not Mounted", "Device is not mounted.")
            return
        self._run_cmd(["udisksctl", "unmount", "-b", f"/dev/{dev}"], f"Unmounting {dev}...")

    def _eject_selected(self):
        dev, mp = self._selected_device()
        if not dev:
            return
        if mp:
            QMessageBox.information(self, "Still Mounted", "Unmount the device before ejecting.")
            return
        self._run_cmd(["udisksctl", "power-off", "-b", f"/dev/{dev}"], f"Ejecting {dev}...")

    def _save_config(self):
        cfg = {
            "auto_mount": self._auto_mount_cb.isChecked(),
            "notify": self._notify_cb.isChecked(),
            "poll_interval": self._poll_spin.value(),
        }
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            log_info("USB auto-mount config updated")
        except OSError as e:
            log_error(f"USB config save failed: {e}")

    def _run_cmd(self, cmd, msg):
        if self._worker is not None and self._worker.isRunning():
            return
        self._status.setText(msg)
        self._mount_btn.setEnabled(False)
        self._unmount_btn.setEnabled(False)
        self._eject_btn.setEnabled(False)
        w = UsbWorker(cmd, parent=self)
        w.done.connect(self._cmd_done)
        self._worker = w
        w.start()

    def _cmd_done(self, ok, out):
        self._mount_btn.setEnabled(True)
        self._unmount_btn.setEnabled(True)
        self._eject_btn.setEnabled(True)
        if ok:
            self._status.setText("Done")
            self._refresh()
        else:
            self._status.setText(f"Failed: {out[:80]}")
            QMessageBox.warning(self, "Error", out or "Operation failed.")

    def closeEvent(self, event):
        self._timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = USBManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
