#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Desktop Shell
Provides a dynamic TopBar (with CPU/RAM/Disk), Dock, Application Search Menu,
power management controls, system tray integration, and wallpaper management.
Uses lib.python.vice_utils for system metrics and command execution.
Includes global exception handling and automatic crash recovery.
"""

import sys
import os
import time
import traceback
import argparse
import shlex
import shutil

sys.path.insert(0, '/opt/vice-os/lib')
sys.path.insert(0, '/opt/vice-os')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QLineEdit, QShortcut
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence

from python.vice_utils import launch_command, get_cpu_usage, get_ram_usage, log_info, log_error

STYLE_FILE = "/opt/vice-os/style.qss"

_TRAY_MODULE = None
_POWER_MODULE = None
_WALL_MODULE = None
_PANEL_CONF = None


def _pc():
    """Return panel_config module, or a fallback with sensible defaults."""
    if _PANEL_CONF is not None:
        return _PANEL_CONF
    class _Fallback:
        TOPBAR_HEIGHT = 30
        DOCK_HEIGHT = 70
        DOCK_WIDTH = 400
        RUNMENU_WIDTH = 400
        RUNMENU_HEIGHT = 50
        RUNMENU_X_FRACTION = 2
        RUNMENU_Y_FRACTION = 3
        TOPBAR_UPDATE_INTERVAL = 2000
        DOCK_APPS = [
            ("Terminal", "xterm"),
            ("Browser", "firefox"),
            ("Files", "thunar"),
            ("Editor", "geany"),
        ]
    return _Fallback


def _load_helper_modules():
    global _TRAY_MODULE, _POWER_MODULE, _WALL_MODULE, _PANEL_CONF
    try:
        import systray_manager as _tm
        _TRAY_MODULE = _tm
    except (ImportError, Exception):
        _TRAY_MODULE = None
    try:
        import power_manager as _pm
        _POWER_MODULE = _pm
    except (ImportError, Exception):
        _POWER_MODULE = None
    try:
        import wallpaper_manager as _wm
        _WALL_MODULE = _wm
    except (ImportError, Exception):
        _WALL_MODULE = None
    try:
        import panel_config as _pc
        _PANEL_CONF = _pc
    except (ImportError, Exception):
        _PANEL_CONF = None


def global_exception_handler(exc_type, exc_value, exc_tb):
    log_error(f"Unhandled exception: {exc_type.__name__}: {exc_value}")
    for line in traceback.format_tb(exc_tb):
        log_error(f"  {line.strip()}")
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    log_error("Desktop shell encountered a fatal error. Attempting auto-restart...")
    launch_command("python3 /opt/vice-os/vice_shell.py &")


class RunMenu(QWidget):
    """Quick search/run menu triggered by W-space."""
    def __init__(self):
        super().__init__()
        self._focus_timer = None
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Run Command")
        self.setObjectName("RunMenu")

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display RunMenu.")
            sys.exit(1)

        geo = screen.geometry()
        pc = _pc()
        menu_w = pc.RUNMENU_WIDTH
        menu_h = pc.RUNMENU_HEIGHT
        self.setGeometry(
            geo.width() // pc.RUNMENU_X_FRACTION - menu_w // 2,
            geo.height() // pc.RUNMENU_Y_FRACTION,
            menu_w, menu_h
        )

        layout = QVBoxLayout()
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Type command and press Enter...")
        self.input_field.returnPressed.connect(self.run_command)
        self.input_field.textChanged.connect(self.clear_error)

        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.close)

        layout.addWidget(self.input_field)
        self.setLayout(layout)

    def clear_error(self):
        self.input_field.setStyleSheet("")

    def run_command(self):
        cmd_str = self.input_field.text().strip()
        if not cmd_str:
            self.close()
            return

        if launch_command(cmd_str):
            self.input_field.clear()
            self.close()
        else:
            self.show_error(f"Command not found: {shlex.split(cmd_str)[0]}")

    def show_error(self, message: str):
        self.input_field.setStyleSheet("border: 2px solid #FF0000; color: #FF0000;")
        self.input_field.setText(message)

    def focusOutEvent(self, event):
        if self._focus_timer is not None and self._focus_timer.isActive():
            self._focus_timer.stop()
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.timeout.connect(self.check_focus)
        self._focus_timer.start(150)

    def check_focus(self):
        if self._focus_timer is not None:
            self._focus_timer.stop()
            self._focus_timer = None
        if not self.isActiveWindow():
            self.close()


class Dock(QWidget):
    """Application dock at the bottom of the screen."""
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("Dock")

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display Dock.")
            sys.exit(1)

        geo = screen.availableGeometry()
        pc = _pc()
        dock_width = pc.DOCK_WIDTH
        dock_height = pc.DOCK_HEIGHT
        x = (geo.width() - dock_width) // 2
        y = geo.height() - dock_height
        self.setGeometry(x, y, dock_width, dock_height)

        layout = QHBoxLayout()

        for app in pc.DOCK_APPS:
            name, cmd = app[0], app[1]
            if shutil.which(shlex.split(cmd)[0]):
                btn = QPushButton(name, self)
                btn.setObjectName("DockButton")
                btn.setFocusPolicy(Qt.NoFocus)
                btn.clicked.connect(lambda state, c=cmd: launch_command(c))
                layout.addWidget(btn)

        self.setLayout(layout)


class TopBar(QWidget):
    """System bar at the top of the screen with system info, clock, and controls."""
    def __init__(self):
        super().__init__()
        self._disk_label = None
        self._power_widgets = []
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("TopBar")

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display TopBar.")
            sys.exit(1)

        geo = screen.availableGeometry()
        pc = _pc()
        self.setGeometry(0, 0, geo.width(), pc.TOPBAR_HEIGHT)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)

        self.sysinfo = QLabel("CPU: 0% | RAM: 0MB", self)
        self.sysinfo.setObjectName("SysInfo")

        self.clock = QLabel("00:00:00", self)
        self.clock.setObjectName("Clock")

        if _POWER_MODULE is not None:
            try:
                self._power_widgets = _POWER_MODULE.create_topbar_widgets(self)
                for w in self._power_widgets:
                    layout.addWidget(w)
            except Exception as e:
                log_error(f"Failed to load power widgets: {e}")

        layout.addWidget(self.sysinfo)
        layout.addStretch()
        layout.addWidget(self.clock)

        self.logout_btn = QPushButton("Exit", self)
        self.logout_btn.setObjectName("ExitButton")
        self.logout_btn.setFocusPolicy(Qt.NoFocus)
        self.logout_btn.clicked.connect(self.logout)
        layout.addWidget(self.logout_btn)

        self.setLayout(layout)

        timer = QTimer(self)
        timer.timeout.connect(self.update_info)
        timer.start(_pc().TOPBAR_UPDATE_INTERVAL)
        self.update_info()

    def update_info(self):
        self.clock.setText(time.strftime("%b %d, %H:%M:%S"))
        try:
            cpu_text = get_cpu_usage()
            ram_text = get_ram_usage()
            parts = [f"{cpu_text} | {ram_text}"]
            if self._disk_label is None:
                self._init_disk_label()
            if self._disk_label is not None:
                parts.append(self._disk_label)
            self.sysinfo.setText(" | ".join(parts))
        except Exception as e:
            log_error(f"Failed to update system info: {e}")
            self.sysinfo.setText("System info error")

    def _init_disk_label(self):
        try:
            self._disk_text = QLabel("", self)
            self._disk_text.setObjectName("SysInfo")
            self._disk_label = ""
            self._update_disk_usage()
        except Exception as e:
            log_error(f"Failed to initialize disk label: {e}")

    def _update_disk_usage(self):
        import subprocess
        try:
            result = subprocess.run(
                ["df", "-h", "--output=pcent", "/"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                if len(lines) >= 2:
                    pct = lines[1].strip()
                    self._disk_label = f"Disk: {pct}"
        except Exception as e:
            log_error(f"Disk usage update failed: {e}")
            self._disk_label = ""

    def logout(self):
        if _POWER_MODULE is not None:
            try:
                _POWER_MODULE.logout_session()
                return
            except Exception as e:
                log_error(f"Power module logout failed: {e}")
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            launch_command("labwc --exit")
        else:
            launch_command("openbox --exit")


def load_stylesheet(app: QApplication):
    if os.path.exists(STYLE_FILE):
        try:
            with open(STYLE_FILE, "r") as f:
                app.setStyleSheet(f.read())
        except IOError as e:
            log_error(f"Failed to read stylesheet: {e}")


def init_wallpaper():
    if _WALL_MODULE is not None:
        try:
            _WALL_MODULE.apply_wallpaper()
            return
        except Exception as e:
            log_error(f"Wallpaper initialization failed: {e}")

    # Wayland sessions use swaybg (started by labwc autostart or wallpaper_manager)
    if os.environ.get("WAYLAND_DISPLAY"):
        return

    if shutil.which("nitrogen"):
        launch_command("nitrogen --restore &")
    elif shutil.which("feh"):
        bg_dir = "/usr/share/backgrounds"
        if os.path.isdir(bg_dir):
            images = [f for f in os.listdir(bg_dir) if f.endswith((".png", ".jpg", ".jpeg"))]
            if images:
                img_path = os.path.join(bg_dir, sorted(images)[-1])
                launch_command(f"feh --bg-scale '{img_path}' &")


if __name__ == '__main__':
    sys.excepthook = global_exception_handler

    _load_helper_modules()

    parser = argparse.ArgumentParser(description="Vice OS Desktop Shell")
    parser.add_argument('--menu', action='store_true', help="Open the run menu")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    load_stylesheet(app)

    if args.menu:
        menu = RunMenu()
        menu.show()
        menu.activateWindow()
        menu.input_field.setFocus()
        app.setQuitOnLastWindowClosed(True)
    else:
        init_wallpaper()
        dock = Dock()
        bar = TopBar()
        dock.show()
        bar.show()
        app.setQuitOnLastWindowClosed(False)

        if _TRAY_MODULE is not None:
            try:
                _TRAY_MODULE.start_systray()
            except Exception as e:
                log_error(f"Systray initialization failed: {e}")

    sys.exit(app.exec_())
