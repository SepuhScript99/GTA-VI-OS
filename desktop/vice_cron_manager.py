#!/usr/bin/env python3
"""Vice OS — Cron Job Manager. Full crontab editor with visual schedule builder."""

import subprocess
import sys

from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640

FIELD_NAMES = ["Minute", "Hour", "Day of Month", "Month", "Day of Week"]
FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


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
        proc = subprocess.run(
            ["crontab", "-"], input=content, text=True, capture_output=True, timeout=5
        )
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
        self.setMinimumSize(560, 420)
        vt.apply_app_theme(self)
        layout = QVBoxLayout(self)

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

        custom_box = QGroupBox("Custom Schedule")
        form = QFormLayout(custom_box)
        self._fields = []
        defaults = schedule if schedule else ["*", "*", "*", "*", "*"]
        dow_map = {
            "sun": "0", "mon": "1", "tue": "2", "wed": "3",
            "thu": "4", "fri": "5", "sat": "6",
        }
        for i, name in enumerate(FIELD_NAMES):
            combo = QComboBox()
            combo.setEditable(True)
            lo, hi = FIELD_RANGES[i]
            combo.addItems(["*"] + [str(n) for n in range(lo, hi + 1)])
            val = defaults[i].lower()
            for dname, dnum in dow_map.items():
                val = val.replace(dname, dnum)
            combo.setCurrentText(val)
            self._fields.append(combo)
            form.addRow(name + ":", combo)
        layout.addWidget(custom_box)

        cmd_box = QGroupBox("Command")
        cl = QVBoxLayout(cmd_box)
        self._command = QLineEdit(command)
        self._command.setPlaceholderText("/usr/local/bin/vice-backup.sh")
        cl.addWidget(self._command)
        layout.addWidget(cmd_box)

        self._preview = QLabel()
        self._preview.setStyleSheet(f"color: {vt.COLORS['accent_aqua']}; font-size: 11px;")
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
        return " ".join(f.currentText().strip() or "*" for f in self._fields)

    def get_command(self):
        return self._command.text().strip()


class CronManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Cron Job Manager")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 500)
        vt.apply_app_theme(self)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Cron Job Manager",
            "User crontab schedule builder and raw editor",
            icon_name="preferences-system-time",
            badge_text="CRONTAB",
            badge_variant="coral",
            parent=self,
        ))

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

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
        add_btn = vt.make_button("+ Add Job", "primary", parent=jobs_tab)
        add_btn.clicked.connect(self._add_job)
        btn_row.addWidget(add_btn)
        edit_btn = vt.make_button("Edit Selected", "secondary", parent=jobs_tab)
        edit_btn.clicked.connect(self._edit_job)
        btn_row.addWidget(edit_btn)
        del_btn = vt.make_button("Delete Selected", "danger", parent=jobs_tab)
        del_btn.clicked.connect(self._delete_job)
        btn_row.addWidget(del_btn)
        reload_btn = vt.make_button("Reload from System", "secondary", parent=jobs_tab)
        reload_btn.clicked.connect(self._refresh)
        btn_row.addWidget(reload_btn)
        jl.addLayout(btn_row)
        tabs.addTab(jobs_tab, "Jobs")

        raw_tab = QWidget()
        rl = QVBoxLayout(raw_tab)
        self._raw_edit = QTextEdit()
        self._raw_edit.setFont(QFont("monospace", 12))
        rl.addWidget(self._raw_edit)
        raw_btns = QHBoxLayout()
        save_raw_btn = vt.make_button("Save Raw Crontab", "primary", parent=raw_tab)
        save_raw_btn.clicked.connect(self._save_raw)
        raw_btns.addWidget(save_raw_btn)
        reload_raw_btn = vt.make_button("Reload", "secondary", parent=raw_tab)
        reload_raw_btn.clicked.connect(self._load_raw)
        raw_btns.addWidget(reload_raw_btn)
        raw_btns.addStretch()
        rl.addLayout(raw_btns)
        tabs.addTab(raw_tab, "Raw Crontab")

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
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
        jobs, _ = self._get_jobs()

        for job in jobs:
            parsed = parse_job_line(job)
            if not parsed:
                continue
            sched, cmd = parsed
            row = self._table.rowCount()
            self._table.insertRow(row)
            sched_item = QTableWidgetItem(" ".join(sched))
            sched_item.setForeground(QBrush(QColor(vt.COLORS["accent_aqua"])))
            self._table.setItem(row, 0, sched_item)
            self._table.setItem(row, 1, QTableWidgetItem(cmd))
            self._table.setItem(row, 2, QTableWidgetItem(describe_schedule(sched)))

        self._load_raw()
        self._status.setText(f"{len(jobs)} cron job(s)")

    def _load_raw(self):
        _, raw = load_crontab()
        self._raw_edit.setPlainText(raw or "# No crontab entries yet\n")

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
        if row < len(jobs):
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
        if QMessageBox.question(
            self, "Delete Job", f"Delete:\n{job}?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        jobs, others = self._get_jobs()
        if row < len(jobs):
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
        parts.append("every minute")
    elif m.startswith("*/") and h == "*":
        parts.append(f"every {m[2:]} minutes")
    elif h == "*":
        parts.append(f"every hour at :{m.zfill(2)}")
    else:
        parts.append(f"daily at {h.zfill(2)}:{m.zfill(2)}")
    if dow != "*":
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        try:
            idx = int(dow) % 7
            parts.append("on " + days[idx])
        except ValueError:
            parts.append(f"on dow={dow}")
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
