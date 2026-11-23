#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice World Clock & Host Time Sync.
Displays live local time synced with host timezone (/etc/localtime dynamic
tzset watcher), world reference clocks, one-click Sync With Host & Internet
Timezone (pkexec /usr/local/bin/vice-timesync --auto --force), searchable IANA
timezone selector (--set <TZ>), and Chrony/VirtualBox timesync diagnostics.
Styled via vice_theme (Noto Sans CJK fallback).
"""

from datetime import datetime
import os
import shutil
import signal
import subprocess
import sys
import time

try:
    from zoneinfo import ZoneInfo, available_timezones
except ImportError:
    ZoneInfo = None
    available_timezones = None

from PyQt5.QtCore import Qt, QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    load_tool_icon,
    make_button,
    make_card,
    make_header,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


WORLD_ZONES = [
    ("UTC", "UTC"),
    ("Miami / New York", "America/New_York"),
    ("London", "Europe/London"),
    ("Tokyo", "Asia/Tokyo"),
    ("Jakarta", "Asia/Jakarta"),
    ("Sydney", "Australia/Sydney"),
]


def _find_timesync_bin() -> str:
    found = shutil.which("vice-timesync")
    if found:
        return found
    repo_root = os.path.abspath(os.path.join(_HERE, ".."))
    for cand in (
        "/usr/local/bin/vice-timesync",
        "/usr/local/system_scripts/vice-timesync.sh",
        os.path.join(repo_root, "system_scripts", "vice-timesync.sh"),
    ):
        if os.path.isfile(cand):
            return cand
    return "/usr/local/bin/vice-timesync"


def _read_active_timezone() -> str:
    if os.path.isfile("/etc/timezone"):
        try:
            with open("/etc/timezone", "r", encoding="utf-8", errors="replace") as fp:
                tz = fp.read().strip()
            if tz:
                return tz
        except OSError:
            pass
    try:
        target = os.path.realpath("/etc/localtime")
        marker = "/usr/share/zoneinfo/"
        if marker in target:
            return target.split(marker, 1)[1]
    except OSError:
        pass
    return time.tzname[0] or "UTC"


def _collect_iana_zones() -> list:
    zones = set()
    tab_path = "/usr/share/zoneinfo/zone1970.tab"
    if os.path.isfile(tab_path):
        try:
            with open(tab_path, "r", encoding="utf-8", errors="replace") as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    cols = line.split("\t")
                    if len(cols) >= 3:
                        zones.add(cols[2].strip())
        except OSError:
            pass
    if not zones and available_timezones is not None:
        try:
            zones = {
                z for z in available_timezones()
                if "/" in z and not z.startswith(("Etc/", "posix/", "right/"))
            }
        except Exception:
            zones = set()
    zones.add("UTC")
    return sorted(zones)


class ClockDiagnosticsWorker(QThread):
    """Collects vice-timesync --status, timedatectl, Chrony, and VBoxService status off UI thread."""
    report_ready = pyqtSignal(str)

    def __init__(self, timesync_bin: str):
        super().__init__()
        self._bin = timesync_bin
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def _run(self, cmd: list) -> str:
        if not cmd or (not os.path.isfile(cmd[0]) and not shutil.which(cmd[0])):
            return f"[{cmd[0]} not found]"
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            out = res.stdout.strip() or res.stderr.strip()
            return out or "(no output)"
        except Exception as exc:
            return f"Error: {exc}"

    def run(self) -> None:
        sections = []
        if os.path.isfile(self._bin) or shutil.which(self._bin):
            cmd = [self._bin, "--status"]
            if self._bin.endswith(".sh") and shutil.which("bash"):
                cmd = ["bash", self._bin, "--status"]
            sections.append("=== vice-timesync --status ===\n" + self._run(cmd))

        if shutil.which("timedatectl"):
            sections.append("=== timedatectl ===\n" + self._run(["timedatectl"]))

        if shutil.which("chronyc"):
            sections.append("=== Chrony Tracking (chronyc tracking) ===\n" + self._run(["chronyc", "tracking"]))
            sections.append("=== Chrony Sources (chronyc sources -v) ===\n" + self._run(["chronyc", "sources", "-v"]))

        if shutil.which("systemctl"):
            sections.append(
                "=== VirtualBox & Sync Services ===\n" + self._run([
                    "systemctl", "is-active", "chrony", "vboxservice",
                    "virtualbox-guest-utils", "vice-timesync.timer"
                ])
            )

        if not self._stopped:
            self.report_ready.emit("\n\n".join(sections))


class ViceClockSyncApp(QMainWindow):
    """Main window for Vice World Clock & Host Time Sync."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice World Clock & Host Time Sync — Vice OS")
        self.resize(940, 660)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-clock-sync", "preferences-system-time")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._timesync_bin = _find_timesync_bin()
        self._all_zones = _collect_iana_zones()
        self._last_localtime_mtime = self._stat_localtime()
        self._sync_proc = None
        self._diag_worker = None
        self._world_labels = []

        self._init_ui()
        self._populate_tz_list()
        self._tick_clock()
        self._refresh_diagnostics()

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start()

    @staticmethod
    def _stat_localtime() -> float:
        try:
            return os.lstat("/etc/localtime").st_mtime
        except OSError:
            return 0.0

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice World Clock & Host Time Sync",
            subtitle="Live local clock, host/internet timezone sync, IANA selector, and Chrony/VBox diagnostics",
            icon_name="vice-tool-clock-sync",
            badge_text=_read_active_timezone(),
            badge_variant="aqua",
            parent=root,
        )
        self._sync_btn = make_button("Sync With Host && Internet Timezone", variant="primary", parent=self._header)
        self._sync_btn.clicked.connect(lambda: self._run_timesync(["--auto", "--force"], "Auto-syncing clock & timezone..."))
        self._header.right_layout.addWidget(self._sync_btn)
        layout.addWidget(self._header)

        # Top Hero Clock + World Clocks
        clock_card = make_card(parent=root, margins=(16, 14, 16, 14), spacing=8)
        top_clock_row = QHBoxLayout()
        left_clock = QVBoxLayout()
        left_clock.setSpacing(4)
        self._clock_lbl = QLabel("--:--:--", clock_card)
        self._clock_lbl.setObjectName("ClockDisplay")
        left_clock.addWidget(self._clock_lbl)

        self._date_lbl = QLabel("Loading date...", clock_card)
        self._date_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        left_clock.addWidget(self._date_lbl)
        top_clock_row.addLayout(left_clock, 1)

        quick_btns = QVBoxLayout()
        quick_btns.setSpacing(6)
        self._sync_only_btn = make_button("Sync Clock Only (Keep TZ)", variant="secondary", parent=clock_card)
        self._sync_only_btn.clicked.connect(lambda: self._run_timesync(["--sync-only"], "Stepping clock from host/NTP..."))
        quick_btns.addWidget(self._sync_only_btn)

        diag_btn = make_button("Refresh Diagnostics", variant="secondary", icon_name="view-refresh", parent=clock_card)
        diag_btn.clicked.connect(self._refresh_diagnostics)
        quick_btns.addWidget(diag_btn)
        top_clock_row.addLayout(quick_btns)
        clock_card.body_layout.addLayout(top_clock_row)

        world_grid = QGridLayout()
        world_grid.setSpacing(10)
        for idx, (city, tz_name) in enumerate(WORLD_ZONES):
            box = QVBoxLayout()
            box.setSpacing(2)
            city_lbl = QLabel(city, clock_card)
            city_lbl.setObjectName("MutedLabel")
            time_lbl = QLabel("--:--", clock_card)
            time_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 14px;")
            box.addWidget(city_lbl)
            box.addWidget(time_lbl)
            world_grid.addLayout(box, 0, idx)
            self._world_labels.append((tz_name, time_lbl))
        clock_card.body_layout.addLayout(world_grid)
        layout.addWidget(clock_card)

        # Bottom Split: Searchable IANA Timezone Selector | Chrony/VBox Diagnostics
        lower = QHBoxLayout()
        lower.setSpacing(12)

        tz_card = make_card(title="IANA Timezone Selector", parent=root)
        self._tz_search = QLineEdit(tz_card)
        self._tz_search.setPlaceholderText("Search timezone (e.g. America/New_York, Asia/Tokyo)...")
        self._tz_search.setClearButtonEnabled(True)
        self._tz_search.textChanged.connect(self._populate_tz_list)
        tz_card.body_layout.addWidget(self._tz_search)

        self._tz_list = QListWidget(tz_card)
        self._tz_list.itemDoubleClicked.connect(lambda _it: self._apply_selected_tz())
        tz_card.body_layout.addWidget(self._tz_list, 1)

        self._apply_tz_btn = make_button("Set Selected Timezone", variant="primary", parent=tz_card)
        self._apply_tz_btn.clicked.connect(self._apply_selected_tz)
        tz_card.body_layout.addWidget(self._apply_tz_btn)
        lower.addWidget(tz_card, 2)

        diag_card = make_card(title="Chrony & VirtualBox Timesync Diagnostics", parent=root)
        self._diag_out = QPlainTextEdit(diag_card)
        self._diag_out.setReadOnly(True)
        self._diag_out.setPlainText("Collecting timesync diagnostics...")
        diag_card.body_layout.addWidget(self._diag_out, 1)

        self._status_lbl = QLabel("Ready.", diag_card)
        self._status_lbl.setObjectName("MutedLabel")
        self._status_lbl.setWordWrap(True)
        diag_card.body_layout.addWidget(self._status_lbl)
        lower.addWidget(diag_card, 3)

        layout.addLayout(lower, 1)

    def _tick_clock(self) -> None:
        cur_mtime = self._stat_localtime()
        if cur_mtime != self._last_localtime_mtime:
            self._last_localtime_mtime = cur_mtime
            if hasattr(time, "tzset"):
                time.tzset()
            self._header.set_badge(_read_active_timezone(), "aqua")

        now_local = datetime.now().astimezone()
        self._clock_lbl.setText(now_local.strftime("%H:%M:%S"))
        tz_active = _read_active_timezone()
        offset = now_local.strftime("%z")
        offset_fmt = f"UTC{offset[:3]}:{offset[3:]}" if len(offset) == 5 else "UTC"
        self._date_lbl.setText(
            f"{now_local.strftime('%A, %d %B %Y')}  ·  {tz_active} ({offset_fmt})"
        )

        for tz_name, lbl in self._world_labels:
            if ZoneInfo is not None:
                try:
                    dt = datetime.now(ZoneInfo(tz_name))
                    lbl.setText(dt.strftime("%H:%M  (%a)"))
                    continue
                except Exception:
                    pass
            lbl.setText("N/A")

    def _populate_tz_list(self) -> None:
        query = self._tz_search.text().strip().lower()
        active = _read_active_timezone()
        self._tz_list.clear()
        for tz in self._all_zones:
            if query and query not in tz.lower():
                continue
            item = QListWidgetItem(tz)
            item.setData(Qt.UserRole, tz)
            self._tz_list.addItem(item)
            if tz == active:
                self._tz_list.setCurrentItem(item)

    def _apply_selected_tz(self) -> None:
        item = self._tz_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Select Timezone", "Select an IANA timezone from the list first.")
            return
        tz = item.data(Qt.UserRole)
        if tz:
            self._run_timesync(["--set", tz], f"Setting timezone to {tz}...")

    def _run_timesync(self, ts_args: list, busy_msg: str) -> None:
        if self._sync_proc is not None and self._sync_proc.state() != QProcess.NotRunning:
            self._status_lbl.setText("Time sync already in progress...")
            return

        runner = self._timesync_bin
        if not os.path.isfile(runner) and not shutil.which(runner):
            QMessageBox.warning(self, "Missing vice-timesync", f"Cannot find {runner}.")
            return

        if os.geteuid() == 0 if hasattr(os, "geteuid") else False:
            prog = runner
            args = ts_args
        elif shutil.which("pkexec"):
            prog = "pkexec"
            args = [runner] + ts_args
        else:
            prog = runner
            args = ts_args

        self._sync_btn.setEnabled(False)
        self._sync_only_btn.setEnabled(False)
        self._apply_tz_btn.setEnabled(False)
        self._status_lbl.setText(busy_msg)

        self._sync_proc = QProcess(self)
        self._sync_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._sync_proc.finished.connect(self._on_timesync_finished)
        self._sync_proc.start(prog, args)

    def _on_timesync_finished(self, exit_code: int, _status) -> None:
        self._sync_btn.setEnabled(True)
        self._sync_only_btn.setEnabled(True)
        self._apply_tz_btn.setEnabled(True)

        output = ""
        if self._sync_proc is not None:
            output = bytes(self._sync_proc.readAllStandardOutput()).decode("utf-8", errors="replace").strip()

        if hasattr(time, "tzset"):
            time.tzset()
        self._last_localtime_mtime = self._stat_localtime()
        self._header.set_badge(_read_active_timezone(), "success" if exit_code == 0 else "danger")
        self._tick_clock()

        if exit_code == 0:
            self._status_lbl.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600;")
            self._status_lbl.setText(output.splitlines()[-1] if output else "Clock & timezone synced.")
            log_info("Vice Clock Sync completed successfully")
        else:
            self._status_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-weight: 600;")
            self._status_lbl.setText(output or f"Time sync exited with code {exit_code}.")

        self._refresh_diagnostics()

    def _refresh_diagnostics(self) -> None:
        if self._diag_worker is not None and self._diag_worker.isRunning():
            return
        self._diag_worker = ClockDiagnosticsWorker(self._timesync_bin)
        self._diag_worker.report_ready.connect(self._diag_out.setPlainText)
        self._diag_worker.start()

    def closeEvent(self, event) -> None:
        self._clock_timer.stop()
        if self._sync_proc is not None and self._sync_proc.state() != QProcess.NotRunning:
            self._sync_proc.terminate()
            if not self._sync_proc.waitForFinished(800):
                self._sync_proc.kill()
                self._sync_proc.waitForFinished(400)
        if self._diag_worker is not None:
            self._diag_worker.stop()
            if self._diag_worker.isRunning():
                self._diag_worker.wait(1500)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceClockSyncApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
