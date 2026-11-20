#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Desktop Shell
Provides a dynamic TopBar with an Apps launcher button, live X11 Taskbar
window switcher, system metrics, quick utilities, power menu, floating Dock,
and Application Search Run Menu.
"""

import sys
import os
import time
import traceback
import argparse
import shlex
import shutil
import subprocess
try:
    import fcntl
except ImportError:
    fcntl = None

sys.path.insert(0, '/opt/vice-os/lib')
sys.path.insert(0, '/opt/vice-os')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QLineEdit, QShortcut,
    QMenu, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QKeySequence, QIcon

from python.vice_utils import launch_command, get_cpu_usage, get_ram_usage, log_info, log_error

STYLE_FILE = "/opt/vice-os/style.qss"

_TRAY_MODULE = None
_POWER_MODULE = None
_WALL_MODULE = None
_PANEL_CONF = None

_SKIP_TASKBAR_TITLES = {
    "vicetopbar", "vicedock", "run command", "stalonetray",
    "nm-applet", "vice panel", "desktop",
}

_COMMAND_FALLBACKS = {
    "xfce4-terminal": ["xfce4-terminal", "xterm"],
    "mousepad": ["mousepad", "geany", "python3 /opt/vice-os/vice_text_editor.py"],
    "firefox": ["firefox", "firefox-esr"],
    "xfce4-taskmanager": ["xfce4-taskmanager", "python3 /opt/vice-os/vice_task_manager.py"],
    "arandr": ["arandr", "python3 /opt/vice-os/vice_display_manager.py"],
    "lxappearance": ["lxappearance", "python3 /opt/vice-os/vice_theme_manager.py"],
}

_DOCK_ICONS = {
    "Apps": ("view-app-grid", "start-here", "applications-other"),
    "Terminal": ("utilities-terminal", "terminal"),
    "Browser": ("firefox-esr", "firefox", "web-browser", "internet-web-browser"),
    "Files": ("system-file-manager", "folder"),
    "Editor": ("accessories-text-editor", "mousepad", "geany"),
    "Calc": ("accessories-calculator", "galculator"),
    "Settings": ("preferences-system", "settings"),
}


def _theme_icon(*names) -> QIcon:
    """Return the first valid Freedesktop theme QIcon from *names*."""
    for name in names:
        if name:
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                return icon
    return QIcon()


def _resolve_command(cmd: str) -> str:
    """Resolve *cmd* to an executable command, checking fallbacks if missing."""
    candidates = _COMMAND_FALLBACKS.get(cmd, [cmd])
    for candidate in candidates:
        parts = shlex.split(candidate)
        if not parts:
            continue
        binary = parts[0]
        if shutil.which(binary):
            if binary == "python3" and len(parts) > 1 and not os.path.exists(parts[1]):
                continue
            return candidate
    return cmd


def _launch_candidates(candidates: list) -> bool:
    """Launch the first available command in *candidates*."""
    for candidate in candidates:
        resolved = _resolve_command(candidate)
        parts = shlex.split(resolved)
        if parts and shutil.which(parts[0]) and launch_command(resolved):
            return True
    return False


def _acquire_shell_lock():
    """Ensure only one instance of the desktop shell (TopBar + Dock) runs per user."""
    if fcntl is None:
        return None
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/vice-{os.getuid()}"
    try:
        os.makedirs(runtime_dir, exist_ok=True)
        lock_file = os.path.join(runtime_dir, "vice_shell.lock")
        f = open(lock_file, "w")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except (IOError, OSError):
        log_info("vice_shell: another instance is already running. Exiting.")
        return False


def _pc():
    """Return panel_config module, or a fallback with sensible defaults."""
    if _PANEL_CONF is not None:
        return _PANEL_CONF
    class _Fallback:
        TOPBAR_HEIGHT = 38
        DOCK_HEIGHT = 64
        DOCK_WIDTH = 620
        RUNMENU_WIDTH = 480
        RUNMENU_HEIGHT = 56
        RUNMENU_X_FRACTION = 2
        RUNMENU_Y_FRACTION = 3
        TOPBAR_UPDATE_INTERVAL = 2000
        DOCK_Y_OFFSET = 0
        DOCK_APPS = [
            ("Apps", "python3 /opt/vice-os/vice_launcher.py", "Open Application Menu"),
            ("Terminal", "xfce4-terminal", "Open Terminal"),
            ("Browser", "firefox", "Launch Web Browser"),
            ("Files", "thunar", "Open File Manager"),
            ("Editor", "mousepad", "Open Text Editor"),
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
        import panel_config as _pc_mod
        _PANEL_CONF = _pc_mod
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


class TaskbarWidget(QWidget):
    """Live X11 taskbar showing open & minimized client windows via wmctrl/xdotool."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 2, 6, 2)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)
        self._buttons = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1200)
        self._poll_timer.timeout.connect(self._refresh)
        self._poll_timer.start()
        self._refresh()

    def _get_windows(self) -> list:
        """Return list of (window_id_int, title) via wmctrl -l."""
        if os.environ.get("WAYLAND_DISPLAY") or not shutil.which("wmctrl"):
            return []
        try:
            out = subprocess.check_output(
                ["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL, timeout=2
            )
        except Exception:
            return []

        windows = []
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            wid_hex, desk, _host, title = parts[0], parts[1], parts[2], parts[3]
            if desk == "-1":
                continue
            clean_title = title.strip()
            if not clean_title or clean_title.lower() in _SKIP_TASKBAR_TITLES:
                continue
            try:
                windows.append((int(wid_hex, 16), clean_title))
            except ValueError:
                continue
        return windows

    def _get_active_window(self):
        """Return currently focused X11 window ID via xdotool, or None."""
        if os.environ.get("WAYLAND_DISPLAY") or not shutil.which("xdotool"):
            return None
        try:
            out = subprocess.check_output(
                ["xdotool", "getactivewindow"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return int(out.strip())
        except Exception:
            return None

    def _refresh(self):
        windows = self._get_windows()
        active_wid = self._get_active_window()
        current_ids = {wid for wid, _ in windows}

        for wid in list(self._buttons.keys()):
            if wid not in current_ids:
                btn = self._buttons.pop(wid)
                self._layout.removeWidget(btn)
                btn.deleteLater()

        stretch_idx = max(0, self._layout.count() - 1)
        for wid, title in windows:
            btn = self._buttons.get(wid)
            if btn is None:
                btn = QPushButton(self)
                btn.setObjectName("TaskButton")
                btn.setCheckable(True)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setFixedHeight(28)
                btn.clicked.connect(lambda _checked=False, w=wid: self._toggle_window(w))
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, w=wid, b=btn: self._show_window_menu(w, b, pos)
                )
                self._buttons[wid] = btn
                self._layout.insertWidget(stretch_idx, btn)
                stretch_idx += 1

            label = title if len(title) <= 22 else title[:20] + "…"
            if btn.text() != label:
                btn.setText(label)
            btn.setToolTip(title)
            btn.setChecked(active_wid is not None and wid == active_wid)

    def _toggle_window(self, wid: int):
        """Focus/restore an inactive window, or minimize the active window."""
        active_wid = self._get_active_window()
        if active_wid is not None and wid == active_wid and shutil.which("xdotool"):
            subprocess.Popen(["xdotool", "windowminimize", str(wid)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("wmctrl"):
            subprocess.Popen(["wmctrl", "-ia", hex(wid)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        QTimer.singleShot(150, self._refresh)

    def _minimize_window(self, wid: int):
        if shutil.which("xdotool"):
            subprocess.Popen(["xdotool", "windowminimize", str(wid)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            QTimer.singleShot(150, self._refresh)

    def _toggle_maximize(self, wid: int):
        if shutil.which("wmctrl"):
            subprocess.Popen(
                ["wmctrl", "-ir", hex(wid), "-b", "toggle,maximized_vert,maximized_horz"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

    def _close_window(self, wid: int):
        if shutil.which("wmctrl"):
            subprocess.Popen(["wmctrl", "-ic", hex(wid)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            QTimer.singleShot(200, self._refresh)

    def _show_window_menu(self, wid: int, btn: QPushButton, pos):
        menu = QMenu(self)
        menu.addAction("Restore / Focus", lambda: self._toggle_window(wid))
        menu.addAction("Minimize", lambda: self._minimize_window(wid))
        menu.addAction("Maximize / Restore", lambda: self._toggle_maximize(wid))
        menu.addSeparator()
        menu.addAction("Close", lambda: self._close_window(wid))
        menu.exec_(btn.mapToGlobal(pos))


class RunMenu(QWidget):
    """Quick search/run menu triggered by W-space."""
    def __init__(self):
        super().__init__()
        self._focus_timer = None
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_StyledBackground, True)
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
            geo.x() + geo.width() // pc.RUNMENU_X_FRACTION - menu_w // 2,
            geo.y() + geo.height() // pc.RUNMENU_Y_FRACTION,
            menu_w, menu_h
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Run command or application...")
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
        self.input_field.setStyleSheet("border: 1px solid #ff3b6b; color: #ff6b8b;")
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
    """Floating application dock centered at the bottom of the screen."""
    def __init__(self):
        super().__init__()
        self._buttons = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle("ViceDock")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        if hasattr(Qt, "WA_X11NetWmWindowTypeDock") and not os.environ.get("WAYLAND_DISPLAY"):
            self.setAttribute(Qt.WA_X11NetWmWindowTypeDock, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("Dock")

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display Dock.")
            sys.exit(1)

        pc = _pc()
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        for app in pc.DOCK_APPS:
            name, cmd = app[0], app[1]
            tip = app[2] if len(app) > 2 else name
            resolved = _resolve_command(cmd)
            parts = shlex.split(resolved)
            if not parts or not shutil.which(parts[0]):
                continue
            if parts[0] == "python3" and len(parts) > 1 and not os.path.exists(parts[1]):
                continue

            btn = QPushButton(name, self)
            btn.setObjectName("DockButton")
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setToolTip(tip)
            icon = _theme_icon(*_DOCK_ICONS.get(name, ("application-x-executable",)))
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(lambda _state=False, c=resolved: launch_command(c))
            layout.addWidget(btn)
            self._buttons.append(btn)

        self.setLayout(layout)
        self._reposition()
        screen.geometryChanged.connect(self._reposition)

    def _reposition(self, _geometry=None):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        pc = _pc()
        btn_count = max(len(self._buttons), len(pc.DOCK_APPS))
        dock_width = min(max(pc.DOCK_WIDTH, btn_count * 94 + 28), geo.width() - 24)
        dock_height = pc.DOCK_HEIGHT
        y_offset = getattr(pc, "DOCK_Y_OFFSET", 0)
        x = geo.x() + (geo.width() - dock_width) // 2
        y = geo.y() + geo.height() - dock_height - y_offset
        self.setGeometry(x, y, dock_width, dock_height)


class TopBar(QWidget):
    """Top desktop bar with Apps launcher, live Taskbar, metrics, quick controls, clock, and Power menu."""
    def __init__(self):
        super().__init__()
        self._disk_label = None
        self._battery_btn = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("ViceTopBar")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        if hasattr(Qt, "WA_X11NetWmWindowTypeDock") and not os.environ.get("WAYLAND_DISPLAY"):
            self.setAttribute(Qt.WA_X11NetWmWindowTypeDock, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("TopBar")

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display TopBar.")
            sys.exit(1)

        self._reposition()
        screen.geometryChanged.connect(self._reposition)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(6)

        # Left: Applications Launcher button
        self.apps_btn = QPushButton("Apps", self)
        self.apps_btn.setObjectName("AppsButton")
        self.apps_btn.setFocusPolicy(Qt.NoFocus)
        self.apps_btn.setToolTip("Open Applications Menu (Super+A)")
        apps_icon = _theme_icon("view-app-grid", "start-here", "applications-other")
        if not apps_icon.isNull():
            self.apps_btn.setIcon(apps_icon)
            self.apps_btn.setIconSize(QSize(16, 16))
        self.apps_btn.clicked.connect(
            lambda: launch_command("python3 /opt/vice-os/vice_launcher.py")
        )
        layout.addWidget(self.apps_btn)

        # Center: Live Taskbar window list
        self.taskbar = TaskbarWidget(self)
        layout.addWidget(self.taskbar, 1)

        # Right: System Telemetry (clickable -> Task Manager)
        self.sysinfo = QPushButton("CPU: 0% · RAM: 0MB", self)
        self.sysinfo.setObjectName("SysInfo")
        self.sysinfo.setFocusPolicy(Qt.NoFocus)
        self.sysinfo.setToolTip("Open Task Manager")
        self.sysinfo.clicked.connect(
            lambda: _launch_candidates(["xfce4-taskmanager", "python3 /opt/vice-os/vice_task_manager.py"])
        )
        layout.addWidget(self.sysinfo)

        # Quick Audio Control
        self.audio_btn = QPushButton("Audio", self)
        self.audio_btn.setObjectName("QuickUtilButton")
        self.audio_btn.setFocusPolicy(Qt.NoFocus)
        self.audio_btn.setToolTip("Volume & Audio Devices")
        audio_icon = _theme_icon("audio-volume-high", "multimedia-volume-control")
        if not audio_icon.isNull():
            self.audio_btn.setIcon(audio_icon)
            self.audio_btn.setIconSize(QSize(15, 15))
        self.audio_btn.clicked.connect(
            lambda: _launch_candidates(["pavucontrol", "python3 /opt/vice-os/vice_audio_manager.py"])
        )
        layout.addWidget(self.audio_btn)

        # Quick Network Control
        self.net_btn = QPushButton("Net", self)
        self.net_btn.setObjectName("QuickUtilButton")
        self.net_btn.setFocusPolicy(Qt.NoFocus)
        self.net_btn.setToolTip("Network Connections")
        net_icon = _theme_icon("network-wired", "network-wireless")
        if not net_icon.isNull():
            self.net_btn.setIcon(net_icon)
            self.net_btn.setIconSize(QSize(15, 15))
        self.net_btn.clicked.connect(
            lambda: _launch_candidates(["nm-connection-editor", "python3 /opt/vice-os/vice_network_monitor.py"])
        )
        layout.addWidget(self.net_btn)

        # Optional battery pill when present
        if _POWER_MODULE is not None:
            try:
                bat_text = _POWER_MODULE._read_battery_status()
                if bat_text != "AC":
                    self._battery_btn = QPushButton(bat_text, self)
                    self._battery_btn.setObjectName("SysInfo")
                    self._battery_btn.setFocusPolicy(Qt.NoFocus)
                    self._battery_btn.setToolTip("Power & Battery Settings")
                    self._battery_btn.clicked.connect(
                        lambda: launch_command("python3 /opt/vice-os/vice_power_manager.py")
                    )
                    layout.addWidget(self._battery_btn)
            except Exception as e:
                log_error(f"Failed to read battery status: {e}")

        # Clock button -> Calendar
        self.clock = QPushButton("00:00", self)
        self.clock.setObjectName("Clock")
        self.clock.setFocusPolicy(Qt.NoFocus)
        self.clock.setToolTip("Open Calendar")
        self.clock.clicked.connect(
            lambda: launch_command("python3 /opt/vice-os/vice_calendar.py")
        )
        layout.addWidget(self.clock)

        # Power / Session dropdown menu (replaces bare top-left shutdown buttons)
        self.power_btn = QPushButton("Power ▾", self)
        self.power_btn.setObjectName("PowerButton")
        self.power_btn.setFocusPolicy(Qt.NoFocus)
        self.power_btn.setToolTip("System Settings & Power Menu")
        power_icon = _theme_icon("system-shutdown", "system-log-out")
        if not power_icon.isNull():
            self.power_btn.setIcon(power_icon)
            self.power_btn.setIconSize(QSize(15, 15))
        self.power_btn.clicked.connect(self._show_power_menu)
        layout.addWidget(self.power_btn)

        self.setLayout(layout)

        timer = QTimer(self)
        timer.timeout.connect(self.update_info)
        timer.start(_pc().TOPBAR_UPDATE_INTERVAL)
        self.update_info()

    def _show_power_menu(self):
        menu = QMenu(self)
        menu.addAction(
            "Settings Center",
            lambda: launch_command("python3 /opt/vice-os/vice_settings.py"),
        )
        menu.addAction(
            "Display Settings",
            lambda: _launch_candidates(["arandr", "python3 /opt/vice-os/vice_display_manager.py"]),
        )
        menu.addAction(
            "Appearance & Themes",
            lambda: _launch_candidates(["lxappearance", "python3 /opt/vice-os/vice_theme_manager.py"]),
        )
        menu.addSeparator()
        menu.addAction("Log Out", self.logout)
        menu.addAction("Suspend", lambda: self._run_power_action("suspend"))
        menu.addAction("Restart", lambda: self._run_power_action("reboot"))
        menu.addAction("Power Off", lambda: self._run_power_action("poweroff"))

        pos = self.power_btn.mapToGlobal(self.power_btn.rect().bottomLeft())
        menu.exec_(pos)

    def _run_power_action(self, action: str):
        if _POWER_MODULE is not None:
            if action == "suspend":
                _POWER_MODULE.suspend_system()
                return
            if action == "reboot":
                _POWER_MODULE.reboot_system()
                return
            if action == "poweroff":
                _POWER_MODULE.shutdown_system()
                return
        launch_command(f"systemctl {action}")

    def _reposition(self, _geometry=None):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        pc = _pc()
        self.setGeometry(geo.x(), geo.y(), geo.width(), pc.TOPBAR_HEIGHT)

    def update_info(self):
        self.clock.setText(time.strftime("%a %b %d  %H:%M"))
        try:
            cpu_text = get_cpu_usage()
            ram_text = get_ram_usage()
            parts = [cpu_text, ram_text]
            if self._disk_label is None:
                self._init_disk_label()
            if self._disk_label:
                parts.append(self._disk_label)
            self.sysinfo.setText(" · ".join(parts))
            if self._battery_btn is not None and _POWER_MODULE is not None:
                self._battery_btn.setText(_POWER_MODULE._read_battery_status())
        except Exception as e:
            log_error(f"Failed to update system info: {e}")
            self.sysinfo.setText("System info")

    def _init_disk_label(self):
        try:
            self._disk_label = ""
            self._update_disk_usage()
        except Exception as e:
            log_error(f"Failed to initialize disk label: {e}")

    def _update_disk_usage(self):
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
        shell_lock_fd = _acquire_shell_lock()
        if shell_lock_fd is False:
            sys.exit(0)
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
