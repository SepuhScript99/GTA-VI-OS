#!/usr/bin/env python3
"""Vice OS Desktop Widgets — draggable widgets: clock, system stats, weather placeholder."""

import sys
import os
import subprocess
from datetime import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QGraphicsDropShadowEffect, QDialog, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF, QMimeData, QDataStream, QByteArray
from PyQt5.QtGui import QFont, QColor, QPainter, QPolygon

from python.vice_utils import log_info

WIDGET_WIDTH = 280
WIDGET_HEIGHT = 180

STYLE_FRAME = """
QFrame {
    background: rgba(10, 10, 10, 220);
    border: 1px solid #00ffff;
    border-radius: 8px;
}
"""

WIDGET_STYLE = """
QLabel { color: #00ffff; background: transparent; }
QLabel#title { color: #ff00ff; font-size: 12px; font-weight: bold; }
QLabel#clock_time { font-size: 36px; font-weight: bold; color: #00ffff; }
QLabel#clock_date { color: #888; font-size: 12px; }
"""


class DragWidget(QFrame):
    def __init__(self, x=None, y=None):
        super().__init__()
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.setFrameShape(QFrame.Box)
        self.setStyleSheet(STYLE_FRAME)
        shadow = QGraphicsDropShadowEffect(blurRadius=15, color=QColor("#ff00ff"), offset=QPointF(3, 3))
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

        self._timer = QTimer()
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update)
        self._timer.start()
        self._update()

    def _update(self):
        now = datetime.now()
        self._time_label.setText(now.strftime("%H:%M:%S"))
        self._date_label.setText(now.strftime("%A, %d %B %Y"))


class SystemStatsWidget(DragWidget):
    def __init__(self, x=None, y=None):
        super().__init__(x, y)
        self.setFixedSize(WIDGET_WIDTH, 200)
        self._init_ui()
        self._timer = QTimer()
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
            lines.append(f"RAM: {pct}%  ({used//1024}/{total//1024} MB)")
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


class WeatherWidget(DragWidget):
    def __init__(self, x=None, y=None):
        super().__init__(x, y)
        self.setFixedSize(WIDGET_WIDTH, 160)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Weather")
        title.setObjectName("title")
        layout.addWidget(title)

        self._temp_label = QLabel("--°C")
        self._temp_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #00ffff;")
        self._temp_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._temp_label)

        self._desc_label = QLabel("Weather data unavailable\nConfigure API key or location")
        self._desc_label.setAlignment(Qt.AlignCenter)
        self._desc_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self._desc_label)

        hint = QLabel("(Double-click to configure)")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 10px; color: #555;")
        layout.addWidget(hint)

    def mouseDoubleClickEvent(self, e):
        dlg = WeatherConfigDialog(self)
        dlg.exec_()


class WeatherConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Weather Widget Config")
        self.setFixedSize(360, 200)
        self.setStyleSheet("background: #0a0a0a; color: #00ffff; font-family: 'Noto Sans Mono CJK JP', 'Noto Sans CJK JP', 'Noto Sans CJK SC', monospace;")
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

        ok_btn = QPushButton("Save")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)


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

        info = QLabel("Double-click widgets to remove  •  Drag to reposition")
        info.setStyleSheet("background: rgba(10,10,10,180); color: #444; font-size: 10px; padding: 4px;")
        info.setAttribute(Qt.WA_TransparentForMouseEvents)
        info.setParent(self)


def main():
    app = QApplication(sys.argv)
    host = WidgetHost()
    host.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()