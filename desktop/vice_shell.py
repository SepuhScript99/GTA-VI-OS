#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Desktop Shell
Provides the Mint Cinnamon-style unified bottom taskbar, instant Windows-key
(Super_L / Alt+F1) Start Menu popup with GTA VI x Debian branding, live X11
Taskbar window switcher, pinned quick-launch icons, system metrics, and Run Menu.
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
    QMenu, QSizePolicy, QListWidget, QListWidgetItem,
    QStyleOption, QStyle
)
from PyQt5.QtCore import Qt, QTimer, QSize, QEvent, QProcess
from PyQt5.QtGui import QFont, QKeySequence, QIcon, QPainter

from python.vice_utils import launch_command, get_cpu_usage, get_ram_usage, log_info, log_error

STYLE_FILE = "/opt/vice-os/style.qss"

_TRAY_MODULE = None
_POWER_MODULE = None
_WALL_MODULE = None
_PANEL_CONF = None
_LAUNCHER_MODULE = None

_SKIP_TASKBAR_TITLES = {
    "vicetopbar", "vicedock", "vicetaskbar", "vicestartmenu",
    "run command", "stalonetray", "nm-applet", "vice panel",
    "desktop", "desktop — pcmanfm",
}

_COMMAND_FALLBACKS = {
    "xfce4-terminal": ["xfce4-terminal", "xterm"],
    "mousepad": ["mousepad", "geany", "python3 /opt/vice-os/vice_text_editor.py"],
    "firefox-esr": ["firefox-esr", "firefox"],
    "firefox": ["firefox-esr", "firefox"],
    "xfce4-taskmanager": ["xfce4-taskmanager", "python3 /opt/vice-os/vice_task_manager.py"],
    "arandr": ["arandr", "python3 /opt/vice-os/vice_display_manager.py"],
    "lxappearance": ["lxappearance", "python3 /opt/vice-os/vice_theme_manager.py"],
}


def _configure_icon_theme():
    """Ensure PyQt5 resolves Freedesktop Papirus-Dark / Adwaita icons even without KDE."""
    search_paths = [
        "/usr/share/icons",
        "/usr/local/share/icons",
        os.path.expanduser("~/.local/share/icons"),
    ]
    QIcon.setThemeSearchPaths(search_paths)
    for theme in ("Papirus-Dark", "Papirus", "Adwaita", "Tango", "hicolor"):
        if os.path.isdir(os.path.join("/usr/share/icons", theme)):
            QIcon.setThemeName(theme)
            return theme
    return ""


def _theme_icon(*names) -> QIcon:
    """Return the first valid Freedesktop theme or file QIcon from *names*."""
    for name in names:
        if not name:
            continue
        if os.path.isfile(name):
            icon = QIcon(name)
            if not icon.isNull():
                return icon
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return QIcon()


def _logo_icon() -> QIcon:
    """Return the custom GTA VI x Debian Swirl logo icon."""
    return _theme_icon(
        "/usr/share/pixmaps/vice-debian-gta6.png",
        "/usr/share/pixmaps/vice-app.png",
        "start-here",
        "view-app-grid",
    )


def _runtime_dir() -> str:
    return os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/vice-{os.getuid()}"


def _toggle_trigger_path() -> str:
    return os.path.join(_runtime_dir(), "vice_start_menu.toggle")


def _lock_path() -> str:
    return os.path.join(_runtime_dir(), "vice_shell.lock")


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


def _is_shell_alive() -> bool:
    """Return True if a live vice_shell.py process holds vice_shell.lock."""
    lock_file = _lock_path()
    if not os.path.isfile(lock_file):
        return False
    try:
        with open(lock_file, "r") as f:
            pid_str = f.read().strip()
        if not pid_str.isdigit():
            return False
        os.kill(int(pid_str), 0)
        return True
    except Exception:
        return False


def _acquire_shell_lock():
    """Ensure only one instance of the desktop shell runs per user."""
    if fcntl is None:
        return None
    rdir = _runtime_dir()
    try:
        os.makedirs(rdir, exist_ok=True)
        lock_file = _lock_path()
        f = open(lock_file, "a+")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        return f
    except (IOError, OSError):
        log_info("vice_shell: another instance is already running. Exiting.")
        return False


