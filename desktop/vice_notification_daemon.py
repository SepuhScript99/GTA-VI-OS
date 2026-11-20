#!/usr/bin/env python3
"""
Vice OS — Notification Daemon
Implements the org.freedesktop.Notifications D-Bus standard interface.
Displays cyberpunk-themed notification popups and records history
(compatible with vice_notif_history.py JSON store).
"""

import sys
import os
import json
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from python.vice_utils import log_info, log_error

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/notification_history.json")
MAX_HISTORY = 200
MAX_VISIBLE = 4

NOTIF_STYLE = """
QWidget {
    background-color: rgba(10, 10, 10, 235);
    border: 1px solid #00ffff;
    border-radius: 6px;
}
QLabel#summary {
    color: #00ffff;
    font-family: monospace;
    font-size: 13px;
    font-weight: bold;
}
QLabel#body {
    color: #aaffff;
    font-family: monospace;
    font-size: 11px;
}
QLabel#urgency {
    color: #ff00ff;
    font-family: monospace;
    font-size: 9px;
}
"""


def append_history(summary, body, urgency="normal", app=""):
    entries = []
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                entries = json.load(f)
        except Exception:
            entries = []
    entries.append({
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "body": body,
        "urgency": urgency,
        "app": app,
        "dismissed": False,
    })
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(entries[-MAX_HISTORY:], f, indent=2)
    except Exception as e:
        log_error(f"History save failed: {e}")


class NotificationPopup(QWidget):
    """Single cyberpunk-styled notification popup."""

    def __init__(self, summary, body, urgency="normal", timeout=5000, app_name=""):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(NOTIF_STYLE)
        self.setFixedSize(360, 96)
        self._urgency = urgency

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        urgency_colors = {"critical": "#ff4444", "normal": "#00ffff", "low": "#888888"}
        uc = urgency_colors.get(urgency, "#00ffff")

        app_label = QLabel(f"[ {app_name or 'Vice OS'} ]")
        app_label.setObjectName("urgency")
        app_label.setStyleSheet(f"color: {uc}; background: transparent;")
        text_layout.addWidget(app_label)

        sum_label = QLabel(summary or "Notification")
        sum_label.setObjectName("summary")
        sum_label.setStyleSheet(f"color: {uc}; background: transparent;")
        sum_label.setWordWrap(True)
        text_layout.addWidget(sum_label)

        if body:
            body_label = QLabel(body)
            body_label.setObjectName("body")
            body_label.setStyleSheet("background: transparent;")
            body_label.setWordWrap(True)
            text_layout.addWidget(body_label)

        layout.addLayout(text_layout, 1)

        screen = QApplication.primaryScreen().geometry()
        self._target_x = screen.width() - self.width() - 20
        self._slot_y = 60  # below the panel

        self.move(self._target_x, self._slot_y)
        self.show()

        if timeout > 0:
            QTimer.singleShot(timeout, self.close)


class ViceNotificationDaemon(dbus.service.Object):
    def __init__(self, bus, qt_app):
        self._bus = bus
        self._app = qt_app
        self._id_counter = 0
        self._active = {}  # id -> popup widget
        self._slot_height = 104

        bus_name = dbus.service.BusName("org.freedesktop.Notifications", bus=bus)
        super().__init__(bus_name, "/org/freedesktop/Notifications")

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="susssasa{sv}i", out_signature="u",
                         sender_keyword="sender")
    def Notify(self, app_name, replaces_id, app_icon, summary,
               body, actions, hints, expire_timeout, sender=None):
        self._id_counter += 1
        nid = self._id_counter

        urgency = "normal"
        try:
            u = hints.get("urgency")
            if u is not None:
                u = int(u)
                urgency = "low" if u == 0 else "normal" if u == 1 else "critical"
        except Exception:
            pass

        # Critical notifications persist until dismissed
        timeout = expire_timeout if expire_timeout > 0 else 5000
        if urgency == "critical":
            timeout = 0

        summary_str = str(summary)
        body_str = str(body)

        log_info(f"Notify [{urgency}] {summary_str}")
        append_history(summary_str, body_str, urgency, str(app_name))

        popup = NotificationPopup(summary_str, body_str, urgency, timeout, str(app_name))
        self._reposition()
        if timeout > 0:
            QTimer.singleShot(timeout + 50, lambda: self._cleanup_popup(nid))

        return dbus.UInt32(nid)

    def _cleanup_popup(self, nid):
        popup = self._active.pop(nid, None)
        if popup:
            popup.close()
            self._reposition()

    def _reposition(self):
        """Stack active popups from top to bottom on the right edge."""
        screen = QApplication.primaryScreen().geometry()
        y = 60
        for popup in self._active.values():
            if popup.isVisible():
                popup.move(screen.width() - popup.width() - 20, y)
                y += popup.height() + 8

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="as")
    def GetCapabilities(self):
        return dbus.Array(["actions", "body", "body-markup", "icon-static",
                           "urgency"], signature="s")

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="", out_signature="ssss")
    def GetServerInformation(self):
        return ("Vice OS Notifications", "Vice OS Project", "1.0", "1.2")

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature="u", out_signature="")
    def CloseNotification(self, nid):
        self._cleanup_popup(int(nid))


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    try:
        session_bus = dbus.SessionBus()
    except Exception as e:
        log_error(f"Cannot connect to session bus: {e}")
        print(f"Error: no D-Bus session available: {e}", file=sys.stderr)
        sys.exit(1)

    # Verify we can claim the name (fails if another daemon owns it)
    try:
        proxy = session_bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
        iface = dbus.Interface(proxy, "org.freedesktop.DBus")
        owner = iface.GetNameOwner("org.freedesktop.Notifications")
        log_error(f"Notification name owned by {owner}; another daemon is running")
        print("Error: another notification daemon already running", file=sys.stderr)
        sys.exit(1)
    except dbus.exceptions.DBusException:
        pass  # name unowned — we can take it

    daemon = ViceNotificationDaemon(session_bus, qt_app)
    log_info("Vice notification daemon started on org.freedesktop.Notifications")
    print("Vice OS notification daemon running (org.freedesktop.Notifications)")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()