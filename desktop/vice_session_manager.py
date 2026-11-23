#!/usr/bin/env python3
"""Vice OS Session Manager — logout, lock screen, switch user, shutdown/reboot."""

from datetime import datetime
import os
import pwd
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    resolve_icon,
)


def _screen_geometry():
    screen = QApplication.primaryScreen()
    if screen is not None:
        return screen.geometry()
    return None


class SessionManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Session Manager")
        apply_app_theme(self)
        rect = _screen_geometry()
        if rect is not None:
            self.setFixedSize(rect.width(), rect.height())
        else:
            self.resize(1280, 720)
        self._lock_win = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        title = QLabel("VICE OS")
        title.setFont(QFont("Noto Sans", 34, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {COLORS['text_primary']}; letter-spacing: 6px; margin-bottom: 8px;")
        root.addWidget(title)

        subtitle = QLabel("Session Manager")
        subtitle.setFont(QFont("Noto Sans", 14))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {COLORS['accent_peach']}; margin-bottom: 36px;")
        root.addWidget(subtitle)

        btn_grid = QHBoxLayout()
        btn_grid.setSpacing(22)
        btn_grid.setAlignment(Qt.AlignCenter)

        actions = [
            ("system-lock-screen", "Lock", "Lock Screen", self._lock, COLORS["accent_aqua"]),
            ("system-log-out", "Exit", "Logout", self._logout, COLORS["accent_peach"]),
            ("system-switch-user", "User", "Switch User", self._switch, COLORS["success"]),
            ("system-suspend", "Sleep", "Suspend", self._suspend, COLORS["accent_gold"]),
            ("system-reboot", "Reboot", "Reboot", self._reboot, COLORS["warning"]),
            ("system-shutdown", "Power", "Shutdown", self._shutdown, COLORS["danger"]),
        ]

        for icon_name, short_txt, label, slot, color in actions:
            container = QVBoxLayout()
            container.setAlignment(Qt.AlignCenter)

            btn = QPushButton("")
            ic = resolve_icon(icon_name)
            if not ic.isNull():
                btn.setIcon(ic)
                btn.setIconSize(QSize(34, 34))
            else:
                btn.setText(short_txt)
            btn.setFixedSize(90, 90)
            btn.setStyleSheet(
                f"QPushButton {{ font-size: 13px; font-weight: 600; border: 2px solid {color}; "
                f"border-radius: 45px; background: {COLORS['bg_surface']}; color: {color}; }}"
                f"QPushButton:hover {{ background: {color}; color: {COLORS['bg_canvas']}; }}"
            )
            btn.clicked.connect(slot)
            container.addWidget(btn)

            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600; margin-top: 6px;")
            container.addWidget(lbl)

            btn_grid.addLayout(container)

        root.addLayout(btn_grid)
        root.addStretch()

        user = os.getenv("USER", os.getenv("LOGNAME", "user"))
        info_row = QHBoxLayout()
        info_row.setAlignment(Qt.AlignCenter)

        self._user_label = QLabel(f"Logged in as: {user}")
        self._user_label.setObjectName("MutedLabel")
        info_row.addWidget(self._user_label)
        root.addLayout(info_row)

        back_btn = make_button("Back to Desktop", variant="secondary", parent=self)
        back_btn.setFixedWidth(200)
        back_btn.clicked.connect(self.close)
        root.addWidget(back_btn, alignment=Qt.AlignCenter)
        root.addSpacing(30)

    def _lock(self):
        log_info("Lock screen requested")
        locker = next(
            (cmd for cmd in ("swaylock", "i3lock", "slock", "xdg-screensaver") if shutil.which(cmd)),
            None,
        )
        if locker == "xdg-screensaver":
            subprocess.Popen(["xdg-screensaver", "lock"])
        elif locker:
            subprocess.Popen([locker])
        else:
            self._lock_win = LockScreen()
            self._lock_win.showFullScreen()

    def _logout(self):
        if QMessageBox.question(
            self, "Logout",
            "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            log_info("Logout requested")
            user = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name
            if os.environ.get("WAYLAND_DISPLAY") and shutil.which("labwc"):
                subprocess.Popen(["labwc", "--exit"])
            elif shutil.which("openbox"):
                subprocess.Popen(["openbox", "--exit"])
            elif shutil.which("loginctl"):
                subprocess.Popen(["loginctl", "terminate-user", user])
            else:
                subprocess.Popen(["pkill", "-u", user])

    def _switch(self):
        log_info("Switch user requested")
        if shutil.which("dm-tool"):
            subprocess.Popen(["dm-tool", "switch-to-greeter"])
        else:
            self._logout()

    def _suspend(self):
        log_info("Suspend requested")
        subprocess.Popen(["systemctl", "suspend"])

    def _reboot(self):
        if QMessageBox.question(
            self, "Reboot",
            "Are you sure you want to reboot?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            log_info("Reboot requested")
            subprocess.Popen(["systemctl", "reboot"])

    def _shutdown(self):
        if QMessageBox.question(
            self, "Shutdown",
            "Are you sure you want to shutdown?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            log_info("Shutdown requested")
            subprocess.Popen(["systemctl", "poweroff"])

    def closeEvent(self, event):
        if self._lock_win is not None:
            self._lock_win.close()
        event.accept()


class LockScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Locked")
        rect = _screen_geometry()
        if rect is not None:
            self.setFixedSize(rect.width(), rect.height())
        else:
            self.resize(1280, 720)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(f"background: {COLORS['bg_canvas']};")
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        lock_lbl = QLabel("LOCKED")
        lock_lbl.setStyleSheet(
            f"font-size: 16px; letter-spacing: 5px; font-weight: bold; color: {COLORS['accent_coral']};"
        )
        lock_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(lock_lbl)

        time_label = QLabel()
        time_label.setStyleSheet(
            f"font-size: 52px; color: {COLORS['text_primary']}; font-weight: bold;"
        )
        time_label.setAlignment(Qt.AlignCenter)
        root.addWidget(time_label)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(lambda: time_label.setText(datetime.now().strftime("%H:%M:%S")))
        self._timer.start()
        time_label.setText(datetime.now().strftime("%H:%M:%S"))

        root.addSpacing(40)

        hint = QLabel("Press Enter or click to unlock")
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Escape, Qt.Key_Enter):
            self.close()

    def mousePressEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self._timer.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    if "--lock" in sys.argv:
        win = LockScreen()
        win.showFullScreen()
    else:
        win = SessionManager()
        win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
