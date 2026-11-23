#!/usr/bin/env python3
"""Vice OS — Calendar & Clock. Month view with events, digital clock, world clocks."""

import calendar as cal
import datetime
import json
import os
import sys
import zoneinfo

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QTextEdit, QLineEdit, QDialog, QFormLayout, QDialogButtonBox,
    QComboBox, QTimeEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    MONO_STACK,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 650

EVENTS_FILE = os.path.expanduser("~/.local/share/vice-os/calendar_events.json")

WORLD_CLOCKS = [
    "UTC", "America/New_York", "America/Los_Angeles", "Europe/London",
    "Europe/Berlin", "Europe/Moscow", "Asia/Tokyo", "Asia/Shanghai",
    "Asia/Kolkata", "Australia/Sydney",
]


def load_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_events(events):
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
    try:
        with open(EVENTS_FILE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(events, f, indent=2)
    except Exception as e:
        log_error(f"Event save failed: {e}")


class EventDialog(QDialog):
    def __init__(self, date_str="", title="", time_str="09:00", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Event")
        self.setFixedSize(420, 240)
        apply_app_theme(self)
        layout = QFormLayout(self)

        self._title = QLineEdit(title)
        self._title.setPlaceholderText("Event title")
        layout.addRow("Title:", self._title)

        self._date = QLineEdit(date_str)
        layout.addRow("Date (YYYY-MM-DD):", self._date)

        self._time = QTimeEdit()
        try:
            h, m = time_str.split(":")
            self._time.setTime(datetime.time(int(h), int(m)))
        except Exception:
            pass
        layout.addRow("Time:", self._time)

        self._recur = QComboBox()
        self._recur.addItems(["none", "daily", "weekly", "monthly", "yearly"])
        layout.addRow("Repeat:", self._recur)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def values(self):
        return {
            "title": self._title.text().strip(),
            "date": self._date.text().strip(),
            "time": self._time.time().toString("HH:mm"),
            "recur": self._recur.currentText(),
        }


class CalendarTab(QWidget):
    def __init__(self):
        super().__init__()
        self._year = datetime.date.today().year
        self._month = datetime.date.today().month
        self._events = load_events()
        self._init_ui()
        self._render()

    def _init_ui(self):
        root = QVBoxLayout(self)

        nav_row = QHBoxLayout()
        prev_btn = make_button("<", variant="secondary", parent=self)
        prev_btn.setFixedWidth(40)
        prev_btn.clicked.connect(self._prev_month)
        nav_row.addWidget(prev_btn)

        self._month_label = QLabel()
        self._month_label.setAlignment(Qt.AlignCenter)
        self._month_label.setFont(QFont("Noto Sans", 14, QFont.Bold))
        self._month_label.setStyleSheet(f"color: {COLORS['accent_peach']};")
        nav_row.addWidget(self._month_label, 1)

        next_btn = make_button(">", variant="secondary", parent=self)
        next_btn.setFixedWidth(40)
        next_btn.clicked.connect(self._next_month)
        nav_row.addWidget(next_btn)

        today_btn = make_button("Today", variant="secondary", parent=self)
        today_btn.clicked.connect(self._go_today)
        nav_row.addWidget(today_btn)

        add_btn = make_button("+ Add Event", variant="primary", parent=self)
        add_btn.clicked.connect(self._add_event)
        nav_row.addWidget(add_btn)
        root.addLayout(nav_row)

        self._table = QTableWidget()
        self._table.setRowCount(6)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        self._table.verticalHeader().setVisible(False)
        for i in range(7):
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        for r in range(6):
            self._table.setRowHeight(r, 72)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.cellDoubleClicked.connect(self._day_double_clicked)
        root.addWidget(self._table)

        self._events_view = QTextEdit()
        self._events_view.setReadOnly(True)
        self._events_view.setMaximumHeight(110)
        root.addWidget(self._events_view)

    def _prev_month(self):
        self._month -= 1
        if self._month < 1:
            self._month = 12
            self._year -= 1
        self._render()

    def _next_month(self):
        self._month += 1
        if self._month > 12:
            self._month = 1
            self._year += 1
        self._render()

    def _go_today(self):
        today = datetime.date.today()
        self._year = today.year
        self._month = today.month
        self._render()

    def _events_for(self, date_str):
        result = []
        for ev in self._events:
            if ev["date"] == date_str:
                result.append(ev)
        return result

    def _render(self):
        self._month_label.setText(f"{cal.month_name[self._month]} {self._year}")
        self._table.clearContents()

        month_cal = cal.Calendar(firstweekday=0)
        today = datetime.date.today()
        weeks = month_cal.monthdayscalendar(self._year, self._month)

        for week_idx, week in enumerate(weeks):
            for day_idx, day in enumerate(week):
                item = QTableWidgetItem()
                if day:
                    date_str = f"{self._year}-{self._month:02d}-{day:02d}"
                    day_events = self._events_for(date_str)
                    text = str(day)
                    if day_events:
                        text += "\n" + "\n".join("• " + e["title"][:10] for e in day_events[:2])
                    item.setText(text)
                    if day == today.day and self._month == today.month and self._year == today.year:
                        item.setBackground(QBrush(QColor(COLORS["bg_active"])))
                        item.setForeground(QBrush(QColor(COLORS["accent_aqua"])))
                    elif day_events:
                        item.setForeground(QBrush(QColor(COLORS["accent_coral"])))
                    elif day_idx >= 5:
                        item.setForeground(QBrush(QColor(COLORS["text_muted"])))
                self._table.setItem(week_idx, day_idx, item)

        # Show this month's events
        lines = []
        for ev in sorted(self._events, key=lambda e: (e["date"], e["time"])):
            if ev["date"].startswith(f"{self._year}-{self._month:02d}"):
                lines.append(f"{ev['date']} {ev['time']}  —  {ev['title']}  (repeat: {ev['recur']})")
        self._events_view.setPlainText("\n".join(lines) if lines else "No events this month")

    def _add_event(self):
        today = datetime.date.today()
        date_str = today.isoformat() if (self._year == today.year and self._month == today.month) else f"{self._year}-{self._month:02d}-01"
        dlg = EventDialog(date_str=date_str, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            ev = dlg.values()
            if ev["title"] and ev["date"]:
                self._events.append(ev)
                save_events(self._events)
                self._render()

    def _day_double_clicked(self, row, col):
        item = self._table.item(row, col)
        if not item or not item.text():
            return
        day = int(item.text().split("\n")[0])
        date_str = f"{self._year}-{self._month:02d}-{day:02d}"
        dlg = EventDialog(date_str=date_str, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            ev = dlg.values()
            if ev["title"] and ev["date"]:
                self._events.append(ev)
                save_events(self._events)
                self._render()


class WorldClockTab(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def _init_ui(self):
        root = QVBoxLayout(self)

        self._big_clock = QLabel()
        self._big_clock.setAlignment(Qt.AlignCenter)
        self._big_clock.setStyleSheet(
            f"font-family: {MONO_STACK}; font-size: 44px; font-weight: bold; "
            f"color: {COLORS['accent_aqua']}; margin: 10px;"
        )
        root.addWidget(self._big_clock)

        self._date_label = QLabel()
        self._date_label.setAlignment(Qt.AlignCenter)
        self._date_label.setFont(QFont("Noto Sans", 14))
        self._date_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        root.addWidget(self._date_label)

        root.addSpacing(10)
        root.addWidget(QLabel("World Clocks:"))

        self._zone_labels = {}
        grid = QGridLayout()
        for i, tz in enumerate(WORLD_CLOCKS):
            row, col = divmod(i, 2)
            box = QHBoxLayout()
            name = QLabel(tz)
            name.setFixedWidth(200)
            name.setStyleSheet(f"color: {COLORS['text_secondary']};")
            time_lbl = QLabel("--:--:--")
            time_lbl.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
            box.addWidget(name)
            box.addWidget(time_lbl)
            self._zone_labels[tz] = time_lbl
            wrapper = QWidget()
            wrapper.setLayout(box)
            grid.addWidget(wrapper, row, col)
        root.addLayout(grid)
        root.addStretch()

    def _tick(self):
        now = datetime.datetime.now()
        self._big_clock.setText(now.strftime("%H:%M:%S"))
        self._date_label.setText(now.strftime("%A, %d %B %Y"))

        for tz, label in self._zone_labels.items():
            try:
                zone_time = now.astimezone(zoneinfo.ZoneInfo(tz))
                label.setText(zone_time.strftime("%H:%M:%S"))
            except Exception:
                label.setText("N/A")

    def stop_timer(self):
        self._timer.stop()

    def closeEvent(self, event):
        self.stop_timer()
        event.accept()


class CalendarApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Calendar & Clock")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 520)
        apply_app_theme(self)
        self._clock_tab = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)
        header = make_header(
            title="Calendar & World Clock",
            subtitle="Monthly planner with recurring events and world timezones",
            icon_name="x-office-calendar",
            badge_text="CALENDAR",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(CalendarTab(), "Calendar")
        self._clock_tab = WorldClockTab()
        tabs.addTab(self._clock_tab, "Clock")
        root.addWidget(tabs, 1)

    def closeEvent(self, event):
        if self._clock_tab is not None:
            self._clock_tab.stop_timer()
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = CalendarApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
