#!/usr/bin/env python3
"""Vice OS — Backup Scheduler. Cron-based backup jobs with retention policies."""

from datetime import datetime
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QTextEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
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
WINDOW_HEIGHT = 640

BACKUP_DIR = os.path.expanduser("~/backups")
JOBS_FILE = os.path.expanduser("~/.config/vice-os/backup_jobs.json")
CRONTAB_MARKER = "# VICE BACKUP JOBS"


def run_cmd(cmd, sudo=False, input_data=None):
    try:
        full_cmd = cmd
        if not isinstance(cmd, str) and sudo and (os.geteuid() != 0 if hasattr(os, "geteuid") else True):
            pk = shutil.which("pkexec")
            if pk:
                full_cmd = [pk] + list(cmd)
        if isinstance(full_cmd, str):
            r = subprocess.run(
                full_cmd, shell=True, input=input_data,
                capture_output=True, text=True, timeout=120
            )
        else:
            r = subprocess.run(
                full_cmd, input=input_data,
                capture_output=True, text=True, timeout=120
            )
        return (r.stdout or "").strip() or (r.stderr or "").strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


def load_jobs():
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_jobs(jobs):
    os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
    try:
        with open(JOBS_FILE, "w") as f:
            json.dump(jobs, f, indent=2)
        return True
    except Exception as e:
        log_error(f"Save jobs failed: {e}")
        return False


def cron_time_to_schedule(minute, hour, day, month, dow):
    return f"{minute} {hour} {day} {month} {dow}"


