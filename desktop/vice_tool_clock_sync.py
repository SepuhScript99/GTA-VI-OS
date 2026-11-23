#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice World Clock, Interactive Calendar & Host Time Sync.
Displays live local time synced with host timezone (/etc/localtime dynamic
tzset watcher), world reference clocks, a Windows 11-inspired interactive
monthly calendar with Day/Date/Month/Year details, one-click Sync With Host &
Internet Timezone (pkexec /usr/local/bin/vice-timesync --auto --force),
searchable IANA timezone selector (--set <TZ>), and Chrony/VirtualBox timesync
diagnostics. Styled via vice_theme (Noto Sans CJK fallback).
"""

from datetime import date as py_date, datetime
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

from PyQt5.QtCore import QDate, QPointF, QProcess, QRectF, QSize, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCharFormat,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    MONO_STACK,
    apply_app_theme,
    load_tool_icon,
    make_badge,
    make_button,
    make_card,
    make_header,
    style_badge,
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
    try:
        target = os.path.realpath("/etc/localtime")
        marker = "/usr/share/zoneinfo/"
        if marker in target:
            return target.split(marker, 1)[1]
    except OSError:
        pass
    if os.path.isfile("/etc/timezone"):
        try:
            with open("/etc/timezone", "r", encoding="utf-8", errors="replace") as fp:
                tz = fp.read().strip()
            if tz:
                return tz
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


def _make_chevron_icon(direction: str) -> QIcon:
    """Render a crisp 14x14 alabaster left/right chevron icon for calendar nav buttons."""
    pix = QPixmap(14, 14)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(COLORS["text_primary"]), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    if direction == "left":
        path.moveTo(QPointF(9.0, 3.0))
        path.lineTo(QPointF(4.5, 7.0))
        path.lineTo(QPointF(9.0, 11.0))
    else:
        path.moveTo(QPointF(5.0, 3.0))
        path.lineTo(QPointF(9.5, 7.0))
        path.lineTo(QPointF(5.0, 11.0))
    painter.drawPath(path)
    painter.end()
    return QIcon(pix)


class ViceCalendarWidget(QCalendarWidget):
    """Windows 11-inspired rounded dark slate calendar widget with Leonida sunset highlights."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ViceCalendar")
        now_local = datetime.now().astimezone()
        self._today = QDate(now_local.year, now_local.month, now_local.day)

        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setFirstDayOfWeek(Qt.Monday)
        self.setNavigationBarVisible(True)
        self.setDateEditEnabled(True)

        header_fmt = QTextCharFormat()
        header_fmt.setBackground(QColor(COLORS["bg_surface"]))
        header_fmt.setForeground(QColor(COLORS["text_secondary"]))
        header_font = QFont("Noto Sans", 9, QFont.Bold)
        header_fmt.setFont(header_font)
        self.setHeaderTextFormat(header_fmt)

        # Override Qt's default harsh red weekend text with soft Leonida contrast
        weekend_fmt = QTextCharFormat()
        weekend_fmt.setForeground(QColor("#D99B8C"))
        self.setWeekdayTextFormat(Qt.Saturday, weekend_fmt)
        self.setWeekdayTextFormat(Qt.Sunday, weekend_fmt)

        prev_btn = self.findChild(QToolButton, "qt_calendar_prevmonth")
        if prev_btn is not None:
            prev_btn.setIcon(_make_chevron_icon("left"))
            prev_btn.setIconSize(QSize(14, 14))
            prev_btn.setToolTip("Previous Month")
        next_btn = self.findChild(QToolButton, "qt_calendar_nextmonth")
        if next_btn is not None:
            next_btn.setIcon(_make_chevron_icon("right"))
            next_btn.setIconSize(QSize(14, 14))
            next_btn.setToolTip("Next Month")

    def today_date(self) -> QDate:
        return self._today

    def set_today(self, today_qd: QDate) -> None:
        if today_qd != self._today:
            self._today = today_qd
            self.updateCells()

    def paintCell(self, painter: QPainter, rect, date: QDate) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(rect, QColor("#10121B"))

        is_selected = date == self.selectedDate()
        is_today = date == self._today
        in_month = date.month() == self.monthShown() and date.year() == self.yearShown()
        is_weekend = date.dayOfWeek() in (6, 7)

        pill = QRectF(rect.adjusted(3, 3, -3, -3))
        font = QFont(painter.font())
        font.setPointSize(10)

        if is_selected:
            grad = QLinearGradient(pill.topLeft(), pill.bottomRight())
            grad.setColorAt(0.0, QColor(COLORS["accent_coral"]))
            grad.setColorAt(1.0, QColor(COLORS["accent_peach"]))
            painter.setBrush(grad)
            painter.setPen(QPen(QColor(COLORS["accent_gold"]), 1.5) if is_today else Qt.NoPen)
            painter.drawRoundedRect(pill, 8.0, 8.0)
            text_color = QColor("#0D0E15")
            font.setBold(True)
        elif is_today:
            painter.setBrush(QColor("#15292E"))
            painter.setPen(QPen(QColor(COLORS["accent_aqua"]), 1.5))
            painter.drawRoundedRect(pill, 8.0, 8.0)
            text_color = QColor(COLORS["accent_aqua"])
            font.setBold(True)
        else:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(Qt.NoPen)
            if not in_month:
                text_color = QColor("#4E556B")
            elif is_weekend:
                text_color = QColor("#E2A496")
            else:
                text_color = QColor(COLORS["text_primary"])
            font.setBold(False)

        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(pill, Qt.AlignCenter, str(date.day()))

        if is_today:
            dot_color = QColor("#0D0E15") if is_selected else QColor(COLORS["accent_aqua"])
            painter.setBrush(dot_color)
            painter.setPen(Qt.NoPen)
            dot_rect = QRectF(pill.center().x() - 2.0, pill.bottom() - 5.5, 4.0, 4.0)
            painter.drawEllipse(dot_rect)

        painter.restore()


