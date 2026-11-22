#!/usr/bin/env python3
"""Vice OS Session Manager — logout, lock screen, switch user, shutdown/reboot."""

import sys
import os
import pwd
import shutil
import subprocess
from datetime import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QDialog, QDesktopWidget, QLineEdit, QFormLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap

from python.vice_utils import log_info, log_error

SCREEN_W = 1920
SCREEN_H = 1080

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton {
    background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff;
    padding: 14px 20px; font-size: 13px;
}
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px; }
QLabel { color: #00ffff; }
"""


def run_cmd(cmd, sudo=False):
    full = (["sudo"] if sudo else []) + cmd
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


class SessionManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Session Manager")
        screen = QApplication.primaryScreen().geometry()
        self.setFixedSize(screen.width(), screen.height())
        self.setStyleSheet(STYLE)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        title = QLabel("Vice OS")
        title.setFont(QFont("monospace", 36, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ff00ff; margin-bottom: 20px;")
        root.addWidget(title)

        subtitle = QLabel("Session Manager")
        subtitle.setFont(QFont("monospace", 14))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #888; margin-bottom: 40px;")
        root.addWidget(subtitle)

        btn_grid = QHBoxLayout()
        btn_grid.setSpacing(20)
        btn_grid.setAlignment(Qt.AlignCenter)

        actions = [
            ("🔒", "Lock Screen",  self._lock,     "#00ffff"),
            ("🚪", "Logout",       self._logout,   "#ff8800"),
            ("👤", "Switch User",  self._switch,   "#00ff88"),
            ("😴", "Suspend",      self._suspend,  "#8888ff"),
            ("🔄", "Reboot",       self._reboot,   "#ffaa00"),
            ("⏻", "Shutdown",     self._shutdown, "#ff4444"),
        ]

        for icon, label, slot, color in actions:
            container = QVBoxLayout()
            container.setAlignment(Qt.AlignCenter)

            btn = QPushButton(icon)
            btn.setFixedSize(90, 90)
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 32px;
                    border: 2px solid {color};
                    border-radius: 45px;
                    background: #0d0d0d;
                    color: {color};
                }}
                QPushButton:hover {{
                    background: {color};
                    color: #0a0a0a;
                }}
            """)
            btn.clicked.connect(slot)
            container.addWidget(btn)

            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; margin-top: 4px;")
            container.addWidget(lbl)

            btn_grid.addLayout(container)

        root.addLayout(btn_grid)
        root.addStretch()

        # User info
        user = os.getenv("USER", os.getenv("LOGNAME", "user"))
        info_row = QHBoxLayout()
        info_row.setAlignment(Qt.AlignCenter)

        self._user_label = QLabel(f"Logged in as: {user}")
        self._user_label.setStyleSheet("color: #888; font-size: 12px;")
        info_row.addWidget(self._user_label)
        root.addLayout(info_row)

        # Back to desktop
        back_btn = QPushButton("← Back to Desktop")
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


class LockScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Locked")
        screen = QApplication.primaryScreen().geometry()
        self.setFixedSize(screen.width(), screen.height())
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background: #0a0a0a;")
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        lock_icon = QLabel("🔒")
        lock_icon.setStyleSheet("font-size: 64px;")
        lock_icon.setAlignment(Qt.AlignCenter)
        root.addWidget(lock_icon)

        time_label = QLabel()
        time_label.setStyleSheet("font-size: 48px; color: #00ffff; font-weight: bold;")
        time_label.setAlignment(Qt.AlignCenter)
        root.addWidget(time_label)

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(lambda: time_label.setText(datetime.now().strftime("%H:%M:%S")))
        self._timer.start()
        time_label.setText(datetime.now().strftime("%H:%M:%S"))

        root.addSpacing(40)

        hint = QLabel("Press Enter or click to unlock")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Escape, Qt.Key_Enter):
            self.close()

    def mousePressEvent(self, event):
        self.close()


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