class JobDialog(QDialog):
    def __init__(self, job=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Backup Job" + (" - Edit" if job else " - New"))
        self.setFixedSize(560, 480)
        apply_app_theme(self)
        layout = QFormLayout(self)

        self._name = QLineEdit()
        layout.addRow("Job Name:", self._name)

        self._src = QLineEdit()
        self._src.setPlaceholderText(os.path.expanduser("~/Documents"))
        layout.addRow("Source Path:", self._src)

        self._dst = QLineEdit()
        self._dst.setPlaceholderText(f"{BACKUP_DIR}/Documents")
        layout.addRow("Destination:", self._dst)

        self._method = QComboBox()
        self._method.addItems(["rsync (incremental)", "tar.gz (full archive)", "7z (compressed)"])
        layout.addRow("Method:", self._method)

        self._schedule = QComboBox()
        self._schedule.addItems(["Daily", "Weekly", "Monthly", "Custom cron"])
        layout.addRow("Schedule:", self._schedule)

        self._time = QLineEdit()
        self._time.setPlaceholderText("02:00")
        layout.addRow("Time (HH:MM):", self._time)

        self._custom_cron = QLineEdit()
        self._custom_cron.setPlaceholderText("* * * * *")
        layout.addRow("Custom Cron:", self._custom_cron)

        self._retention = QSpinBox()
        self._retention.setRange(1, 365)
        self._retention.setValue(7)
        layout.addRow("Retention (days):", self._retention)

        self._exclude = QLineEdit()
        self._exclude.setPlaceholderText("*.tmp, .cache, node_modules")
        layout.addRow("Exclude patterns:", self._exclude)

        self._notify = QCheckBox("Notify on completion")
        self._notify.setChecked(True)
        layout.addRow("", self._notify)

        self._enabled = QCheckBox("Enabled")
        self._enabled.setChecked(True)
        layout.addRow("", self._enabled)

        if job:
            self._name.setText(job.get("name", ""))
            self._src.setText(job.get("source", ""))
            self._dst.setText(job.get("dest", ""))
            self._method.setCurrentText(job.get("method", "rsync (incremental)"))
            self._schedule.setCurrentText(job.get("schedule", "Daily"))
            self._time.setText(job.get("time", "02:00"))
            self._custom_cron.setText(job.get("custom_cron", ""))
            self._retention.setValue(job.get("retention", 7))
            self._exclude.setText(job.get("exclude", ""))
            self._notify.setChecked(job.get("notify", True))
            self._enabled.setChecked(job.get("enabled", True))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_job(self):
        return {
            "name": self._name.text().strip(),
            "source": self._src.text().strip(),
            "dest": self._dst.text().strip(),
            "method": self._method.currentText(),
            "schedule": self._schedule.currentText(),
            "time": self._time.text().strip() or "02:00",
            "custom_cron": self._custom_cron.text().strip(),
            "retention": self._retention.value(),
            "exclude": self._exclude.text().strip(),
            "notify": self._notify.isChecked(),
            "enabled": self._enabled.isChecked(),
        }


class BackupScheduler(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Backup Scheduler")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        apply_app_theme(self)
        self._jobs = load_jobs()
        self._worker = None
        self._init_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(30000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Backup Scheduler",
            subtitle="Cron-scheduled rsync, tar.gz, and 7z archive jobs with retention",
            icon_name="document-save",
            badge_text="CRON",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Name", "Source", "Dest", "Schedule", "Method", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = make_button("Add Job", variant="primary", parent=self)
        add_btn.clicked.connect(self._add_job)
        btn_row.addWidget(add_btn)

        edit_btn = make_button("Edit Job", variant="secondary", parent=self)
        edit_btn.clicked.connect(self._edit_job)
        btn_row.addWidget(edit_btn)

        del_btn = make_button("Delete Job", variant="danger", parent=self)
        del_btn.clicked.connect(self._delete_job)
        btn_row.addWidget(del_btn)

        run_btn = make_button("Run Now", variant="secondary", parent=self)
        run_btn.clicked.connect(self._run_now)
        btn_row.addWidget(run_btn)

        sync_btn = make_button("Sync Crontab", variant="secondary", parent=self)
        sync_btn.clicked.connect(self._sync_cron)
        btn_row.addWidget(sync_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Preview
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(120)
        root.addWidget(self._preview)

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _refresh(self):
        self._jobs = load_jobs()
        self._table.setRowCount(0)
        for job in self._jobs:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(job.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(job.get("source", "")))
            self._table.setItem(row, 2, QTableWidgetItem(job.get("dest", "")))
            sched = job.get("schedule", "")
            if sched == "Custom cron":
                sched += f" ({job.get('custom_cron', '')})"
            else:
                sched += f" @ {job.get('time', '')}"
            self._table.setItem(row, 3, QTableWidgetItem(sched))
            self._table.setItem(row, 4, QTableWidgetItem(job.get("method", "")))
            status = "Enabled" if job.get("enabled", True) else "Disabled"
            item = QTableWidgetItem(status)
            col = COLORS["success"] if job.get("enabled", True) else COLORS["text_muted"]
            item.setForeground(QBrush(QColor(col)))
            self._table.setItem(row, 5, item)

        self._update_preview()
        self._status.setText(f"{len(self._jobs)} backup job(s)")

    def _selected_job(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._jobs[row]

    def _add_job(self):
        dlg = JobDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            job = dlg.get_job()
            if not job["name"] or not job["source"] or not job["dest"]:
                QMessageBox.warning(self, "Missing Info", "Name, source, and destination required.")
                return
            self._jobs.append(job)
            save_jobs(self._jobs)
            self._refresh()

    def _edit_job(self):
        job = self._selected_job()
        if not job:
            QMessageBox.warning(self, "No Selection", "Select a job first.")
            return
        dlg = JobDialog(job, self)
        if dlg.exec_() == QDialog.Accepted:
            new_job = dlg.get_job()
            for i, j in enumerate(self._jobs):
                if j.get("name") == job.get("name"):
                    self._jobs[i] = new_job
                    break
            save_jobs(self._jobs)
            self._refresh()

    def _delete_job(self):
        job = self._selected_job()
        if not job:
            QMessageBox.warning(self, "No Selection", "Select a job first.")
            return
        if QMessageBox.question(self, "Delete", f"Delete job '{job['name']}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._jobs = [j for j in self._jobs if j.get("name") != job["name"]]
            save_jobs(self._jobs)
            self._refresh()

    def _run_now(self):
        job = self._selected_job()
        if not job:
            return
        self._execute_job(job)

    @staticmethod
    def _build_job_cmd(job, timestamp):
        src = os.path.expanduser(job.get("source", "")).rstrip("/\\")
        dest = os.path.expanduser(job.get("dest", "")).rstrip("/\\")
        method = job.get("method", "rsync (incremental)")
        exclude = job.get("exclude", "")
        excludes = [e.strip() for e in exclude.split(",") if e.strip()]

        if method == "rsync (incremental)":
            cmd = ["rsync", "-avh", "--delete"]
            for e in excludes:
                cmd.append(f"--exclude={e}")
            cmd.extend([f"{src}/", f"{dest}/"])
            return cmd
        if method == "tar.gz (full archive)":
            out = os.path.join(dest, f"{job['name']}_{timestamp}.tar.gz")
            cmd = ["tar", "-czf", out]
            for e in excludes:
                cmd.append(f"--exclude={e}")
            parent = os.path.dirname(src) or "."
            base = os.path.basename(src) or "."
            cmd.extend(["-C", parent, base])
            return cmd
        out = os.path.join(dest, f"{job['name']}_{timestamp}.7z")
        cmd = ["7z", "a", out, src]
        for e in excludes:
            cmd.append(f"-x!{e}")
        return cmd

    def _execute_job(self, job):
        src = os.path.expanduser(job.get("source", "")).strip()
        dest = os.path.expanduser(job.get("dest", "")).strip()
        if not src or not dest:
            return
        if not os.path.exists(src):
            QMessageBox.warning(self, "Missing Source", f"Source path does not exist:\n{src}")
            return
        os.makedirs(dest, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cmd = self._build_job_cmd(job, timestamp)
        if not shutil.which(cmd[0]):
            QMessageBox.warning(self, "Missing Tool", f"Required command '{cmd[0]}' is not installed.")
            return

        if self._worker is not None and self._worker.isRunning():
            self._status.setText("Another backup job is already running...")
            return

        self._status.setText(f"Running: {job['name']}...")
        w = CmdWorker(cmd, sudo=False)
        w.done.connect(lambda ok, out: self._job_done(ok, out, job))
        w.start()
        self._worker = w

    def _job_done(self, ok, out, job):
        if ok:
            self._status.setText(f"Backup complete: {job['name']}")
            log_info(f"Backup job '{job['name']}' completed")
            self._cleanup_old(job)
        else:
            self._status.setText(f"Backup failed: {out[:80]}")
            log_error(f"Backup job '{job['name']}' failed: {out}")

    def _cleanup_old(self, job):
        dest = os.path.expanduser(job.get("dest", ""))
        retention = job.get("retention", 7)
        if not dest or not os.path.exists(dest):
            return
        try:
            now = time.time()
            for fname in os.listdir(dest):
                path = os.path.join(dest, fname)
                if os.path.isfile(path):
                    age = now - os.path.getmtime(path)
                    if age > retention * 86400:
                        os.remove(path)
                        log_info(f"Removed old backup: {path}")
        except Exception as e:
            log_error(f"Cleanup failed: {e}")

    def _sync_cron(self):
        """Update user's crontab with backup jobs."""
        if not shutil.which("crontab"):
            QMessageBox.warning(self, "Crontab Unavailable", "'crontab' command not found on system.")
            return
        try:
            out, _ = run_cmd(["crontab", "-l"])
            lines = [line for line in (out.splitlines() if out else []) if CRONTAB_MARKER not in line and not line.startswith("no crontab for")]

            for job in self._jobs:
                if not job.get("enabled", True):
                    continue
                sched = job.get("schedule", "Daily")
                t = job.get("time", "02:00")
                parts = t.split(":")
                hour = parts[0] if len(parts) >= 2 and parts[0].isdigit() else "02"
                minute = parts[1] if len(parts) >= 2 and parts[1].isdigit() else "00"
                if sched == "Daily":
                    cron = f"{int(minute)} {int(hour)} * * *"
                elif sched == "Weekly":
                    cron = f"{int(minute)} {int(hour)} * * 0"
                elif sched == "Monthly":
                    cron = f"{int(minute)} {int(hour)} 1 * *"
                else:
                    cron = job.get("custom_cron", "* * * * *").strip() or "* * * * *"

                cmd_list = self._build_job_cmd(job, "$(date +\\%Y\\%m\\%d_\\%H\\%M\\%S)")
                quoted = " ".join(
                    arg if "$(date" in arg else shlex.quote(arg)
                    for arg in cmd_list
                )
                lines.append(f"{cron} {quoted} {CRONTAB_MARKER} {job['name']}")

            payload = "\n".join(lines) + ("\n" if lines else "")
            msg, ok = run_cmd(["crontab", "-"], input_data=payload)
            if ok:
                self._status.setText("Crontab synced")
                log_info("Backup crontab updated")
            else:
                self._status.setText(f"Cron sync failed: {msg}")
        except Exception as e:
            log_error(f"Cron sync failed: {e}")
            self._status.setText(f"Cron sync failed: {e}")

    def _update_preview(self):
        self._preview.clear()
        for job in self._jobs:
            self._preview.append(f"# {job.get('name')}")
            self._preview.append(f"  Source: {job.get('source')} -> {job.get('dest')}")
            self._preview.append(f"  Method: {job.get('method')}")
            self._preview.append(f"  Schedule: {job.get('schedule')} @ {job.get('time')}")
            if job.get("custom_cron"):
                self._preview.append(f"  Cron: {job.get('custom_cron')}")
            self._preview.append(f"  Retention: {job.get('retention')} days")
            self._preview.append(f"  Enabled: {job.get('enabled', True)}")
            self._preview.append("")

    def closeEvent(self, event):
        self._timer.stop()
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        event.accept()


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, sudo=False):
        super().__init__()
        self.cmd = cmd
        self.sudo = sudo
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
        full_cmd = list(self.cmd)
        if self.sudo and (os.geteuid() != 0 if hasattr(os, "geteuid") else True):
            pk = shutil.which("pkexec")
            if pk:
                full_cmd = [pk] + full_cmd
        try:
            self._proc = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            out, _ = self._proc.communicate(timeout=300)
            if not self._stopped:
                self.done.emit(self._proc.returncode == 0, (out or "").strip())
        except Exception as e:
            if not self._stopped:
                self.done.emit(False, str(e))
        finally:
            self._proc = None


def main():
    app = QApplication(sys.argv)
    win = BackupScheduler()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