def _pc():
    """Return panel_config module, or a fallback with sensible defaults."""
    if _PANEL_CONF is not None:
        return _PANEL_CONF
    class _Fallback:
        TOPBAR_HEIGHT = 44
        DOCK_HEIGHT = 44
        DOCK_WIDTH = 620
        RUNMENU_WIDTH = 480
        RUNMENU_HEIGHT = 56
        RUNMENU_X_FRACTION = 2
        RUNMENU_Y_FRACTION = 3
        TOPBAR_UPDATE_INTERVAL = 2000
        DOCK_Y_OFFSET = 0
        DOCK_APPS = []
    return _Fallback


def _load_helper_modules():
    global _TRAY_MODULE, _POWER_MODULE, _WALL_MODULE, _PANEL_CONF, _LAUNCHER_MODULE
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
    try:
        import vice_launcher as _vl_mod
        _LAUNCHER_MODULE = _vl_mod
    except (ImportError, Exception):
        _LAUNCHER_MODULE = None


def global_exception_handler(exc_type, exc_value, exc_tb):
    log_error(f"Unhandled exception: {exc_type.__name__}: {exc_value}")
    for line in traceback.format_tb(exc_tb):
        log_error(f"  {line.strip()}")
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    log_error("Desktop shell encountered a fatal error. Attempting auto-restart...")
    launch_command("python3 /opt/vice-os/vice_shell.py &")


