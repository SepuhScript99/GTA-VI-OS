#!/usr/bin/env python3
"""Vice OS Panel — top taskbar with app launcher, clock, system tray, quick actions."""

import sys
import os
import pwd
import shutil
import subprocess
from datetime import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSystemTrayIcon, QMenu, QAction, QFrame, QGraphicsDropShadowEffect,
    QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QProcess
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter

from python.vice_utils import log_info

PANEL_HEIGHT = 36
PANEL_WIDTH = 1920

STYLE = """
QWidget#panel {
    background-color: #0a0a0a;
    border-bottom: 1px solid #00ffff;
}
QPushButton#launcherBtn {
    background: transparent;
    color: #ff00ff;
    border: none;
    font-size: 16px;
    font-weight: bold;
    padding: 4px 12px;
}
QPushButton#launcherBtn:hover {
    background: #1a1a1a;
}
QPushButton#sysBtn {
    background: transparent;
    color: #00ffff;
    border: none;
    padding: 4px 8px;
    font-size: 12px;
}
QPushButton#sysBtn:hover {
    background: #1a1a1a;
}
QLabel#clockLabel {
    color: #00ffff;
    font-size: 12px;
    padding: 4px 10px;
}
QLabel#titleLabel {
    color: #ff00ff;
    font-size: 14px;
    font-weight: bold;
    padding: 4px 8px;
}
QMenu {
    background: #1a1a1a;
    color: #00ffff;
    border: 1px solid #00ffff;
    padding: 4px;
}
QMenu::item:selected {
    background: #00ffff;
    color: #0a0a0a;
}
QFrame#divider {
    background: #1a1a1a;
    max-width: 1px;
    min-width: 1px;
    margin: 6px 2px;
}
"""

DESKTOP_DIR = os.path.join(os.path.dirname(__file__))

WINDOW_BTN_STYLE = """
QPushButton {
    background: #1a1a1a; color: #aaffff; border: 1px solid #1a4a4a;
    padding: 2px 10px; max-width: 160px; min-width: 40px;
    font-size: 11px; text-align: left;
}
QPushButton:hover { border-color: #00ffff; color: #00ffff; }
QPushButton:checked { background: #003333; color: #00ffff; border-color: #00ffff; }
"""

SKIP_TITLES = {"vice panel", "desktop", "stalonetray", "nm-applet",
               "vice os — desktop widgets", "vice os — locked"}


class WindowList(QWidget):
    """Taskbar area listing open windows via wmctrl/xdotool (X11)."""

    def __init__(self):
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 0, 4, 0)
        self._layout.setSpacing(2)
        self._buttons = {}  # window id (int) -> button
        self._timer = QTimer()
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _get_windows(self):
        """Return list of (window_id_int, title) for visible client windows."""
        try:
            out = subprocess.check_output(["wmctrl", "-l"], text=True, timeout=2)
        except Exception:
            return []
        windows = []
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            wid_hex, _host, desk, title = parts[0], parts[1], parts[2], parts[3]
            if desk == "-1":  # dock/desktop layer windows
                continue
            if title.strip().lower() in SKIP_TITLES:
                continue
            try:
                windows.append((int(wid_hex, 16), title.strip()))
            except ValueError:
                continue
        return windows

    def _get_active(self):
        """Return active window id (int) via xdotool, or None."""
        try:
            out = subprocess.check_output(["xdotool", "getactivewindow"],
                                          text=True, timeout=2)
            return int(out.strip())
        except Exception:
            return None

    def _refresh(self):
        windows = self._get_windows()
        active = self._get_active()

        # Remove buttons for closed windows
        current_ids = {wid for wid, _ in windows}
        for wid in list(self._buttons.keys()):
            if wid not in current_ids:
                btn = self._buttons.pop(wid)
                btn.deleteLater()

        # Add/update buttons
        for wid, title in windows:
            btn = self._buttons.get(wid)
            if btn is None:
                btn = QPushButton()
                btn.setStyleSheet(WINDOW_BTN_STYLE)
                btn.setCheckable(True)
                btn.setFlat(False)
                btn.setToolTip(title)
                btn.clicked.connect(lambda _, w=wid: self._activate(w))
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda _pos, w=wid: self._close(w)
                )
                self._buttons[wid] = btn
                self._layout.addWidget(btn)
            label = title if len(title) <= 22 else title[:20] + "…"
            if btn.text() != label:
                btn.setText(label)
            btn.setChecked(wid == active)

    def _activate(self, wid):
        """Click behavior: focus window, or minimize if already active."""
        active = self._get_active()
        if wid == active:
            subprocess.Popen(["xdotool", "windowminimize", str(wid)])
        else:
            subprocess.Popen(["wmctrl", "-ia", hex(wid)])

    def _close(self, wid):
        subprocess.Popen(["wmctrl", "-ic", hex(wid)])


class ClockWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setObjectName("clockLabel")
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update)
        self._timer.start()
        self._update()

    def _update(self):
        now = datetime.now()
        self.setText(now.strftime("%a %b %d  %H:%M:%S"))


class QuickActionsMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addAction("🔊 Volume", self._volume)
        self.addAction("📶 Network", self._network)
        self.addAction("🔋 Battery", self._battery)
        self.addSeparator()
        self.addAction("📸 Screenshot", self._screenshot)
        self.addSeparator()
        self.addAction("⏻ Shutdown", self._shutdown)
        self.addAction("🔄 Reboot", self._reboot)
        self.addAction("😴 Suspend", self._suspend)
        self.addSeparator()
        self.addAction("🔒 Lock", self._lock)
        self.addAction("🚪 Logout", self._logout)

    def _volume(self): self._open("vice_audio_manager.py")
    def _network(self): self._open("vice_network_monitor.py")
    def _battery(self): self._open("vice_power_manager.py")
    def _screenshot(self): self._open("vice_screenshot.py")

    def _lock(self):
        locker = next((c for c in ("swaylock", "i3lock", "slock", "xdg-screensaver") if shutil.which(c)), None)
        if locker == "xdg-screensaver":
            subprocess.Popen(["xdg-screensaver", "lock"])
        elif locker:
            subprocess.Popen([locker])
        else:
            path = os.path.join(DESKTOP_DIR, "vice_session_manager.py")
            if os.path.exists(path):
                subprocess.Popen([sys.executable, path, "--lock"])

    def _logout(self):
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("labwc"):
            subprocess.Popen(["labwc", "--exit"])
        elif shutil.which("openbox"):
            subprocess.Popen(["openbox", "--exit"])
        else:
            user = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name
            subprocess.Popen(["pkill", "-u", user])
    def _shutdown(self): subprocess.Popen(["systemctl", "poweroff"])
    def _reboot(self): subprocess.Popen(["systemctl", "reboot"])
    def _suspend(self): subprocess.Popen(["systemctl", "suspend"])

    def _open(self, script):
        path = os.path.join(DESKTOP_DIR, script)
        if os.path.exists(path):
            subprocess.Popen([sys.executable, path])


class Panel(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("panel")
        self.setWindowTitle("Vice Panel")
        self.setFixedHeight(PANEL_HEIGHT)
        screen = QApplication.primaryScreen().geometry()
        self.setFixedWidth(screen.width())
        self.move(0, 0)
        self.setStyleSheet(STYLE)
        self._launcher_proc = None
        self._init_ui()

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 0, 4, 0)
        root.setSpacing(0)

        # Launcher button
        self._launcher_btn = QPushButton(" vice ")
        self._launcher_btn.setObjectName("launcherBtn")
        self._launcher_btn.setFixedHeight(PANEL_HEIGHT - 4)
        self._launcher_btn.clicked.connect(self._toggle_launcher)
        self._launcher_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self._launcher_btn.customContextMenuRequested.connect(self._show_session_menu)
        root.addWidget(self._launcher_btn)

        self._divider()
        root.addWidget(QLabel("  Vice OS  "))
        self._divider()

        # Open window list (taskbar)
        self._window_list = WindowList()
        root.addWidget(self._window_list, 1)

        # Quick action buttons
        for label, script in [
            ("💻", "vice_terminal.py"),
            ("📁", "vice_file_manager.py"),
            ("📝", "vice_text_editor.py"),
            ("⚙", "vice_settings.py"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("sysBtn")
            btn.setFixedHeight(PANEL_HEIGHT - 4)
            btn.clicked.connect(lambda _, s=script: self._launch_app(s))
            root.addWidget(btn)

        self._divider()

        # System tray
        self._tray_icon = QSystemTrayIcon()
        tray_menu = QMenu()
        tray_menu.addAction("Vice OS", lambda: self._launch_app("vice_launcher.py"))
        tray_menu.addSeparator()
        tray_menu.addAction("Settings", lambda: self._launch_app("vice_settings.py"))
        tray_menu.addAction("System Report", lambda: self._launch_app("vice_system_report.py"))
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", QApplication.quit)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.setIcon(QIcon.fromTheme("computer"))
        self._tray_icon.setToolTip("Vice OS")
        self._tray_icon.activated.connect(self._tray_activated)
        self._tray_icon.show()

        # Quick actions button
        self._qa_btn = QPushButton("⚡")
        self._qa_btn.setObjectName("sysBtn")
        self._qa_btn.setFixedHeight(PANEL_HEIGHT - 4)
        self._qa_menu = QuickActionsMenu()
        self._qa_btn.clicked.connect(self._qa_menu.exec_)
        root.addWidget(self._qa_btn)

        # Clock
        self._clock = ClockWidget()
        root.addWidget(self._clock)

    def _divider(self):
        d = QFrame()
        d.setObjectName("divider")
        d.setFrameShape(QFrame.VLine)
        d.setFrameShadow(QFrame.Sunken)
        root = self.layout()
        # safe add — won't crash if layout is None
        if root:
            root.addWidget(d)

    def _toggle_launcher(self):
        if self._launcher_proc and self._launcher_proc.state() == QProcess.Running:
            self._launcher_proc.terminate()
            self._launcher_proc = None
        else:
            path = os.path.join(DESKTOP_DIR, "vice_launcher.py")
            if os.path.exists(path):
                self._launcher_proc = QProcess(self)
                self._launcher_proc.start(sys.executable, [path])
                log_info("Launcher opened")

    def _launch_app(self, script):
        path = os.path.join(DESKTOP_DIR, script)
        if os.path.exists(path):
            QProcess.startDetached(sys.executable, [path])
            log_info(f"Launched: {script}")

    def _show_session_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Settings", lambda: self._launch_app("vice_settings.py"))
        menu.addAction("System Report", lambda: self._launch_app("vice_system_report.py"))
        menu.addAction("Task Manager", lambda: self._launch_app("vice_task_manager.py"))
        menu.addSeparator()
        menu.addAction("About Vice OS", self._about)
        menu.exec_(self._launcher_btn.mapToGlobal(pos))

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_launcher()

    def _about(self):
        QMessageBox.information(self, "About Vice OS",
            "Vice OS — A cyberpunk-themed Linux distribution\n"
            "Built with Python + PyQt5\n"
            "Based on Debian Bookworm")


def main():
    app = QApplication(sys.argv)
    # prevent panel from being killed by other windows
    app.setQuitOnLastWindowClosed(False)
    panel = Panel()
    panel.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
