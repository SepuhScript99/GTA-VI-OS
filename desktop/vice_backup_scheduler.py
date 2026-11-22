#!/usr/bin/env python3
"""Vice OS — Backup Scheduler. Cron-based backup jobs with retention policies."""

import sys
import os
import subprocess
import json
import shlex

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QTextEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QTextEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; }
QCheckBox { color: #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""

BACKUP_DIR = os.path.expanduser("~/backups")
JOBS_FILE = os.path.expanduser("~/.config/vice-os/backup_jobs.json")
CRONTAB_MARKER = "# VICE BACKUP JOBS"


def run_cmd(cmd):
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
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
        self.setStyleSheet(STYLE)
        layout = QFormLayout(self)

        self._name = QLineEdit()
        layout.addRow("Job Name:", self._name)

        self._src = QLineEdit()
        self._src.setPlaceholderText("/home/user/Documents")
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
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._jobs = load_jobs()
        self._init_ui()
        self._refresh()
        self._timer = QTimer()
        self._timer.setInterval(30000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Backup Scheduler")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

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
        root.addWidget(self._table)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Job")
        add_btn.clicked.connect(self._add_job)
        btn_row.addWidget(add_btn)

        edit_btn = QPushButton("Edit Job")
        edit_btn.clicked.connect(self._edit_job)
        btn_row.addWidget(edit_btn)

        del_btn = QPushButton("Delete Job")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_btn.clicked.connect(self._delete_job)
        btn_row.addWidget(del_btn)

        run_btn = QPushButton("Run Now")
        run_btn.clicked.connect(self._run_now)
        btn_row.addWidget(run_btn)

        sync_btn = QPushButton("Sync Crontab")
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
        self._status.setStyleSheet("color: #888; font-size: 11px;")
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
            item.setForeground(QBrush(QColor("#00ff88" if job.get("enabled", True) else "#888")))
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

    def _execute_job(self, job):
        src = job.get("source", "")
        dest = job.get("dest", "")
        if not src or not dest:
            return
        os.makedirs(dest, exist_ok=True)
        method = job.get("method", "rsync")
        exclude = job.get("exclude", "")

        if method == "rsync (incremental)":
            excl = ""
            for e in exclude.split(","):
                e = e.strip()
                if e:
                    excl += f" --exclude='{e}'"
            cmd = f"rsync -avh --delete{excl} {shlex.quote(src)}/ {shlex.quote(dest)}/"
        elif method == "tar.gz (full archive)":
            timestamp = subprocess.check_output(["date", "+%Y%m%d_%H%M%S"], text=True).strip()
            out = os.path.join(dest, f"{job['name']}_{timestamp}.tar.gz")
            excl = ""
            for e in exclude.split(","):
                e = e.strip()
                if e:
                    excl += f" --exclude='{e}'"
            cmd = f"tar -czf {shlex.quote(out)} {excl} -C {shlex.quote(os.path.dirname(src))} {os.path.basename(src)}"
        else:  # 7z
            timestamp = subprocess.check_output(["date", "+%Y%m%d_%H%M%S"], text=True).strip()
            out = os.path.join(dest, f"{job['name']}_{timestamp}.7z")
            excl = ""
            for e in exclude.split(","):
                e = e.strip()
                if e:
                    excl += f" -x!{e}"
            cmd = f"7z a {shlex.quote(out)} {shlex.quote(src)} {excl}"

        self._status.setText(f"Running: {job['name']}...")
        w = CmdWorker(cmd, sudo=False)
        w.done.connect(lambda ok, out: self._job_done(ok, out, job))
        w.start()
        self._worker = w

    def _job_done(self, ok, out, job):
        if ok:
            self._status.setText(f"Backup complete: {job['name']}")
            log_info(f"Backup job '{job['name']}' completed")
            # Cleanup old backups
            self._cleanup_old(job)
        else:
            self._status.setText(f"Backup failed: {out[:80]}")
            log_error(f"Backup job '{job['name']}' failed: {out}")

    def _cleanup_old(self, job):
        dest = job.get("dest", "")
        retention = job.get("retention", 7)
        if not dest or not os.path.exists(dest):
            return
        try:
            import time
            now = time.time()
            for f in os.listdir(dest):
                path = os.path.join(dest, f)
                if os.path.isfile(path):
                    age = now - os.path.getmtime(path)
                    if age > retention * 86400:
                        os.remove(path)
                        log_info(f"Removed old backup: {path}")
        except Exception as e:
            log_error(f"Cleanup failed: {e}")

    def _sync_cron(self):
        """Update user's crontab with backup jobs."""
        try:
            # Get current crontab
            out, _ = run_cmd("crontab -l")
            lines = out.splitlines() if out else []

            # Remove old VICE backup entries
            lines = [l for l in lines if CRONTAB_MARKER not in l]

            for job in self._jobs:
                if not job.get("enabled", True):
                    continue
                sched = job.get("schedule", "Daily")
                t = job.get("time", "02:00")
                if sched == "Daily":
                    cron = f"{t.split(':')[1]} {t.split(':')[0]} * * *"
                elif sched == "Weekly":
                    cron = f"{t.split(':')[1]} {t.split(':')[0]} * * 0"
                elif sched == "Monthly":
                    cron = f"{t.split(':')[1]} {t.split(':')[0]} 1 * *"
                else:
                    cron = job.get("custom_cron", "* * * * *")

                src = job.get("source", "").replace("'", "'\\''")
                dest = job.get("dest", "").replace("'", "'\\''")
                cmd = f"cd ~ && {sys.executable} -c \"import os,sys; from backup_scheduler import run_backup; run_backup('{job['name']}')\""
                # Simpler: use a wrapper script
                lines.append(f"{cron} {CRONTAB_MARKER} {job['name']}")

            run_cmd("crontab -", input_data="\n".join(lines))
            self._status.setText("Crontab synced")
            log_info("Backup crontab updated")
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


class CmdWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, cmd, sudo=False):
        super().__init__()
        self.cmd = cmd
        self.sudo = sudo

    def run(self):
        out, ok = run_cmd(self.cmd, self.sudo)
        self.done.emit(ok, out)


def main():
    app = QApplication(sys.argv)
    win = BackupScheduler()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()