class _StyledWidget(QWidget):
    """QWidget subclass that properly paints QSS background and borders."""

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class TaskbarWidget(QWidget):
    """Live X11 taskbar showing open & minimized client windows via wmctrl/xdotool."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
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
            low = clean_title.lower()
            if not clean_title or low in _SKIP_TASKBAR_TITLES or low.startswith("pcmanfm"):
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
                btn.setFixedHeight(32)
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


class StartMenuPopup(_StyledWidget):
    """Mint Cinnamon-style instant Start Menu anchored bottom-left above the taskbar."""

    _MENU_CATEGORIES = [
        ("All Applications", ("view-app-grid", "start-here", "applications-other")),
        ("Accessories", ("applications-accessories", "accessories-text-editor")),
        ("Graphics", ("applications-graphics", "image-x-generic")),
        ("Internet", ("applications-internet", "internet-web-browser")),
        ("Office", ("applications-office", "x-office-document")),
        ("Sound & Video", ("applications-multimedia", "multimedia-video-player")),
        ("Development", ("applications-development", "applications-engineering")),
        ("Administration", ("applications-system", "system-run")),
        ("Preferences", ("preferences-desktop", "preferences-system")),
        ("Places", ("folder-home", "user-home")),
    ]

    _CAT_REMAP = {
        "Utilities": "Accessories",
        "Internet": "Internet",
        "Office": "Office",
        "Development": "Development",
        "System": "Administration",
        "Settings": "Preferences",
        "Multimedia": "Sound & Video",
    }

    _PLACES = [
        ("Home", os.path.expanduser("~"), "user-home"),
        ("Desktop", os.path.expanduser("~/Desktop"), "user-desktop"),
        ("Documents", os.path.expanduser("~/Documents"), "folder-documents"),
        ("Downloads", os.path.expanduser("~/Downloads"), "folder-downloads"),
        ("Pictures", os.path.expanduser("~/Pictures"), "folder-pictures"),
        ("Music", os.path.expanduser("~/Music"), "folder-music"),
        ("Videos", os.path.expanduser("~/Videos"), "folder-videos"),
        ("File System", "/", "drive-harddisk"),
        ("Trash", "trash:///", "user-trash"),
    ]

    def __init__(self, logout_cb, power_cb):
        super().__init__()
        self._logout_cb = logout_cb
        self._power_cb = power_cb
        self._menu_open = False
        self.last_deactivated_at = 0.0
        self._apps = []
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("ViceStartMenu")
        self.setObjectName("StartMenuPopup")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Left Favorites & Power Rail (Cinnamon-style)
        rail = _StyledWidget(self)
        rail.setObjectName("StartRail")
        rail.setFixedWidth(56)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(8, 12, 8, 12)
        rail_layout.setSpacing(8)

        pinned_rail = [
            ("Firefox", ["firefox-esr", "firefox"], ("firefox-esr", "firefox", "web-browser")),
            ("Software Center", ["python3 /opt/vice-os/vice_software_center.py", "synaptic"],
             ("system-software-install", "synaptic")),
            ("Settings Center", ["python3 /opt/vice-os/vice_settings.py"], ("preferences-system", "settings")),
            ("Terminal", ["xfce4-terminal", "xterm"], ("utilities-terminal", "terminal")),
            ("Files", ["thunar", "pcmanfm"], ("system-file-manager", "folder")),
        ]
        for tip, cmds, icons in pinned_rail:
            btn = self._make_rail_button(tip, icons)
            btn.clicked.connect(lambda _=False, c=cmds: self._run_and_hide(c))
            rail_layout.addWidget(btn)

        rail_layout.addStretch(1)

        lock_btn = self._make_rail_button("Session & Lock", ("system-lock-screen", "changes-prevent"))
        lock_btn.clicked.connect(
            lambda: self._run_and_hide(["python3 /opt/vice-os/vice_session_manager.py"])
        )
        rail_layout.addWidget(lock_btn)

        logout_btn = self._make_rail_button("Log Out", ("system-log-out", "application-exit"))
        logout_btn.clicked.connect(self._do_logout)
        rail_layout.addWidget(logout_btn)

        self._power_rail_btn = self._make_rail_button("Power Options", ("system-shutdown", "system-log-out"))
        self._power_rail_btn.clicked.connect(self._show_power_menu)
        rail_layout.addWidget(self._power_rail_btn)

        root.addWidget(rail)

        # 2. Right Search + Two-Column Categories & Apps
        main_area = QWidget(self)
        main_area.setAttribute(Qt.WA_TranslucentBackground, True)
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header + Search row
        header_row = QHBoxLayout()
        logo_lbl = QLabel(main_area)
        logo_icon = _logo_icon()
        if not logo_icon.isNull():
            logo_lbl.setPixmap(logo_icon.pixmap(26, 26))
        header_row.addWidget(logo_lbl)

        brand = QLabel("VICE OS · Leonida", main_area)
        brand.setFont(QFont("Noto Sans", 11, QFont.Bold))
        brand.setStyleSheet("color: #ff8a5b;")
        header_row.addWidget(brand)
        header_row.addStretch(1)
        main_layout.addLayout(header_row)

        self._search = QLineEdit(main_area)
        self._search.setPlaceholderText("Type to search apps or settings...")
        self._search.textChanged.connect(self._populate_items)
        self._search.returnPressed.connect(self._launch_selected_or_first)
        main_layout.addWidget(self._search)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self.hide)

        # Categories (left) + Apps/Places (right)
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(10)

        self._cat_list = QListWidget(main_area)
        self._cat_list.setObjectName("StartCatList")
        self._cat_list.setFixedWidth(182)
        self._cat_list.setIconSize(QSize(18, 18))
        for cat_name, cat_icons in self._MENU_CATEGORIES:
            item = QListWidgetItem(_theme_icon(*cat_icons), cat_name)
            self._cat_list.addItem(item)
        self._cat_list.setCurrentRow(0)
        self._cat_list.currentRowChanged.connect(self._populate_items)
        cols_layout.addWidget(self._cat_list)

        self._app_list = QListWidget(main_area)
        self._app_list.setObjectName("StartAppList")
        self._app_list.setIconSize(QSize(24, 24))
        self._app_list.itemActivated.connect(self._launch_item)
        self._app_list.itemClicked.connect(self._launch_item)
        cols_layout.addWidget(self._app_list, 1)

        main_layout.addLayout(cols_layout, 1)
        root.addWidget(main_area, 1)

    def _make_rail_button(self, tooltip: str, icons: tuple) -> QPushButton:
        btn = QPushButton(self)
        btn.setObjectName("RailButton")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(38, 38)
        btn.setToolTip(tooltip)
        icon = _theme_icon(*icons)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QSize(22, 22))
        else:
            btn.setText(tooltip[:2])
        return btn

    def _map_app_category(self, app_entry: dict) -> str:
        raw_cat = app_entry.get("category", "Utilities")
        name_low = app_entry.get("label", "").lower()
        if any(k in name_low for k in ("ristretto", "image viewer", "screenshot")):
            return "Graphics"
        return self._CAT_REMAP.get(raw_cat, "Accessories")

    def reload_apps(self):
        if _LAUNCHER_MODULE is not None and hasattr(_LAUNCHER_MODULE, "discover_apps"):
            try:
                self._apps = _LAUNCHER_MODULE.discover_apps()
            except Exception as e:
                log_error(f"StartMenu: discover_apps failed: {e}")
                self._apps = []
        self._populate_items()

    def _populate_items(self):
        self._app_list.clear()
        current_item = self._cat_list.currentItem()
        selected_cat = current_item.text() if current_item else "All Applications"
        query = self._search.text().strip().lower()

        if selected_cat == "Places" and not query:
            for label, target, icon_name in self._PLACES:
                item = QListWidgetItem(_theme_icon(icon_name, "folder"), label)
                item.setData(Qt.UserRole, {"args": ["thunar", target], "label": label})
                item.setToolTip(target)
                self._app_list.addItem(item)
            return

        for app in self._apps:
            mapped_cat = self._map_app_category(app)
            if not query and selected_cat not in ("All Applications", mapped_cat):
                continue
            haystack = f"{app.get('label', '')} {app.get('name', '')} {app.get('comment', '')}".lower()
            if query and query not in haystack:
                continue
            icon = _theme_icon(app.get("icon", ""), "application-x-executable", "applications-other")
            item = QListWidgetItem(icon, app.get("label", ""))
            item.setData(Qt.UserRole, app)
            item.setToolTip(app.get("comment") or app.get("label", ""))
            self._app_list.addItem(item)

        if self._app_list.count() > 0:
            self._app_list.setCurrentRow(0)

    def _launch_selected_or_first(self):
        item = self._app_list.currentItem() or (self._app_list.item(0) if self._app_list.count() else None)
        if item:
            self._launch_item(item)

    def _launch_item(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole) or {}
        args = data.get("args", [])
        if not args:
            return
        self.hide()
        QProcess.startDetached(args[0], args[1:], os.path.expanduser("~"))

    def _run_and_hide(self, candidates: list):
        self.hide()
        _launch_candidates(candidates)

    def _do_logout(self):
        self.hide()
        self._logout_cb()

    def _show_power_menu(self):
        menu = QMenu(self)
        menu.addAction("Suspend", lambda: self._run_power("suspend"))
        menu.addAction("Restart", lambda: self._run_power("reboot"))
        menu.addAction("Power Off", lambda: self._run_power("poweroff"))
        self._menu_open = True
        try:
            pos = self._power_rail_btn.mapToGlobal(self._power_rail_btn.rect().topRight())
            menu.exec_(pos)
        finally:
            self._menu_open = False

    def _run_power(self, action: str):
        self.hide()
        self._power_cb(action)

    def open_at_bottom_left(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        pc = _pc()
        w = min(680, geo.width() - 24)
        h = min(510, geo.height() - pc.DOCK_HEIGHT - 24)
        self.setGeometry(geo.x() + 10, geo.y() + geo.height() - pc.DOCK_HEIGHT - h - 8, w, h)
        if not self._apps:
            self.reload_apps()
        self._search.clear()
        self._cat_list.setCurrentRow(0)
        self._populate_items()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(40, self._search.setFocus)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            if not self._menu_open and self.isVisible():
                self.last_deactivated_at = time.monotonic()
                self.hide()
        super().changeEvent(event)


class RunMenu(_StyledWidget):
    """Quick search/run menu triggered by W-space."""
    def __init__(self):
        super().__init__()
        self._focus_timer = None
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
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


class BottomTaskbar(_StyledWidget):
    """Unified Mint Cinnamon-style bottom panel: Start button, pinned icons, live taskbar, tray & clock."""

    def __init__(self):
        super().__init__()
        self._disk_label = None
        self._battery_btn = None
        self._start_menu = StartMenuPopup(self.logout, self._run_power_action)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("ViceTaskbar")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        if hasattr(Qt, "WA_X11NetWmWindowTypeDock") and not os.environ.get("WAYLAND_DISPLAY"):
            self.setAttribute(Qt.WA_X11NetWmWindowTypeDock, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("BottomTaskbar")

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display BottomTaskbar.")
            sys.exit(1)

        self._reposition()
        screen.geometryChanged.connect(self._reposition)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 1. GTA VI x Debian Start Button (bottom-left)
        self.apps_btn = QPushButton("Menu", self)
        self.apps_btn.setObjectName("StartButton")
        self.apps_btn.setFocusPolicy(Qt.NoFocus)
        self.apps_btn.setFixedHeight(34)
        self.apps_btn.setToolTip("Vice OS Start Menu (Windows Key)")
        logo_icon = _logo_icon()
        if not logo_icon.isNull():
            self.apps_btn.setIcon(logo_icon)
            self.apps_btn.setIconSize(QSize(24, 24))
        self.apps_btn.clicked.connect(self.toggle_start_menu)
        layout.addWidget(self.apps_btn)

        # 2. Pinned Quick-Launch Icons (Mint-style next to Start button)
        pinned_items = [
            ("Files", ["thunar", "pcmanfm"], ("system-file-manager", "folder")),
            ("Firefox", ["firefox-esr", "firefox"], ("firefox-esr", "firefox", "web-browser")),
            ("Terminal", ["xfce4-terminal", "xterm"], ("utilities-terminal", "terminal")),
            ("Text Editor", ["mousepad", "geany"], ("accessories-text-editor", "text-editor")),
        ]
        for tip, cmds, icon_names in pinned_items:
            pbtn = QPushButton(self)
            pbtn.setObjectName("PinButton")
            pbtn.setFocusPolicy(Qt.NoFocus)
            pbtn.setFixedSize(34, 34)
            pbtn.setToolTip(tip)
            picon = _theme_icon(*icon_names)
            if not picon.isNull():
                pbtn.setIcon(picon)
                pbtn.setIconSize(QSize(22, 22))
            else:
                pbtn.setText(tip[:2])
            pbtn.clicked.connect(lambda _=False, c=cmds: _launch_candidates(c))
            layout.addWidget(pbtn)

        # 3. Center: Live Taskbar window list
        self.taskbar = TaskbarWidget(self)
        layout.addWidget(self.taskbar, 1)

        # 4. Right Utility Tray: Metrics, Net, Audio, Battery, Clock, Show Desktop
        self.sysinfo = QPushButton("CPU: 0% · RAM: 0MB", self)
        self.sysinfo.setObjectName("SysInfo")
        self.sysinfo.setFocusPolicy(Qt.NoFocus)
        self.sysinfo.setToolTip("Open Task Manager")
        self.sysinfo.clicked.connect(
            lambda: _launch_candidates(["xfce4-taskmanager", "python3 /opt/vice-os/vice_task_manager.py"])
        )
        layout.addWidget(self.sysinfo)

        self.net_btn = QPushButton(self)
        self.net_btn.setObjectName("QuickUtilButton")
        self.net_btn.setFocusPolicy(Qt.NoFocus)
        self.net_btn.setFixedHeight(32)
        self.net_btn.setToolTip("Network Connections")
        net_icon = _theme_icon("network-wired", "network-wireless")
        if not net_icon.isNull():
            self.net_btn.setIcon(net_icon)
            self.net_btn.setIconSize(QSize(18, 18))
        else:
            self.net_btn.setText("Net")
        self.net_btn.clicked.connect(
            lambda: _launch_candidates(["nm-connection-editor", "python3 /opt/vice-os/vice_network_monitor.py"])
        )
        layout.addWidget(self.net_btn)

        self.audio_btn = QPushButton(self)
        self.audio_btn.setObjectName("QuickUtilButton")
        self.audio_btn.setFocusPolicy(Qt.NoFocus)
        self.audio_btn.setFixedHeight(32)
        self.audio_btn.setToolTip("Volume & Audio Devices")
        audio_icon = _theme_icon("audio-volume-high", "multimedia-volume-control")
        if not audio_icon.isNull():
            self.audio_btn.setIcon(audio_icon)
            self.audio_btn.setIconSize(QSize(18, 18))
        else:
            self.audio_btn.setText("Vol")
        self.audio_btn.clicked.connect(
            lambda: _launch_candidates(["pavucontrol", "python3 /opt/vice-os/vice_audio_manager.py"])
        )
        layout.addWidget(self.audio_btn)

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

        self.clock = QPushButton("00:00", self)
        self.clock.setObjectName("Clock")
        self.clock.setFocusPolicy(Qt.NoFocus)
        self.clock.setToolTip("Open Calendar")
        self.clock.clicked.connect(
            lambda: launch_command("python3 /opt/vice-os/vice_calendar.py")
        )
        layout.addWidget(self.clock)

        self.show_desk_btn = QPushButton(self)
        self.show_desk_btn.setObjectName("ShowDesktopButton")
        self.show_desk_btn.setFocusPolicy(Qt.NoFocus)
        self.show_desk_btn.setFixedSize(16, 32)
        self.show_desk_btn.setToolTip("Show Desktop (Super+D)")
        self.show_desk_btn.clicked.connect(self._toggle_show_desktop)
        layout.addWidget(self.show_desk_btn)

        self.setLayout(layout)

        # Periodic telemetry updates
        timer = QTimer(self)
        timer.timeout.connect(self.update_info)
        timer.start(_pc().TOPBAR_UPDATE_INTERVAL)
        self.update_info()

        # Fast IPC polling for Super/Windows key (--toggle-menu)
        self._ipc_timer = QTimer(self)
        self._ipc_timer.setInterval(100)
        self._ipc_timer.timeout.connect(self._check_toggle_trigger)
        self._ipc_timer.start()

        # Pre-load app index shortly after startup for instant Start Menu opening
        QTimer.singleShot(800, self._start_menu.reload_apps)

    def _check_toggle_trigger(self):
        trig = _toggle_trigger_path()
        if os.path.exists(trig):
            try:
                os.remove(trig)
            except OSError:
                pass
            self.toggle_start_menu()

    def toggle_start_menu(self):
        if self._start_menu.isVisible():
            self._start_menu.hide()
            return
        if time.monotonic() - self._start_menu.last_deactivated_at < 0.25:
            return
        self._start_menu.open_at_bottom_left()

    def _toggle_show_desktop(self):
        if shutil.which("xdotool"):
            subprocess.Popen(["xdotool", "key", "super+d"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
        h = getattr(pc, "DOCK_HEIGHT", 44)
        self.setGeometry(geo.x(), geo.y() + geo.height() - h, geo.width(), h)

    def update_info(self):
        self.clock.setText(time.strftime("%H:%M\n%a %d/%m"))
        self.clock.setToolTip(time.strftime("%A, %d %B %Y — Click for Calendar"))
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


TopBar = BottomTaskbar


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
    parser = argparse.ArgumentParser(description="Vice OS Desktop Shell")
    parser.add_argument('--menu', action='store_true', help="Open the run menu")
    parser.add_argument('--toggle-menu', action='store_true', help="Toggle the Start Menu popup")
    args = parser.parse_args()

    # Fast pure-Python toggle path for Windows-key / Alt+F1 (<20ms)
    if args.toggle_menu:
        if _is_shell_alive():
            rdir = _runtime_dir()
            os.makedirs(rdir, exist_ok=True)
            with open(_toggle_trigger_path(), "w") as f:
                f.write("toggle\n")
            sys.exit(0)
        launcher_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vice_launcher.py")
        subprocess.Popen([sys.executable, launcher_py], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sys.exit(0)

    sys.excepthook = global_exception_handler
    _load_helper_modules()

    app = QApplication(sys.argv)
    _configure_icon_theme()
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
        taskbar = BottomTaskbar()
        taskbar.show()
        app.setQuitOnLastWindowClosed(False)

        if _TRAY_MODULE is not None:
            try:
                _TRAY_MODULE.start_systray()
            except Exception as e:
                log_error(f"Systray initialization failed: {e}")

    sys.exit(app.exec_())