class ClockDiagnosticsWorker(QThread):
    """Collects vice-timesync --status, timedatectl, Chrony, and VBoxService status off UI thread."""
    report_ready = pyqtSignal(str)

    def __init__(self, timesync_bin: str):
        super().__init__()
        self._bin = timesync_bin
        self._stopped = False
        self._proc = None

    def stop(self) -> None:
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

    def _run(self, cmd: list) -> str:
        if self._stopped:
            return "[cancelled]"
        if not cmd or (not os.path.isfile(cmd[0]) and not shutil.which(cmd[0])):
            return f"[{cmd[0]} not found]"
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            try:
                stdout, stderr = self._proc.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.communicate()
                return "[timed out]"
            out = (stdout or "").strip() or (stderr or "").strip()
            return out or "(no output)"
        except Exception as exc:
            return f"Error: {exc}"
        finally:
            self._proc = None

    def run(self) -> None:
        sections = []
        if not self._stopped and (os.path.isfile(self._bin) or shutil.which(self._bin)):
            cmd = [self._bin, "--status"]
            if self._bin.endswith(".sh") and shutil.which("bash"):
                cmd = ["bash", self._bin, "--status"]
            sections.append("=== vice-timesync --status ===\n" + self._run(cmd))

        if not self._stopped and shutil.which("timedatectl"):
            sections.append("=== timedatectl ===\n" + self._run(["timedatectl"]))

        if not self._stopped and shutil.which("chronyc"):
            sections.append("=== Chrony Tracking (chronyc tracking) ===\n" + self._run(["chronyc", "tracking"]))
            if not self._stopped:
                sections.append("=== Chrony Sources (chronyc sources -v) ===\n" + self._run(["chronyc", "sources", "-v"]))

        if not self._stopped and shutil.which("systemctl"):
            units = ["chrony", "vboxservice", "virtualbox-guest-utils", "vice-timesync.timer"]
            lines = [f"{unit}: {self._run(['systemctl', 'is-active', unit])}" for unit in units if not self._stopped]
            sections.append("=== VirtualBox & Sync Services ===\n" + "\n".join(lines))

        if not self._stopped:
            self.report_ready.emit("\n\n".join(sections))


