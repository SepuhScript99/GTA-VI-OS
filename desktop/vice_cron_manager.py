#!/usr/bin/env python3
"""Vice OS — Cron Job Manager. Full crontab editor with visual schedule builder."""

import sys
import os
import subprocess

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QComboBox, QSpinBox, QLineEdit,
    QDialogButtonBox, QTabWidget, QTextEdit, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 12px; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QLabel { color: #00ffff; }
"""

FIELD_NAMES = ["Minute", "Hour", "Day of Month", "Month", "Day of Week"]


def load_crontab():
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return [], ""
        return r.stdout.splitlines(), r.stdout
    except Exception as e:
        log_error(f"crontab -l failed: {e}")
        return [], ""


def save_crontab(content):
    try:
        proc = subprocess.run(["crontab", "-"], input=content, text=True,
                              capture_output=True, timeout=5)
        return proc.returncode == 0, proc.stderr.strip()
    except Exception as e:
        return False, str(e)


def parse_job_line(line):
    """Parse a cron line into (schedule fields, command)."""
    parts = line.split(None, 5)
    if len(parts) < 6:
        return None
    return parts[:5], parts[5]


class CronBuilderDialog(QDialog):
    def __init__(self, schedule=None, command="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cron Job Builder")
        self.setFixedSize(560, 420)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)

        # Preset schedules
        preset_box = QGroupBox("Preset Schedule")
        pl = QHBoxLayout(preset_box)
        self._preset = QComboBox()
        self._preset.addItems([
            "Custom...",
            "Every minute",
            "Every 5 minutes",
            "Every hour",
            "Every day @ 02:00",
            "Every Sunday @ 03:00",
            "Every month (1st) @ 00:00",
        ])
        self._preset.currentIndexChanged.connect(self._apply_preset)
        pl.addWidget(self._preset)
        layout.addWidget(preset_box)

        # Custom fields
        custom_box = QGroupBox("Custom Schedule")
        form = QFormLayout(custom_box)
        self._fields = []
        defaults = schedule if schedule else ["*", "*", "*", "*", "*"]
        # Map day-of-week names to numbers when loading
        dow_map = {"sun": "0", "mon": "1", "tue": "2", "wed": "3", "thu": "4",
                   "fri": "5", "sat": "6"}
        for i, name in enumerate(FIELD_NAMES):
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(["*"] + [str(n) for n in range(0, 60 if i == 0 else 24 if i == 1 else 32 if i == 2 else 13)])
            val = defaults[i].lower()
            for dname, dnum in dow_map.items():
                val = val.replace(dname, dnum)
            combo.setCurrentText(val)
            self._fields.append(combo)
            form.addRow(name + ":", combo)
        layout.addWidget(custom_box)

        # Command
        cmd_box = QGroupBox("Command")
        cl = QVBoxLayout(cmd_box)
        self._command = QLineEdit(command)
        self._command.setPlaceholderText("/usr/local/bin/vice-backup.sh")
        cl.addWidget(self._command)
        layout.addWidget(cmd_box)

        # Preview
        self._preview = QLabel()
        self._preview.setStyleSheet("color: #ff00ff; font-size: 11px;")
        layout.addWidget(self._preview)
        for f in self._fields:
            f.currentTextChanged.connect(self._update_preview)
        self._command.textChanged.connect(self._update_preview)
        self._update_preview()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _apply_preset(self, index):
        presets = {
            1: ["*", "*", "*", "*", "*"],
            2: ["*/5", "*", "*", "*", "*"],
            3: ["0", "*", "*", "*", "*"],
            4: ["0", "2", "*", "*", "*"],
            5: ["0", "3", "*", "*", "0"],
            6: ["0", "0", "1", "*", "*"],
        }
        if index in presets:
            for field, value in zip(self._fields, presets[index]):
                field.setCurrentText(value)

    def _update_preview(self):
        self._preview.setText("Cron: " + self.get_schedule() + " " + self._command.text())

    def get_schedule(self):
        return " ".join(f.currentText() for f in self._fields)

    def get_command(self):
        return self._command.text().strip()


class CronManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Cron Job Manager")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Cron Job Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # --- Jobs tab ---
        jobs_tab = QWidget()
        jl = QVBoxLayout(jobs_tab)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Schedule", "Command", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        jl.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Job")
        add_btn.clicked.connect(self._add_job)
        btn_row.addWidget(add_btn)
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_job)
        btn_row.addWidget(edit_btn)
        del_btn = QPushButton("Delete Selected")
        del_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        del_btn.clicked.connect(self._delete_job)
        btn_row.addWidget(del_btn)
        reload_btn = QPushButton("Reload from System")
        reload_btn.clicked.connect(self._refresh)
        btn_row.addWidget(reload_btn)
        jl.addLayout(btn_row)
        tabs.addTab(jobs_tab, "Jobs")

        # --- Raw tab ---
        raw_tab = QWidget()
        rl = QVBoxLayout(raw_tab)
        self._raw_edit = QTextEdit()
        self._raw_edit.setFont(QFont("monospace", 12))
        rl.addWidget(self._raw_edit)
        raw_btns = QHBoxLayout()
        save_raw_btn = QPushButton("Save Raw Crontab")
        save_raw_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        save_raw_btn.clicked.connect(self._save_raw)
        raw_btns.addWidget(save_raw_btn)
        reload_raw_btn = QPushButton("Reload")
        reload_raw_btn.clicked.connect(self._load_raw)
        raw_btns.addWidget(reload_raw_btn)
        raw_btns.addStretch()
        rl.addLayout(raw_btns)
        tabs.addTab(raw_tab, "Raw Crontab")

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _get_jobs(self):
        """Return (job_lines, other_lines) from current crontab."""
        lines, _ = load_crontab()
        jobs = []
        others = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                others.append(line)
                continue
            if parse_job_line(stripped):
                jobs.append(stripped)
            else:
                others.append(line)
        return jobs, others

    def _refresh(self):
        self._table.setRowCount(0)
        jobs, others = self._get_jobs()

        for job in jobs:
            sched, cmd = parse_job_line(job)
            row = self._table.rowCount()
            self._table.insertRow(row)
            sched_item = QTableWidgetItem(" ".join(sched))
            sched_item.setForeground(QBrush(QColor("#ff00ff")))
            self._table.setItem(row, 0, sched_item)
            self._table.setItem(row, 1, QTableWidgetItem(cmd))
            self._table.setItem(row, 2, QTableWidgetItem(describe_schedule(sched)))

        self._load_raw()
        self._status.setText(f"{len(jobs)} cron job(s)")

    def _load_raw(self):
        _, raw = load_crontab()
        self._raw_edit.setPlainText(raw or "no crontab for user\n")

    def _save_raw(self):
        ok, err = save_crontab(self._raw_edit.toPlainText())
        if ok:
            self._status.setText("Crontab saved")
            log_info("Crontab saved (raw)")
            self._refresh()
        else:
            QMessageBox.warning(self, "Save Failed", err or "crontab rejected input")
            log_error(f"Crontab save failed: {err}")

    def _add_job(self):
        dlg = CronBuilderDialog(parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        sched, cmd = dlg.get_schedule(), dlg.get_command()
        if not cmd:
            QMessageBox.warning(self, "Missing Command", "Enter a command to run.")
            return
        jobs, others = self._get_jobs()
        jobs.append(f"{sched} {cmd}")
        self._commit(jobs, others)

    def _selected_job(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        jobs, _ = self._get_jobs()
        if row >= len(jobs):
            return None
        return jobs[row]

    def _edit_job(self):
        job = self._selected_job()
        if job is None:
            QMessageBox.warning(self, "No Selection", "Select a job first.")
            return
        sched, cmd = parse_job_line(job)
        dlg = CronBuilderDialog(sched, cmd, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_sched, new_cmd = dlg.get_schedule(), dlg.get_command()
        if not new_cmd:
            QMessageBox.warning(self, "Missing Command", "Enter a command to run.")
            return
        row = self._table.currentRow()
        jobs, others = self._get_jobs()
        jobs[row] = f"{new_sched} {new_cmd}"
        self._commit(jobs, others)

    def _delete_job(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a job first.")
            return
        job = self._selected_job()
        if job is None:
            return
        if QMessageBox.question(self, "Delete Job", f"Delete:\n{job}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        jobs, others = self._get_jobs()
        jobs.pop(row)
        self._commit(jobs, others)

    def _commit(self, jobs, others):
        """Write jobs + other lines (comments, env vars) back to crontab."""
        content = "\n".join(others + jobs) + "\n"
        ok, err = save_crontab(content)
        if ok:
            self._status.setText(f"Saved — {len(jobs)} job(s)")
            log_info(f"Crontab updated: {len(jobs)} jobs")
            self._refresh()
        else:
            QMessageBox.warning(self, "Save Failed", err or "crontab rejected input")
            log_error(f"Crontab commit failed: {err}")


def describe_schedule(sched):
    """Human-readable description of a cron schedule."""
    m, h, dom, mon, dow = sched
    parts = []
    if m == "*" and h == "*":
        parts.append("every hour")
    elif m.startswith("*/"):
        parts.append(f"every {m[2:]} minutes")
    elif h == "*":
        parts.append(f"every hour at :{m.zfill(2)}")
    else:
        parts.append(f"daily at {h.zfill(2)}:{m.zfill(2)}")
    if dow != "*":
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        try:
            parts.append("on " + days[int(dow)])
        except (ValueError, IndexError):
            pass
    if dom != "*":
        parts.append(f"day {dom} of month")
    if mon != "*":
        parts.append(f"month {mon}")
    return ", ".join(parts)


def main():
    app = QApplication(sys.argv)
    win = CronManager()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()