#!/usr/bin/env python3
"""Vice OS Desktop Widgets — draggable widgets: clock, system stats, weather placeholder."""

import json
import os
import subprocess
import sys
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsDropShadowEffect, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error  # noqa: E402
import vice_theme as vt  # noqa: E402

WIDGET_WIDTH = 280
WIDGET_HEIGHT = 180
WEATHER_CFG_FILE = os.path.expanduser("~/.config/vice-os/weather_widget.json")

STYLE_FRAME = f"""
QFrame {{
    background: rgba(20, 22, 33, 232);
    border: 1px solid {vt.COLORS['border_strong']};
    border-radius: 8px;
}}
"""

WIDGET_STYLE = f"""
QLabel {{ color: {vt.COLORS['text_primary']}; background: transparent; border: none; }}
QLabel#title {{ color: {vt.COLORS['accent_coral']}; font-size: 12px; font-weight: bold; }}
QLabel#clock_time {{ font-size: 34px; font-weight: bold; color: {vt.COLORS['text_primary']}; }}
QLabel#clock_date {{ color: {vt.COLORS['text_secondary']}; font-size: 12px; }}
"""


class DragWidget(QFrame):
    def __init__(self, x=None, y=None):
        super().__init__()
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.setFrameShape(QFrame.Box)
        self.setStyleSheet(STYLE_FRAME + WIDGET_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(vt.COLORS["accent_coral"]))
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)

        if x is not None:
            self.move(x, y)
        self._drag_pos = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.close()


class ClockWidget(DragWidget):
    def __init__(self, x=None, y=None):
        super().__init__(x, y)
        self.setFixedSize(WIDGET_WIDTH, 140)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Clock")
        title.setObjectName("title")
        layout.addWidget(title)

        self._time_label = QLabel()
        self._time_label.setObjectName("clock_time")
        self._time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._time_label)

        self._date_label = QLabel()
        self._date_label.setObjectName("clock_date")
        self._date_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._date_label)

        layout.addStretch()

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update)
        self._timer.start()
        self._update()

    def _update(self):
        now = datetime.now()
        self._time_label.setText(now.strftime("%H:%M:%S"))
        self._date_label.setText(now.strftime("%A, %d %B %Y"))

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


class SystemStatsWidget(DragWidget):
    def __init__(self, x=None, y=None):
        super().__init__(x, y)
        self.setFixedSize(WIDGET_WIDTH, 200)
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("System Stats")
        title.setObjectName("title")
        layout.addWidget(title)

        self._content = QLabel("")
        self._content.setStyleSheet("font-size: 11px; line-height: 1.6;")
        self._content.setAlignment(Qt.AlignTop)
        layout.addWidget(self._content)

    def _refresh(self):
        lines = []
        # CPU
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            vals = list(map(int, line.split()[1:]))
            idle = vals[3]
            total = sum(vals)
            prev = getattr(self, "_prev_cpu", None)
            self._prev_cpu = (total, idle)
            if prev is None:
                lines.append("CPU: calculating...")
            else:
                pt, pi = prev
                dt, di = total - pt, idle - pi
                cpu = 0 if dt <= 0 else int((1 - di / dt) * 100)
                lines.append(f"CPU: {cpu}%")
        except Exception:
            lines.append("CPU: N/A")

        # Memory
        try:
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    k, v = line.split(":")
                    info[k.strip()] = int(v.split()[0])
            total = info.get("MemTotal", 1)
            avail = info.get("MemAvailable", 0)
            used = total - avail
            pct = int(used / total * 100)
            lines.append(f"RAM: {pct}%  ({used // 1024}/{total // 1024} MB)")
        except Exception:
            lines.append("RAM: N/A")

        # Disk
        try:
            out = subprocess.check_output(
                ["df", "-h", "--output=target,pcent"],
                text=True, timeout=2
            )
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[0] in ("/", "/home"):
                    lines.append(f"Disk {parts[0]}: {parts[1]}")
                    break
        except Exception:
            lines.append("Disk: N/A")

        # Uptime
        try:
            with open("/proc/uptime") as f:
                secs = float(f.read().split()[0])
            h, rem = divmod(int(secs), 3600)
            m, _ = divmod(rem, 60)
            lines.append(f"Uptime: {h}h {m}m")
        except Exception:
            lines.append("Uptime: N/A")

        self._content.setText("\n".join(lines))

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