_CALENDAR_EXTRA_QSS = f"""
QFrame#WorldTile {{
    background-color: #10121B;
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
}}
QFrame#DateBanner {{
    background-color: #10121B;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}
QCalendarWidget#ViceCalendar {{
    background-color: #10121B;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}
QCalendarWidget#ViceCalendar QWidget#qt_calendar_navigationbar {{
    background-color: {COLORS['bg_surface']};
    border-bottom: 1px solid {COLORS['border']};
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 6px 8px;
}}
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_prevmonth,
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_nextmonth {{
    background-color: {COLORS['bg_elevated']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
    min-width: 28px;
    min-height: 28px;
}}
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_prevmonth:hover,
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_nextmonth:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['accent_coral']};
}}
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_monthbutton {{
    background-color: transparent;
    color: {COLORS['text_primary']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px 12px;
    font-size: 13px;
    font-weight: bold;
}}
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_monthbutton:hover {{
    background-color: {COLORS['bg_elevated']};
    border-color: {COLORS['border_strong']};
}}
QCalendarWidget#ViceCalendar QToolButton#qt_calendar_monthbutton::menu-indicator {{
    width: 0px;
}}
QCalendarWidget#ViceCalendar QSpinBox#qt_calendar_yearedit {{
    background-color: {COLORS['bg_elevated']};
    color: {COLORS['accent_peach']};
    border: 1px solid {COLORS['border']};
    border-radius: 7px;
    padding: 3px 8px;
    min-width: 62px;
    font-size: 13px;
    font-weight: bold;
}}
QCalendarWidget#ViceCalendar QTableView#qt_calendar_calendarview {{
    background-color: #10121B;
    alternate-background-color: {COLORS['bg_surface']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent_coral']};
    selection-color: #0D0E15;
    border: none;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
    outline: none;
}}
"""


class ViceClockSyncApp(QMainWindow):
    """Main window for Vice World Clock, Interactive Calendar & Host Time Sync."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice World Clock & Host Time Sync — Vice OS")
        self.resize(1040, 620)
        self.setMinimumSize(880, 540)
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
        self._update_calendar_banner()
        self._refresh_diagnostics()

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start()

    @staticmethod
    def _stat_localtime() -> tuple:
        try:
            mtime = os.lstat("/etc/localtime").st_mtime
        except OSError:
            mtime = 0.0
        try:
            target = os.path.realpath("/etc/localtime")
        except OSError:
            target = ""
        return (mtime, target)

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        root.setStyleSheet(_CALENDAR_EXTRA_QSS)
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        self._header = make_header(
            title="Vice World Clock & Host Time Sync",
            subtitle="Live local clock, interactive monthly calendar, IANA timezone sync, and Chrony/VBox diagnostics",
            icon_name="vice-tool-clock-sync",
            badge_text=_read_active_timezone(),
            badge_variant="aqua",
            parent=root,
        )
        self._sync_btn = make_button("Sync With Host && Internet Timezone", variant="primary", parent=self._header)
        self._sync_btn.clicked.connect(lambda: self._run_timesync(["--auto", "--force"], "Auto-syncing clock & timezone..."))
        self._header.right_layout.addWidget(self._sync_btn)
        layout.addWidget(self._header)

        # Main Two-Pane Split: Left (~58%) Clock + Tabs | Right (~42%) Always-Visible Calendar
        main_split = QHBoxLayout()
        main_split.setSpacing(12)

        # --- LEFT PANE (~58%) ---
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        clock_card = make_card(parent=root, margins=(14, 12, 14, 12), spacing=8)
        top_clock_row = QHBoxLayout()
        top_clock_row.setSpacing(10)

        clock_text_col = QVBoxLayout()
        clock_text_col.setSpacing(2)
        self._clock_lbl = QLabel("--:--:--", clock_card)
        self._clock_lbl.setObjectName("ClockDisplay")
        self._clock_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-family: {MONO_STACK}; font-size: 34px; font-weight: bold;"
        )
        clock_text_col.addWidget(self._clock_lbl)

        self._date_lbl = QLabel("Loading date...", clock_card)
        self._date_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self._date_lbl.setWordWrap(True)
        clock_text_col.addWidget(self._date_lbl)
        top_clock_row.addLayout(clock_text_col, 1)

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
        world_grid.setSpacing(8)
        for idx, (city, tz_name) in enumerate(WORLD_ZONES):
            tile = QFrame(clock_card)
            tile.setObjectName("WorldTile")
            tile_lay = QVBoxLayout(tile)
            tile_lay.setContentsMargins(10, 6, 10, 6)
            tile_lay.setSpacing(1)
            city_lbl = QLabel(city, tile)
            city_lbl.setObjectName("MutedLabel")
            city_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
            time_lbl = QLabel("--:--", tile)
            time_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 13px;")
            tile_lay.addWidget(city_lbl)
            tile_lay.addWidget(time_lbl)
            r, c = divmod(idx, 3)
            world_grid.addWidget(tile, r, c)
            self._world_labels.append((tz_name, time_lbl))
        clock_card.body_layout.addLayout(world_grid)
        left_col.addWidget(clock_card)

        # Tabbed IANA Selector & Diagnostics
        self._tabs = QTabWidget(root)

        tz_tab = QWidget(self._tabs)
        tz_lay = QVBoxLayout(tz_tab)
        tz_lay.setContentsMargins(12, 12, 12, 12)
        tz_lay.setSpacing(8)

        self._tz_search = QLineEdit(tz_tab)
        self._tz_search.setPlaceholderText("Search IANA timezone (e.g. America/New_York, Asia/Tokyo)...")
        self._tz_search.setClearButtonEnabled(True)
        self._tz_search.textChanged.connect(self._populate_tz_list)
        tz_lay.addWidget(self._tz_search)

        self._tz_list = QListWidget(tz_tab)
        self._tz_list.itemDoubleClicked.connect(lambda _it: self._apply_selected_tz())
        tz_lay.addWidget(self._tz_list, 1)

        self._apply_tz_btn = make_button("Set Selected Timezone", variant="primary", parent=tz_tab)
        self._apply_tz_btn.clicked.connect(self._apply_selected_tz)
        tz_lay.addWidget(self._apply_tz_btn)
        self._tabs.addTab(tz_tab, "IANA Timezone Selector")

        diag_tab = QWidget(self._tabs)
        diag_lay = QVBoxLayout(diag_tab)
        diag_lay.setContentsMargins(12, 12, 12, 12)
        diag_lay.setSpacing(8)

        self._diag_out = QPlainTextEdit(diag_tab)
        self._diag_out.setReadOnly(True)
        self._diag_out.setPlainText("Collecting timesync diagnostics...")
        diag_lay.addWidget(self._diag_out, 1)
        self._tabs.addTab(diag_tab, "Chrony && VirtualBox Diagnostics")

        left_col.addWidget(self._tabs, 1)

        self._status_lbl = QLabel("Ready.", root)
        self._status_lbl.setObjectName("MutedLabel")
        self._status_lbl.setWordWrap(True)
        left_col.addWidget(self._status_lbl)

        main_split.addLayout(left_col, 58)

        # --- RIGHT PANE (~42%): Always-Visible Leonida Interactive Calendar ---
        cal_card = make_card(parent=root, margins=(14, 12, 14, 12), spacing=10)
        cal_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cal_title_row = QHBoxLayout()
        cal_title_row.setSpacing(8)
        cal_title = QLabel("Interactive Calendar", cal_card)
        cal_title.setObjectName("SectionTitle")
        cal_title_row.addWidget(cal_title)
        cal_title_row.addStretch(1)
        self._cal_rel_badge = make_badge("TODAY", "aqua", cal_card)
        cal_title_row.addWidget(self._cal_rel_badge)
        cal_card.body_layout.addLayout(cal_title_row)

        # Hero Date Banner (Day, Date, Month, Year + ISO Week & Day of Year)
        banner = QFrame(cal_card)
        banner.setObjectName("DateBanner")
        banner_lay = QVBoxLayout(banner)
        banner_lay.setContentsMargins(12, 10, 12, 10)
        banner_lay.setSpacing(5)

        banner_top = QHBoxLayout()
        banner_top.setSpacing(8)
        self._cal_day_badge = make_badge("Monday", "coral", banner)
        banner_top.addWidget(self._cal_day_badge)
        self._cal_meta_lbl = QLabel("Week 1 · Day 1 of 365", banner)
        self._cal_meta_lbl.setObjectName("MutedLabel")
        banner_top.addWidget(self._cal_meta_lbl, 1)
        banner_lay.addLayout(banner_top)

        self._cal_date_big = QLabel("-- ---- ----", banner)
        self._cal_date_big.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: bold;"
        )
        banner_lay.addWidget(self._cal_date_big)
        cal_card.body_layout.addWidget(banner)

        # Interactive Monthly Calendar Grid
        self._calendar = ViceCalendarWidget(cal_card)
        self._calendar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._calendar.selectionChanged.connect(self._update_calendar_banner)
        self._calendar.currentPageChanged.connect(lambda _y, _m: self._calendar.updateCells())
        cal_card.body_layout.addWidget(self._calendar, 1)

        # Footer: Selected Day/Date/Month/Year summary + Jump to Today button
        cal_footer = QHBoxLayout()
        cal_footer.setSpacing(8)
        self._cal_footer_lbl = QLabel("Selected: --", cal_card)
        self._cal_footer_lbl.setObjectName("MutedLabel")
        self._cal_footer_lbl.setWordWrap(True)
        cal_footer.addWidget(self._cal_footer_lbl, 1)

        self._jump_today_btn = make_button("Jump to Today", variant="secondary", parent=cal_card)
        self._jump_today_btn.clicked.connect(self._jump_to_today)
        cal_footer.addWidget(self._jump_today_btn)
        cal_card.body_layout.addLayout(cal_footer)

        main_split.addWidget(cal_card, 42)
        layout.addLayout(main_split, 1)

    def _jump_to_today(self) -> None:
        now_local = datetime.now().astimezone()
        today_qd = QDate(now_local.year, now_local.month, now_local.day)
        self._calendar.set_today(today_qd)
        self._calendar.setSelectedDate(today_qd)
        self._calendar.setCurrentPage(today_qd.year(), today_qd.month())
        self._update_calendar_banner()

    def _update_calendar_banner(self) -> None:
        sel = self._calendar.selectedDate()
        sel_py = py_date(sel.year(), sel.month(), sel.day())
        today_qd = self._calendar.today_date()
        today_py = py_date(today_qd.year(), today_qd.month(), today_qd.day())

        day_name = sel_py.strftime("%A")
        full_dmy = sel_py.strftime("%d %B %Y")
        iso_week = sel_py.isocalendar()[1]
        day_of_year = sel_py.timetuple().tm_yday
        days_in_year = py_date(sel_py.year, 12, 31).timetuple().tm_yday

        style_badge(self._cal_day_badge, "coral")
        self._cal_day_badge.setText(day_name)
        self._cal_date_big.setText(full_dmy)
        self._cal_meta_lbl.setText(f"Week {iso_week} · Day {day_of_year} of {days_in_year}")

        delta = (sel_py - today_py).days
        if delta == 0:
            self._cal_rel_badge.setText("TODAY")
            style_badge(self._cal_rel_badge, "aqua")
        elif delta == 1:
            self._cal_rel_badge.setText("TOMORROW")
            style_badge(self._cal_rel_badge, "gold")
        elif delta == -1:
            self._cal_rel_badge.setText("YESTERDAY")
            style_badge(self._cal_rel_badge, "neutral")
        elif delta > 0:
            self._cal_rel_badge.setText(f"+{delta} DAYS")
            style_badge(self._cal_rel_badge, "gold")
        else:
            self._cal_rel_badge.setText(f"{abs(delta)}D AGO")
            style_badge(self._cal_rel_badge, "neutral")

        self._cal_footer_lbl.setText(f"Selected: {day_name}, {full_dmy}")

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

        today_qd = QDate(now_local.year, now_local.month, now_local.day)
        old_today = self._calendar.today_date()
        if today_qd != old_today:
            was_on_today = self._calendar.selectedDate() == old_today
            self._calendar.set_today(today_qd)
            if was_on_today:
                self._calendar.setSelectedDate(today_qd)
                self._calendar.setCurrentPage(today_qd.year(), today_qd.month())
            self._update_calendar_banner()

        for tz_name, lbl in self._world_labels:
            if ZoneInfo is not None:
                try:
                    dt = datetime.now(ZoneInfo(tz_name))
                    lbl.setText(dt.strftime("%H:%M (%a)"))
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
        self._sync_proc.errorOccurred.connect(self._on_timesync_error)
        self._sync_proc.start(prog, args)

    def _on_timesync_error(self, _err) -> None:
        self._sync_btn.setEnabled(True)
        self._sync_only_btn.setEnabled(True)
        self._apply_tz_btn.setEnabled(True)
        msg = self._sync_proc.errorString() if self._sync_proc is not None else "Process failed to start"
        self._status_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-weight: 600;")
        self._status_lbl.setText(f"Failed to start time sync: {msg}")

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
                self._diag_worker.wait(2500)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app, extra_qss=_CALENDAR_EXTRA_QSS)
    win = ViceClockSyncApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