class WeatherWidget(DragWidget):
    def __init__(self, x=None, y=None):
        super().__init__(x, y)
        self.setFixedSize(WIDGET_WIDTH, 160)
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Weather")
        title.setObjectName("title")
        layout.addWidget(title)

        self._temp_label = QLabel("--°C")
        self._temp_label.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {vt.COLORS['accent_aqua']}; border: none;"
        )
        self._temp_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._temp_label)

        self._desc_label = QLabel("Weather data unavailable\nConfigure API key or location")
        self._desc_label.setAlignment(Qt.AlignCenter)
        self._desc_label.setStyleSheet(f"font-size: 11px; color: {vt.COLORS['text_secondary']}; border: none;")
        layout.addWidget(self._desc_label)

        hint = QLabel("(Double-click to configure)")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"font-size: 10px; color: {vt.COLORS['text_muted']}; border: none;")
        layout.addWidget(hint)

    def _load_config(self):
        if os.path.isfile(WEATHER_CFG_FILE):
            try:
                with open(WEATHER_CFG_FILE, encoding="utf-8") as fp:
                    cfg = json.load(fp)
                city = cfg.get("city", "").strip()
                if city:
                    self._desc_label.setText(f"{city}\nOffline / pending weather sync")
            except Exception:
                pass

    def mouseDoubleClickEvent(self, e):
        dlg = WeatherConfigDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._load_config()


class WeatherConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Weather Widget Config")
        self.setFixedSize(360, 210)
        vt.apply_app_theme(self)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Weather Widget Configuration"))
        layout.addWidget(QLabel("API Key:"))
        self._api_edit = QLineEdit()
        self._api_edit.setPlaceholderText("OpenWeatherMap API key (optional)")
        layout.addWidget(self._api_edit)

        layout.addWidget(QLabel("City:"))
        self._city_edit = QLineEdit()
        self._city_edit.setPlaceholderText("e.g. London, UK")
        layout.addWidget(self._city_edit)

        if os.path.isfile(WEATHER_CFG_FILE):
            try:
                with open(WEATHER_CFG_FILE, encoding="utf-8") as fp:
                    cfg = json.load(fp)
                self._api_edit.setText(cfg.get("api_key", ""))
                self._city_edit.setText(cfg.get("city", ""))
            except Exception:
                pass

        ok_btn = vt.make_button("Save", variant="primary", parent=self)
        ok_btn.clicked.connect(self._save_and_accept)
        layout.addWidget(ok_btn)

    def _save_and_accept(self):
        try:
            os.makedirs(os.path.dirname(WEATHER_CFG_FILE), exist_ok=True)
            with open(WEATHER_CFG_FILE, "w", encoding="utf-8") as fp:
                json.dump({
                    "api_key": self._api_edit.text().strip(),
                    "city": self._city_edit.text().strip(),
                }, fp, indent=2)
        except Exception as e:
            log_error(f"Weather widget config save failed: {e}")
        self.accept()


class WidgetHost(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Desktop Widgets")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 60, screen.width(), screen.height() - 60)
        self.setStyleSheet("background: transparent;")
        self._init_ui()

    def _init_ui(self):
        x = self.width() - WIDGET_WIDTH - 20
        self._clock = ClockWidget(x, 70)
        self._clock.setParent(self)

        self._stats = SystemStatsWidget(x, 70 + 145)
        self._stats.setParent(self)

        self._weather = WeatherWidget(x - WIDGET_WIDTH - 10, 70)
        self._weather.setParent(self)

        info = QLabel("Double-click widgets to remove  |  Drag to reposition")
        info.setStyleSheet(
            f"background: rgba(13, 14, 21, 195); color: {vt.COLORS['text_muted']}; "
            "font-size: 10px; padding: 4px 8px; border-radius: 4px;"
        )
        info.setAttribute(Qt.WA_TransparentForMouseEvents)
        info.setParent(self)

    def closeEvent(self, event):
        for w in (self._clock, self._stats, self._weather):
            w.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    host = WidgetHost()
    host.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
