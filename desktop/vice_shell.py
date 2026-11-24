#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Desktop Shell
Provides the Mint Cinnamon-style unified bottom taskbar, instant Windows-key
(Super_L / Alt+F1) Start Menu popup with GTA VI x Debian branding, live X11
Taskbar window switcher, pinned quick-launch icons, system metrics, and Run Menu.
"""

import sys
import os
import json
import re
import time
import threading
import traceback
import argparse
import shlex
import shutil
import subprocess
try:
    import fcntl
except ImportError:
    fcntl = None

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QLineEdit, QShortcut,
    QMenu, QSizePolicy, QListWidget, QListWidgetItem,
    QSlider, QStyleOption, QStyle
)
from PyQt5.QtCore import Qt, QTimer, QSize, QEvent, QProcess, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetrics, QKeySequence, QIcon, QPainter, QPixmap, QPen, QColor

sys.path.insert(0, '/opt/vice-os/lib')
sys.path.insert(0, '/opt/vice-os')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import launch_command, get_cpu_usage, get_ram_usage, log_info, log_error  # noqa: E402
from vice_theme import COLORS, configure_cjk_fonts, configure_icon_theme, resolve_icon  # noqa: E402

STYLE_FILE = "/opt/vice-os/style.qss"

_TRAY_MODULE = None
_POWER_MODULE = None
_WALL_MODULE = None
_PANEL_CONF = None
_LAUNCHER_MODULE = None

_CJK_FONT_FAMILIES = (
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
)

_MONO_CJK_FAMILIES = (
    "DejaVu Sans Mono",
    "Noto Sans Mono CJK JP",
    "Noto Sans Mono CJK SC",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
)

_SKIP_TASKBAR_TITLES = {
    "vicetopbar", "vicedock", "vicetaskbar", "vicestartmenu", "vicevolumepopup",
    "run command", "stalonetray", "nm-applet", "vice panel",
    "desktop", "desktop — pcmanfm", "vice os — desktop widgets",
    "vicepanel", "polkit-gnome-authentication-agent-1",
}

_COMMAND_FALLBACKS = {
    "xfce4-terminal": ["xfce4-terminal", "xterm"],
    "mousepad": ["mousepad", "geany", "python3 /opt/vice-os/vice_text_editor.py"],
    "geany": ["geany", "mousepad", "python3 /opt/vice-os/vice_text_editor.py"],
    "firefox-esr": ["firefox-esr", "firefox"],
    "firefox": ["firefox-esr", "firefox"],
    "xfce4-taskmanager": ["xfce4-taskmanager", "python3 /opt/vice-os/vice_task_manager.py"],
    "arandr": ["arandr", "python3 /opt/vice-os/vice_display_manager.py"],
    "lxappearance": ["lxappearance", "python3 /opt/vice-os/vice_theme_manager.py"],
    "galculator": ["galculator", "python3 /opt/vice-os/vice_calculator.py"],
    "celluloid": ["celluloid", "mpv", "python3 /opt/vice-os/vice_media_player.py"],
    "mpv": ["mpv", "celluloid", "python3 /opt/vice-os/vice_media_player.py"],
    "ristretto": ["ristretto", "feh", "python3 /opt/vice-os/vice_image_viewer.py"],
    "qpdfview": ["qpdfview", "python3 /opt/vice-os/vice_pdf_viewer.py"],
    "file-roller": ["file-roller", "python3 /opt/vice-os/vice_archive_manager.py"],
    "gnome-screenshot": ["gnome-screenshot", "python3 /opt/vice-os/vice_screenshot.py"],
    "pavucontrol": ["pavucontrol", "python3 /opt/vice-os/vice_audio_manager.py"],
    "nm-connection-editor": ["nm-connection-editor", "python3 /opt/vice-os/vice_wifi_connect.py"],
    "gparted": ["gparted", "python3 /opt/vice-os/vice_disk_manager.py"],
    "synaptic": ["synaptic-pkexec", "synaptic", "python3 /opt/vice-os/vice_software_center.py"],
}


def _configure_cjk_fonts(app: QApplication):
    """Register Noto Sans CJK fallbacks so Japanese/CJK window titles render without tofu boxes."""
    cjk_list = list(_CJK_FONT_FAMILIES)
    for base in ("Noto Sans", "DejaVu Sans", "Sans", "sans-serif", "Arial"):
        QFont.insertSubstitutions(base, cjk_list)
    configure_cjk_fonts(app, size=10)


def _configure_icon_theme():
    """Ensure PyQt5 resolves Freedesktop Papirus-Dark / Adwaita icons even without KDE."""
    theme = configure_icon_theme()
    if theme:
        QIcon.setThemeName(theme)
    return theme


def _theme_icon(*names) -> QIcon:
    """Return the first valid Freedesktop theme, hicolor app icon, or pixmap QIcon from *names*."""
    return resolve_icon(*names)


def _make_show_desktop_icon() -> QIcon:
    """Render a crisp 16x16 desktop-peek vector icon so ShowDesktopButton is never blank."""
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(QColor(COLORS["text_secondary"]), 1.4))
    p.drawRoundedRect(1, 2, 14, 11, 2.0, 2.0)
    p.fillRect(2, 10, 12, 2, QColor(COLORS["accent_aqua"]))
    p.fillRect(11, 4, 2, 5, QColor(COLORS["accent_coral"]))
    p.end()
    return QIcon(pix)


def _battery_icon(bat_text: str) -> QIcon:
    """Return a Freedesktop battery icon matching charging state and percentage."""
    low = (bat_text or "").lower()
    charging = "chrg" in low or "charg" in low
    m = re.search(r"(\d+)", low)
    pct = int(m.group(1)) if m else 100
    if charging:
        if pct >= 80:
            return _theme_icon("battery-full-charging", "battery-good-charging", "battery")
        if pct >= 35:
            return _theme_icon("battery-good-charging", "battery-full-charging", "battery")
        return _theme_icon("battery-low-charging", "battery-caution-charging", "battery")
    if pct >= 80:
        return _theme_icon("battery-full", "battery-good", "battery")
    if pct >= 35:
        return _theme_icon("battery-good", "battery-full", "battery")
    if pct >= 15:
        return _theme_icon("battery-low", "battery-caution", "battery")
    return _theme_icon("battery-caution", "battery-empty", "battery")


def _logo_icon() -> QIcon:
    """Return the custom GTA VI x Debian Swirl logo icon."""
    return _theme_icon(
        "/usr/share/pixmaps/vice-debian-gta6.png",
        "/usr/share/pixmaps/vice-app.png",
        "start-here",
        "view-app-grid",
    )


def _runtime_dir() -> str:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg and os.path.isdir(xdg):
        return xdg
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    run_dir = f"/run/user/{uid}"
    if os.path.isdir(run_dir) and os.access(run_dir, os.W_OK):
        return run_dir
    return f"/tmp/vice-{uid}"


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
    """Live X11 taskbar showing open & minimized client windows via xprop spy + wmctrl/xdotool."""

    _polled = pyqtSignal(list, object)
    _spy_event = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self._buttons = {}
        self._window_titles = {}
        self._window_classes = {}
        self._last_windows = None
        self._last_active = None
        self._poll_busy = False
        self._spy_stop = False
        self._spy_proc = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(0)

        self._polled.connect(self._apply_poll_result)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._refresh)
        self._spy_event.connect(self._schedule_refresh)

        has_spy = self._start_x11_spy()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(6000 if has_spy else 2500)
        self._poll_timer.timeout.connect(self._refresh)
        self._poll_timer.start()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_spy)
        self._refresh()

    def _schedule_refresh(self):
        if not self._debounce.isActive():
            self._debounce.start()

    def _start_x11_spy(self) -> bool:
        """Watch X11 root properties via xprop -spy for 0% idle CPU taskbar updates."""
        if os.environ.get("WAYLAND_DISPLAY") or not shutil.which("xprop"):
            return False

        def _spy_loop():
            try:
                proc = subprocess.Popen(
                    ["xprop", "-root", "-spy", "_NET_CLIENT_LIST", "_NET_ACTIVE_WINDOW"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
                )
                self._spy_proc = proc
                while not self._spy_stop and proc.poll() is None:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    try:
                        self._spy_event.emit()
                    except RuntimeError:
                        break
            except Exception:
                pass

        threading.Thread(target=_spy_loop, daemon=True).start()
        return True

    def _stop_spy(self):
        self._spy_stop = True
        proc = self._spy_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def closeEvent(self, event):
        self._stop_spy()
        super().closeEvent(event)

    def _get_windows(self) -> list:
        """Return list of (window_id_int, title, wm_class) via wmctrl -lx."""
        if os.environ.get("WAYLAND_DISPLAY") or not shutil.which("wmctrl"):
            return []
        try:
            out = subprocess.check_output(
                ["wmctrl", "-lx"], text=True, encoding="utf-8", errors="replace",
                stderr=subprocess.DEVNULL, timeout=0.8
            )
        except Exception:
            return []

        windows = []
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue
            wid_hex, desk, wm_class, _host, title = parts
            if desk == "-1":
                continue
            clean_title = title.strip()
            low = clean_title.lower()
            if not clean_title or low in _SKIP_TASKBAR_TITLES or low == "pcmanfm":
                continue
            try:
                windows.append((int(wid_hex, 16), clean_title, wm_class))
            except ValueError:
                continue
        return windows

    def _get_active_window(self):
        """Return currently focused X11 window ID via xprop or xdotool fallback, or None."""
        if os.environ.get("WAYLAND_DISPLAY"):
            return None
        if shutil.which("xprop"):
            try:
                out = subprocess.check_output(
                    ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                    text=True, stderr=subprocess.DEVNULL, timeout=0.5
                )
                m = re.search(r"0x([0-9a-fA-F]+)", out)
                if m:
                    wid = int(m.group(1), 16)
                    return wid if wid != 0 else None
            except Exception:
                pass
        if shutil.which("xdotool"):
            try:
                out = subprocess.check_output(
                    ["xdotool", "getactivewindow"],
                    text=True, stderr=subprocess.DEVNULL, timeout=0.6
                )
                return int(out.strip())
            except Exception:
                return None
        return None

    def _refresh(self):
        if self._poll_busy:
            return
        self._poll_busy = True

        def _worker():
            try:
                windows = self._get_windows()
                active_wid = self._get_active_window()
            except Exception:
                windows, active_wid = [], None
            try:
                self._polled.emit(windows, active_wid)
            except RuntimeError:
                self._poll_busy = False

        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def _icon_for_title(title: str, wm_class: str = "") -> QIcon:
        low_title = (title or "").lower()
        low_class = (wm_class or "").lower()
        if "vice os — system info" in low_title or "vicefetch" in low_title:
            ic = _theme_icon("vice-tool-fetch", "utilities-terminal")
            if not ic.isNull():
                return ic
        if "hw & vm auto-detect" in low_title or "hw auto-detect" in low_title:
            ic = _theme_icon("vice-tool-hw-autodetect", "vice-tool-sys-deck", "computer")
            if not ic.isNull():
                return ic
        if any(k in low_class for k in ("xfce4-terminal", "xterm")) or "vice os - " in low_title:
            ic = _theme_icon("utilities-terminal", "terminal")
            if not ic.isNull():
                return ic
        low = f"{low_title} {low_class}"
        rules = (
            (("vice tool hub", "tool hub"), ("vice-tool-hub", "view-app-grid")),
            (("leonida fm radio",), ("vice-tool-radio", "audio-x-generic")),
            (("leonida net radar",), ("vice-tool-net-radar", "network-workgroup")),
            (("vice mission",), ("vice-tool-missions", "view-task")),
            (("vice vault",), ("vice-tool-vault", "security-high")),
            (("vice turbo",), ("vice-tool-turbo", "utilities-system-monitor")),
            (("vice media studio",), ("vice-tool-media-studio", "multimedia-video-player")),
            (("vice qr",), ("vice-tool-qr-hash", "applications-development")),
            (("vice payload lab", "payload lab", "cyber encoder"), ("vice-tool-payload-lab", "security-high")),
            (("vice cyber", "cyber deck"), ("vice-tool-cyber-deck", "security-high")),
            (("vice hardware", "hw & vm auto-detect", "hw auto-detect", "hardware"), ("vice-tool-hw-autodetect", "vice-tool-sys-deck", "computer")),
            (("vice command",), ("vice-tool-cheatsheets", "utilities-terminal")),
            (("vice net shield", "net shield"), ("vice-tool-net-shield", "network-vpn")),
            (("vice privacy", "identity cloak", "mac cloak"), ("vice-tool-mac-cloak", "changes-prevent")),
            (("vice office", "office studio"), ("vice-tool-office-hub", "x-office-document")),
            (("vice world clock", "clock sync"), ("vice-tool-clock-sync", "preferences-system-time")),
            (("galculator", "calculator"), ("vice-tool-galculator", "galculator", "accessories-calculator")),
            (("libreoffice writer", "libreoffice-writer"), ("vice-tool-libreoffice-writer", "libreoffice-writer", "x-office-document")),
            (("libreoffice calc", "libreoffice-calc"), ("vice-tool-libreoffice-calc", "libreoffice-calc", "x-office-spreadsheet")),
            (("libreoffice impress", "libreoffice-impress"), ("vice-tool-libreoffice-impress", "libreoffice-impress", "x-office-presentation")),
            (("libreoffice draw", "libreoffice-draw"), ("vice-tool-libreoffice-draw", "libreoffice-draw", "x-office-drawing")),
            (("libreoffice math", "libreoffice-math"), ("vice-tool-libreoffice-math", "libreoffice-math", "accessories-calculator")),
            (("vice os settings",), ("preferences-system", "settings")),
            (("firefox",), ("firefox-esr", "firefox", "web-browser")),
            (("thunar",), ("system-file-manager", "folder")),
            (("terminal",), ("utilities-terminal", "terminal")),
            (("mousepad", "geany"), ("accessories-text-editor", "text-editor")),
            (("pavucontrol", "audio manager"), ("audio-volume-high", "multimedia-volume-control")),
        )
        for keys, icons in rules:
            if any(k in low for k in keys):
                ic = _theme_icon(*icons)
                if not ic.isNull():
                    return ic
        if "visual studio code" in low or re.search(r"\b(?:code|vscode)\b", low_class) or re.search(r"\bcode\b", low_title):
            ic = _theme_icon("vice-tool-vscode", "code", "accessories-text-editor")
            if not ic.isNull():
                return ic
        return _theme_icon("application-x-executable", "applications-other")

    @staticmethod
    def _compute_button_width(avail: int, count: int, spacing_px: int = 4) -> int:
        """Compute uniform TaskButton width (34..210px) bounded inside *avail*."""
        if count <= 0:
            return 210
        spacing = max(0, count - 1) * spacing_px
        raw_w = (avail - spacing) // count
        floor_w = 34 if (34 * count + spacing) <= avail else max(22, raw_w)
        return max(floor_w, min(210, raw_w))

    def _available_taskbar_width(self) -> int:
        parent = self.parentWidget()
        if parent is not None and parent.width() > 0:
            layout = parent.layout()
            if layout is not None:
                margins = layout.contentsMargins()
                spacing = max(0, layout.spacing())
                used = margins.left() + margins.right()
                other_count = 0
                for idx in range(layout.count()):
                    item = layout.itemAt(idx)
                    w = item.widget() if item is not None else None
                    if w is not None and w is not self and w.isVisibleTo(parent):
                        w_est = max(w.width(), w.sizeHint().width()) if parent.isVisible() else w.sizeHint().width()
                        used += w_est
                        other_count += 1
                used += other_count * spacing
                parent_avail = max(48, parent.width() - used - 8)
                if self.width() <= 100:
                    return parent_avail
                return min(max(48, self.width() - 8), parent_avail)
        return max(48, self.width() - 8)

    def _update_button_layout(self):
        count = len(self._buttons)
        if count <= 0:
            return
        avail = self._available_taskbar_width()
        per_btn_w = self._compute_button_width(avail, count)
        for wid, btn in self._buttons.items():
            title = self._window_titles.get(wid, btn.toolTip() or btn.text())
            btn.setFixedWidth(per_btn_w)
            if per_btn_w < 54:
                label = ""
            else:
                text_budget = per_btn_w - 36
                bold_font = QFont(btn.font())
                bold_font.setBold(True)
                elided = QFontMetrics(bold_font).elidedText(title, Qt.ElideRight, max(12, text_budget))
                label = elided.replace("&", "&&")
            if btn.text() != label:
                btn.setText(label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_button_layout()

    def _apply_poll_result(self, windows, active_wid):
        self._poll_busy = False
        if windows == self._last_windows and active_wid == self._last_active:
            return
        self._last_windows = list(windows)
        self._last_active = active_wid

        current_ids = {entry[0] for entry in windows}

        for wid in list(self._buttons.keys()):
            if wid not in current_ids:
                btn = self._buttons.pop(wid)
                self._window_titles.pop(wid, None)
                self._window_classes.pop(wid, None)
                self._layout.removeWidget(btn)
                btn.deleteLater()

        stretch_idx = max(0, self._layout.count() - 1)
        for entry in windows:
            wid = entry[0]
            title = entry[1]
            wm_class = entry[2] if len(entry) > 2 else ""
            self._window_titles[wid] = title
            self._window_classes[wid] = wm_class
            btn = self._buttons.get(wid)
            if btn is None:
                btn = QPushButton(self)
                btn.setObjectName("TaskButton")
                btn.setCheckable(True)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                btn.setFixedHeight(32)
                btn.setIconSize(QSize(16, 16))
                btn.clicked.connect(lambda _checked=False, w=wid: self._toggle_window(w))
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, w=wid, b=btn: self._show_window_menu(w, b, pos)
                )
                self._buttons[wid] = btn
                self._layout.insertWidget(stretch_idx, btn)
                stretch_idx += 1

            ic = self._icon_for_title(title, wm_class)
            if not ic.isNull():
                btn.setIcon(ic)
            if btn.toolTip() != title:
                btn.setToolTip(title)
            is_active = active_wid is not None and wid == active_wid
            if btn.isChecked() != is_active:
                btn.setChecked(is_active)

        self._update_button_layout()

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


def _read_registry_counts() -> tuple:
    """Return (current_count, target_count) from tools_registry.json."""
    candidates = (
        "/opt/vice-os/tools_registry.json",
        os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "tools_registry.json")
        ),
    )
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                cur = int(next(
                    (v for v in (
                        data.get("current_count"),
                        data.get("implemented_count"),
                        len(data.get("tools", [])),
                    ) if v),
                    425,
                ))
                tgt = int(data.get("target_count") or data.get("total_slots") or 500)
                return cur, tgt
            except Exception:
                pass
    return 425, 500


class StartMenuPopup(_StyledWidget):
    """Mint Cinnamon-style instant Start Menu anchored bottom-left above the taskbar."""

    _MENU_CATEGORIES = [
        ("All Applications", ("view-app-grid", "start-here", "applications-other")),
        ("Vice Tools", ("vice-tool-hub", "applications-utilities", "applications-other")),
        ("Office", ("vice-tool-office-hub", "applications-office", "x-office-document")),
        ("Security", ("vice-tool-cyber-deck", "security-high", "changes-prevent")),
        ("Accessories", ("applications-accessories", "accessories-text-editor")),
        ("Graphics", ("applications-graphics", "image-x-generic")),
        ("Internet", ("applications-internet", "internet-web-browser")),
        ("Sound & Video", ("applications-multimedia", "multimedia-video-player")),
        ("Development", ("applications-development", "applications-engineering")),
        ("Administration", ("applications-system", "system-run")),
        ("Preferences", ("preferences-desktop", "preferences-system")),
        ("Places", ("folder-home", "user-home")),
    ]

    _CAT_REMAP = {
        "Utilities": "Accessories",
        "Graphics": "Graphics",
        "Internet": "Internet",
        "Office": "Office",
        "Security": "Security",
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
        self._opened_at = 0.0
        self._last_launch_at = 0.0
        self._last_apps_mtime = None
        self._apps = []
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("ViceStartMenu")
        self.setObjectName("StartMenuPopup")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        root = QHBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        # 1. Left Favorites & Power Rail (Cinnamon-style)
        rail = _StyledWidget(self)
        rail.setObjectName("StartRail")
        rail.setFixedWidth(56)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(8, 10, 8, 10)
        rail_layout.setSpacing(6)

        cur_tools, tgt_tools = _read_registry_counts()
        pct_tools = int(round((cur_tools / max(1, tgt_tools)) * 100))
        pinned_rail = [
            (f"Vice Tool Hub ({cur_tools} / {tgt_tools} ({pct_tools}%))", ["python3 /opt/vice-os/vice_tool_hub.py"],
             ("vice-tool-hub", "view-app-grid"), "RailHubButton"),
            ("Visual Studio Code", ["code"], ("vice-tool-vscode", "code", "accessories-text-editor"), "RailButton"),
            ("Vice Office Studio", ["python3 /opt/vice-os/vice_tool_office_hub.py"],
             ("vice-tool-office-hub", "x-office-document"), "RailButton"),
            ("Vice Net Shield", ["python3 /opt/vice-os/vice_tool_net_shield.py"],
             ("vice-tool-net-shield", "network-vpn"), "RailButton"),
            ("Firefox", ["firefox-esr", "firefox"], ("firefox-esr", "firefox", "web-browser"), "RailButton"),
            ("Settings Center", ["python3 /opt/vice-os/vice_settings.py"], ("preferences-system", "settings"), "RailButton"),
            ("Terminal", ["xfce4-terminal", "xterm"], ("utilities-terminal", "terminal"), "RailButton"),
            ("Files", ["thunar", "pcmanfm"], ("system-file-manager", "folder"), "RailButton"),
        ]
        for tip, cmds, icons, obj_name in pinned_rail:
            btn = self._make_rail_button(tip, icons, obj_name=obj_name)
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
            logo_lbl.setPixmap(logo_icon.pixmap(24, 24))
        header_row.addWidget(logo_lbl)

        brand = QLabel("VICE OS · Leonida", main_area)
        brand.setFont(QFont("Noto Sans", 11, QFont.Bold))
        brand.setStyleSheet(f"color: {COLORS['text_primary']};")
        header_row.addWidget(brand)
        header_row.addStretch(1)

        self._hub_pill = QPushButton(f"Tool Hub · {cur_tools}/{tgt_tools}", main_area)
        self._hub_pill.setObjectName("StartHubPill")
        self._hub_pill.setFocusPolicy(Qt.NoFocus)
        self._hub_pill.setToolTip(
            f"Open Vice Tool Hub ({cur_tools} / {tgt_tools} ({pct_tools}%) GTA VI & Debian Tools)"
        )
        hub_ic = _theme_icon("vice-tool-hub", "view-app-grid")
        if not hub_ic.isNull():
            self._hub_pill.setIcon(hub_ic)
            self._hub_pill.setIconSize(QSize(16, 16))
        self._hub_pill.clicked.connect(lambda: self._run_and_hide(["python3 /opt/vice-os/vice_tool_hub.py"]))
        header_row.addWidget(self._hub_pill)
        main_layout.addLayout(header_row)

        self._search = QLineEdit(main_area)
        self._search.setPlaceholderText("Type to search apps, Vice tools, or settings...")
        self._search.textChanged.connect(self._populate_items)
        self._search.returnPressed.connect(self._launch_selected_or_first)
        main_layout.addWidget(self._search)

        esc_sc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc_sc.setContext(Qt.WidgetWithChildrenShortcut)
        esc_sc.activated.connect(self.hide)

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
        self._app_list.setIconSize(QSize(26, 26))
        self._app_list.itemClicked.connect(self._launch_item)
        self._app_list.installEventFilter(self)
        cols_layout.addWidget(self._app_list, 1)

        main_layout.addLayout(cols_layout, 1)
        root.addWidget(main_area, 1)

    def _make_rail_button(self, tooltip: str, icons: tuple, obj_name: str = "RailButton") -> QPushButton:
        btn = QPushButton(self)
        btn.setObjectName(obj_name)
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

    @staticmethod
    def _is_vice_tool(app_entry: dict) -> bool:
        app_id = str(app_entry.get("id", "")).lower()
        return app_id.startswith("vice-tool-")

    @staticmethod
    def _is_tool_hub(app_entry: dict) -> bool:
        app_id = str(app_entry.get("id", "")).lower()
        label = str(app_entry.get("label", "")).lower()
        return app_id in ("vice-tool-hub.desktop", "vice_tool_hub.py") or label == "vice tool hub"

    @staticmethod
    def _is_office_hub(app_entry: dict) -> bool:
        app_id = str(app_entry.get("id", "")).lower()
        label = str(app_entry.get("label", "")).lower()
        return app_id in ("vice-tool-office-hub.desktop", "vice_tool_office_hub.py") or label == "vice office studio"

    def _apps_dirs_mtime(self) -> float:
        dirs = getattr(_LAUNCHER_MODULE, "DESKTOP_APP_DIRS", ["/usr/share/applications"])
        latest = 0.0
        for d in dirs:
            if d and os.path.isdir(d):
                try:
                    latest = max(latest, os.stat(d).st_mtime)
                except OSError:
                    pass
        return latest

    def _map_app_category(self, app_entry: dict) -> str:
        raw_cat = app_entry.get("category", "Utilities")
        name_low = app_entry.get("label", "").lower()
        if any(k in name_low for k in ("ristretto", "image viewer", "screenshot", "feh")):
            return "Graphics"
        return self._CAT_REMAP.get(raw_cat, "Accessories")

    def reload_apps(self):
        if _LAUNCHER_MODULE is not None and hasattr(_LAUNCHER_MODULE, "discover_apps"):
            try:
                self._apps = _LAUNCHER_MODULE.discover_apps()
                self._last_apps_mtime = self._apps_dirs_mtime()
            except Exception as e:
                log_error(f"StartMenu: discover_apps failed: {e}")
                self._apps = []
        self._populate_items()

    def _make_app_list_item(self, app: dict) -> QListWidgetItem:
        icon_name = app.get("icon", "")
        if self._is_tool_hub(app) and not icon_name:
            icon_name = "vice-tool-hub"
        elif self._is_office_hub(app) and not icon_name:
            icon_name = "vice-tool-office-hub"
        icon = _theme_icon(icon_name, "application-x-executable", "applications-other")
        label = app.get("label", "")
        item = QListWidgetItem(icon, label)
        item.setData(Qt.UserRole, app)
        if self._is_tool_hub(app):
            cur_tools, tgt_tools = _read_registry_counts()
            bold_font = QFont("Noto Sans", 10, QFont.Bold)
            item.setFont(bold_font)
            item.setForeground(QColor(COLORS["accent_aqua"]))
            item.setToolTip(f"Featured: {app.get('comment') or f'Vice Tool Hub ({cur_tools}/{tgt_tools} GTA VI Tools)'}")
        elif self._is_office_hub(app):
            bold_font = QFont("Noto Sans", 10, QFont.Bold)
            item.setFont(bold_font)
            item.setForeground(QColor(COLORS["accent_gold"]))
            item.setToolTip(f"Featured: {app.get('comment') or 'Vice Office Studio (LibreOffice Suite)'}")
        else:
            item.setToolTip(app.get("comment") or label)
        return item

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

        matched = []
        for app in self._apps:
            mapped_cat = self._map_app_category(app)
            if not query:
                if selected_cat == "Vice Tools":
                    if not (self._is_vice_tool(app) or self._is_tool_hub(app)):
                        continue
                elif selected_cat not in ("All Applications", mapped_cat):
                    continue
            haystack = f"{app.get('label', '')} {app.get('name', '')} {app.get('comment', '')}".lower()
            if query and query not in haystack:
                continue
            matched.append(app)

        if not query and selected_cat in ("All Applications", "Vice Tools"):
            def _sort_key(entry: dict):
                if self._is_tool_hub(entry):
                    return (0, "")
                if self._is_office_hub(entry):
                    return (1, "")
                is_native = any("vice_tool_" in str(a) for a in entry.get("args", []))
                if selected_cat == "Vice Tools":
                    return (2 if is_native else 3, entry.get("label", "").lower())
                return (2, entry.get("label", "").lower())
            matched.sort(key=_sort_key)

        for app in matched:
            self._app_list.addItem(self._make_app_list_item(app))

        if self._app_list.count() > 0:
            self._app_list.setCurrentRow(0)

    def eventFilter(self, obj, event):
        if obj is self._app_list and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._launch_selected_or_first()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def _launch_selected_or_first(self):
        item = self._app_list.currentItem() or (self._app_list.item(0) if self._app_list.count() else None)
        if item:
            self._launch_item(item)

    def _launch_item(self, item: QListWidgetItem):
        now = time.monotonic()
        if now - self._last_launch_at < 0.25:
            return
        data = item.data(Qt.UserRole) or {}
        args = data.get("args", [])
        if not args:
            return
        self._last_launch_at = now
        self.hide()
        workdir = data.get("workdir") or os.path.expanduser("~")
        if not os.path.isdir(workdir):
            workdir = os.path.expanduser("~")
        ok = QProcess.startDetached(args[0], args[1:], workdir)
        if not ok:
            cmd_str = " ".join(shlex.quote(a) for a in args)
            log_error(f"StartMenu: QProcess.startDetached failed for {cmd_str}")
            launch_command(cmd_str)

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
        w = min(690, geo.width() - 24)
        h = min(540, geo.height() - pc.DOCK_HEIGHT - 20)
        self.setGeometry(geo.x() + 10, geo.y() + geo.height() - pc.DOCK_HEIGHT - h - 8, w, h)
        cur_tools, tgt_tools = _read_registry_counts()
        pct_tools = int(round((cur_tools / max(1, tgt_tools)) * 100))
        self._hub_pill.setText(f"Tool Hub · {cur_tools}/{tgt_tools}")
        self._hub_pill.setToolTip(
            f"Open Vice Tool Hub ({cur_tools} / {tgt_tools} ({pct_tools}%) GTA VI & Debian Tools)"
        )
        if not self._apps or self._apps_dirs_mtime() != self._last_apps_mtime:
            self.reload_apps()
        self._search.clear()
        self._cat_list.setCurrentRow(0)
        self._populate_items()
        self._opened_at = time.monotonic()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(40, self._search.setFocus)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            if not self._menu_open and self.isVisible():
                if time.monotonic() - self._opened_at < 0.30:
                    return
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
        self.input_field.setStyleSheet(
            f"border: 1px solid {COLORS['danger']}; color: {COLORS['danger']};"
        )
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


_AUDIO_CACHE = (85, False, False)


def _run_audio_cmd_async(cmd: list, timeout: float = 0.6) -> None:
    """Run an audio control command off the UI thread with bounded timeout."""
    def _runner():
        try:
            subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout
            )
        except Exception:
            pass

    threading.Thread(target=_runner, daemon=True).start()


def _get_audio_state() -> tuple:
    """Return (volume_pct, muted, available) via pactl with amixer fallback."""
    global _AUDIO_CACHE
    if shutil.which("pactl"):
        try:
            vol_out = subprocess.check_output(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                text=True, stderr=subprocess.DEVNULL, timeout=0.6
            )
            mute_out = subprocess.check_output(
                ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
                text=True, stderr=subprocess.DEVNULL, timeout=0.6
            )
            m = re.search(r"(\d+)%", vol_out)
            vol = int(m.group(1)) if m else 85
            muted = "yes" in mute_out.lower()
            _AUDIO_CACHE = (min(max(vol, 0), 100), muted, True)
            return _AUDIO_CACHE
        except Exception:
            pass
    if shutil.which("amixer"):
        try:
            out = subprocess.check_output(
                ["amixer", "sget", "Master"],
                text=True, stderr=subprocess.DEVNULL, timeout=0.6
            )
            m = re.search(r"\[(\d+)%\]", out)
            vol = int(m.group(1)) if m else 85
            muted = "[off]" in out.lower()
            _AUDIO_CACHE = (min(max(vol, 0), 100), muted, True)
            return _AUDIO_CACHE
        except Exception:
            pass
    _AUDIO_CACHE = (85, False, False)
    return _AUDIO_CACHE


def _set_audio_volume(pct: int) -> None:
    """Set default sink volume percentage via pactl with amixer fallback."""
    global _AUDIO_CACHE
    pct = min(max(int(pct), 0), 100)
    _, muted, avail = _AUDIO_CACHE
    _AUDIO_CACHE = (pct, muted, avail)
    if shutil.which("pactl"):
        _run_audio_cmd_async(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"])
    elif shutil.which("amixer"):
        _run_audio_cmd_async(["amixer", "sset", "Master", f"{pct}%", "unmute"])


def _adjust_audio_volume(delta: int) -> None:
    """Adjust default sink volume by signed *delta* percent via pactl/amixer."""
    global _AUDIO_CACHE
    vol, muted, avail = _AUDIO_CACHE
    target = min(max(vol + int(delta), 0), 100)
    _AUDIO_CACHE = (target, muted, avail)
    if shutil.which("pactl"):
        _run_audio_cmd_async(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{target}%"])
    elif shutil.which("amixer"):
        _run_audio_cmd_async(["amixer", "sset", "Master", f"{target}%", "unmute"])


def _toggle_audio_mute() -> None:
    """Toggle default sink mute via pactl with amixer fallback."""
    global _AUDIO_CACHE
    vol, muted, avail = _AUDIO_CACHE
    _AUDIO_CACHE = (vol, not muted, avail)
    if shutil.which("pactl"):
        _run_audio_cmd_async(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    elif shutil.which("amixer"):
        _run_audio_cmd_async(["amixer", "sset", "Master", "toggle"])


def _get_net_state() -> tuple:
    """Return (connected, kind, detail) using nmcli or sysfs net operstate."""
    if shutil.which("nmcli"):
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "dev"],
                text=True, stderr=subprocess.DEVNULL, timeout=0.6
            )
            for line in out.splitlines():
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                ntype, state, conn = parts[0].strip(), parts[1].strip().lower(), parts[2].strip()
                if ntype != "loopback" and state == "connected":
                    kind = "wifi" if "wifi" in ntype else "wired"
                    return (True, kind, conn or ntype)
        except Exception:
            pass
    net_dir = "/sys/class/net"
    if os.path.isdir(net_dir):
        try:
            for iface in sorted(os.listdir(net_dir)):
                if iface == "lo":
                    continue
                op_path = os.path.join(net_dir, iface, "operstate")
                if os.path.isfile(op_path):
                    with open(op_path, "r") as fp:
                        if fp.read().strip().lower() == "up":
                            kind = "wifi" if iface.startswith(("wl", "wifi")) else "wired"
                            return (True, kind, iface)
        except Exception:
            pass
    return (False, "offline", "Disconnected")


class VolumePopup(_StyledWidget):
    """Lightweight bottom-right popup for quick volume slider, mute toggle, and mixer launch."""

    _synced = pyqtSignal(int, bool, bool)

    def __init__(self, on_change_cb=None):
        super().__init__()
        self._on_change_cb = on_change_cb
        self.last_deactivated_at = 0.0
        self._updating_ui = False
        self._sync_busy = False
        self._synced.connect(self._apply_audio_state)
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("ViceVolumePopup")
        self.setObjectName("VolumePopup")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Audio Output", self)
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)
        self._pct_label = QLabel("85%", self)
        self._pct_label.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
        header.addWidget(self._pct_label)
        layout.addLayout(header)

        slider_row = QHBoxLayout()
        self._mute_btn = QPushButton("Mute", self)
        self._mute_btn.setObjectName("VolumeMuteButton")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFocusPolicy(Qt.NoFocus)
        self._mute_btn.clicked.connect(self._handle_mute)
        slider_row.addWidget(self._mute_btn)

        self._slider = QSlider(Qt.Horizontal, self)
        self._slider.setRange(0, 100)
        self._slider.setValue(85)
        self._slider.valueChanged.connect(self._handle_slider)
        slider_row.addWidget(self._slider, 1)
        layout.addLayout(slider_row)

        btn_row = QHBoxLayout()
        mixer_btn = QPushButton("Audio Mixer (pavucontrol)", self)
        mixer_btn.setFocusPolicy(Qt.NoFocus)
        mixer_btn.clicked.connect(self._open_mixer)
        btn_row.addWidget(mixer_btn)
        layout.addLayout(btn_row)

        esc_sc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc_sc.setContext(Qt.WidgetWithChildrenShortcut)
        esc_sc.activated.connect(self.hide)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def sync_from_system(self):
        vol, muted, avail = _AUDIO_CACHE
        self._apply_audio_state(vol, muted, avail)
        if self._sync_busy:
            return
        self._sync_busy = True

        def _probe():
            v, m, a = _get_audio_state()
            try:
                self._synced.emit(v, m, a)
            except RuntimeError:
                self._sync_busy = False

        threading.Thread(target=_probe, daemon=True).start()

    def _apply_audio_state(self, vol: int, muted: bool, avail: bool):
        self._sync_busy = False
        self._updating_ui = True
        try:
            self._slider.setValue(min(vol, 100))
            self._mute_btn.setChecked(muted)
            self._mute_btn.setText("Unmute" if muted else "Mute")
            if not avail:
                self._pct_label.setText("No sink")
            elif muted:
                self._pct_label.setText(f"{vol}% (Muted)")
            else:
                self._pct_label.setText(f"{vol}%")
        finally:
            self._updating_ui = False

    def _handle_slider(self, value: int):
        if self._updating_ui:
            return
        self._pct_label.setText(f"{value}%")
        _set_audio_volume(value)
        if self._on_change_cb:
            self._on_change_cb()

    def _handle_mute(self):
        if self._updating_ui:
            return
        _toggle_audio_mute()
        vol, muted, avail = _AUDIO_CACHE
        self._apply_audio_state(vol, muted, avail)
        QTimer.singleShot(140, self.sync_from_system)
        if self._on_change_cb:
            self._on_change_cb()

    def _open_mixer(self):
        self.hide()
        _launch_candidates(["pavucontrol", "python3 /opt/vice-os/vice_audio_manager.py"])

    def open_above(self, anchor_btn: QWidget):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        self.sync_from_system()
        geo = screen.geometry()
        pc = _pc()
        w, h = 296, 138
        btn_global = anchor_btn.mapToGlobal(anchor_btn.rect().topRight())
        x = min(max(geo.x() + 10, btn_global.x() - w), geo.x() + geo.width() - w - 10)
        y = geo.y() + geo.height() - pc.DOCK_HEIGHT - h - 8
        self.setGeometry(x, y, w, h)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.PopupFocusReason)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            if self.isVisible():
                self.last_deactivated_at = time.monotonic()
                self.hide()
        super().changeEvent(event)


class _VolumeButton(QPushButton):
    """Taskbar speaker button supporting scroll-wheel volume adjustments."""

    def __init__(self, parent=None, wheel_cb=None):
        super().__init__(parent)
        self._wheel_cb = wheel_cb

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0 and self._wheel_cb is not None:
            self._wheel_cb(5 if delta > 0 else -5)
            event.accept()
            return
        super().wheelEvent(event)


def _format_sysinfo(cpu_text: str, ram_text: str, disk_text: str, compact: bool = False) -> tuple:
    """Return (concise_taskbar_text, detailed_tooltip_text) for the sysinfo tray button."""
    full_parts = [p for p in (cpu_text, ram_text, disk_text) if p]
    full_tip = " · ".join(full_parts) + " — Click for Task Manager"

    cpu_m = re.search(r"(\d+%)", cpu_text or "")
    cpu_short = f"CPU {cpu_m.group(1)}" if cpu_m else (cpu_text or "CPU N/A")

    ram_m = re.search(r"(\d+)\s*MB\s*/\s*(\d+)\s*MB", ram_text or "")
    if ram_m:
        used_mb, total_mb = int(ram_m.group(1)), int(ram_m.group(2))
        if total_mb >= 1024:
            if compact:
                ram_short = f"{used_mb / 1024:.1f}/{total_mb / 1024:.1f}G"
            else:
                ram_short = f"RAM {used_mb / 1024:.1f}/{total_mb / 1024:.1f}G"
        else:
            ram_short = f"{used_mb}/{total_mb}M" if compact else f"RAM {used_mb}/{total_mb}M"
    else:
        ram_short = (ram_text or "").replace("RAM: ", "RAM ")

    disk_m = re.search(r"(\d+%)", disk_text or "")
    if disk_m:
        disk_short = disk_m.group(1) if compact else f"Disk {disk_m.group(1)}"
    else:
        disk_short = ""

    short_parts = [p for p in (cpu_short, ram_short, disk_short) if p]
    return (" · ".join(short_parts) or "Sys", full_tip)


class BottomTaskbar(_StyledWidget):
    """Unified Mint Cinnamon-style bottom panel: Start button, pinned icons, live taskbar, tray & clock."""

    _audio_updated = pyqtSignal(int, bool, bool)
    _net_updated = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self._disk_label = None
        self._battery_btn = None
        self._showing_desktop = False
        self._info_ticks = 0
        self._audio_probe_busy = False
        self._net_probe_busy = False
        self._last_clock_text = ""
        self._last_clock_tip = ""
        self._last_sysinfo_text = ""
        self._last_bat_text = ""
        self._last_tz_sig = self._localtime_sig()
        self._audio_updated.connect(self._apply_audio_indicator)
        self._net_updated.connect(self._apply_net_indicator)
        self._start_menu = StartMenuPopup(self.logout, self._run_power_action)
        self._volume_popup = VolumePopup(self._refresh_audio_indicator)
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
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        # 1. GTA VI x Debian Start Button (bottom-left)
        self.apps_btn = QPushButton("Menu", self)
        self.apps_btn.setObjectName("StartButton")
        self.apps_btn.setFocusPolicy(Qt.NoFocus)
        self.apps_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.apps_btn.setFixedHeight(34)
        self.apps_btn.setToolTip("Vice OS Start Menu (Windows Key)")
        logo_icon = _logo_icon()
        if not logo_icon.isNull():
            self.apps_btn.setIcon(logo_icon)
            self.apps_btn.setIconSize(QSize(20, 20))
        self.apps_btn.clicked.connect(self.toggle_start_menu)
        layout.addWidget(self.apps_btn)

        # 2. Pinned Quick-Launch Icons (Mint-style next to Start button)
        pinned_items = [
            ("Files", ["thunar", "pcmanfm"], ("folder", "system-file-manager")),
            ("Firefox", ["firefox-esr", "firefox"], ("firefox-esr", "firefox", "web-browser")),
            ("Terminal", ["xfce4-terminal", "xterm"], ("utilities-terminal", "terminal")),
            ("Vice Office Studio", ["python3 /opt/vice-os/vice_tool_office_hub.py", "libreoffice --writer"],
             ("vice-tool-office-hub", "x-office-document")),
            ("Vice Tool Hub", ["python3 /opt/vice-os/vice_tool_hub.py"], ("vice-tool-hub", "view-app-grid")),
        ]
        for tip, cmds, icon_names in pinned_items:
            pbtn = QPushButton(self)
            pbtn.setObjectName("PinButton")
            pbtn.setFocusPolicy(Qt.NoFocus)
            pbtn.setFixedSize(32, 32)
            pbtn.setToolTip(tip)
            picon = _theme_icon(*icon_names)
            if not picon.isNull():
                pbtn.setIcon(picon)
                pbtn.setIconSize(QSize(20, 20))
            else:
                pbtn.setText(tip[:2])
            pbtn.clicked.connect(lambda _=False, c=cmds: _launch_candidates(c))
            layout.addWidget(pbtn)

        # 3. Center: Live Taskbar window list
        self.taskbar = TaskbarWidget(self)
        layout.addWidget(self.taskbar, 1)

        # 4. Right Utility Tray: Metrics, Net, Audio, Battery, Clock, Show Desktop
        self.sysinfo = QPushButton("CPU 0% · RAM 0G", self)
        self.sysinfo.setObjectName("SysInfo")
        self.sysinfo.setFocusPolicy(Qt.NoFocus)
        self.sysinfo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.sysinfo.setFixedHeight(30)
        self.sysinfo.setMaximumWidth(235)
        self.sysinfo.setToolTip("Open Task Manager")
        self.sysinfo.clicked.connect(
            lambda: _launch_candidates(["xfce4-taskmanager", "python3 /opt/vice-os/vice_task_manager.py"])
        )
        layout.addWidget(self.sysinfo)

        self.net_btn = QPushButton(self)
        self.net_btn.setObjectName("QuickUtilButton")
        self.net_btn.setFocusPolicy(Qt.NoFocus)
        self.net_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.net_btn.setFixedHeight(30)
        self.net_btn.setToolTip("Network Connections")
        net_icon = _theme_icon("network-wired", "network-wireless")
        if not net_icon.isNull():
            self.net_btn.setIcon(net_icon)
            self.net_btn.setIconSize(QSize(16, 16))
            self.net_btn.setFixedSize(30, 30)
        else:
            self.net_btn.setText("Net")
            self.net_btn.setMaximumWidth(48)
        self.net_btn.clicked.connect(
            lambda: _launch_candidates(["nm-connection-editor", "python3 /opt/vice-os/vice_network_monitor.py"])
        )
        self.net_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.net_btn.customContextMenuRequested.connect(self._show_net_menu)
        QTimer.singleShot(600, self._refresh_net_indicator)
        layout.addWidget(self.net_btn)

        self.audio_btn = _VolumeButton(self, wheel_cb=self._on_audio_wheel)
        self.audio_btn.setObjectName("QuickUtilButton")
        self.audio_btn.setFocusPolicy(Qt.NoFocus)
        self.audio_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.audio_btn.setFixedHeight(30)
        self.audio_btn.clicked.connect(self.toggle_volume_popup)
        self.audio_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.audio_btn.customContextMenuRequested.connect(self._show_audio_menu)
        self._apply_audio_indicator(*_AUDIO_CACHE)
        QTimer.singleShot(500, self._refresh_audio_indicator)
        layout.addWidget(self.audio_btn)

        if _POWER_MODULE is not None:
            try:
                bat_text = _POWER_MODULE._read_battery_status()
                if bat_text != "AC":
                    self._battery_btn = QPushButton(bat_text, self)
                    self._battery_btn.setObjectName("BatteryButton")
                    self._battery_btn.setFocusPolicy(Qt.NoFocus)
                    self._battery_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    self._battery_btn.setFixedHeight(30)
                    self._battery_btn.setMaximumWidth(94)
                    b_icon = _battery_icon(bat_text)
                    if not b_icon.isNull():
                        self._battery_btn.setIcon(b_icon)
                        self._battery_btn.setIconSize(QSize(16, 16))
                    self._battery_btn.setToolTip(f"Battery: {bat_text} — Click for Power Manager")
                    self._battery_btn.clicked.connect(
                        lambda: launch_command("python3 /opt/vice-os/vice_power_manager.py")
                    )
                    layout.addWidget(self._battery_btn)
            except Exception as e:
                log_error(f"Failed to read battery status: {e}")

        self.clock = QPushButton("00:00", self)
        self.clock.setObjectName("Clock")
        self.clock.setFocusPolicy(Qt.NoFocus)
        self.clock.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clock.setFixedHeight(36)
        self.clock.setMinimumWidth(68)
        self.clock.setMaximumWidth(96)
        self.clock.setToolTip("World Clock & Host Time Sync — Click to open")
        self.clock.clicked.connect(
            lambda: _launch_candidates([
                "python3 /opt/vice-os/vice_tool_clock_sync.py",
                "python3 /opt/vice-os/vice_calendar.py",
            ])
        )
        layout.addWidget(self.clock)

        self.show_desk_btn = QPushButton(self)
        self.show_desk_btn.setObjectName("ShowDesktopButton")
        self.show_desk_btn.setCheckable(True)
        self.show_desk_btn.setFocusPolicy(Qt.NoFocus)
        self.show_desk_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.show_desk_btn.setFixedSize(26, 32)
        self.show_desk_btn.setIcon(_make_show_desktop_icon())
        self.show_desk_btn.setIconSize(QSize(16, 16))
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
        self._ipc_timer.setInterval(120)
        self._ipc_timer.timeout.connect(self._check_toggle_trigger)
        self._ipc_timer.start()

        # Pre-load app index shortly after startup for instant Start Menu opening
        QTimer.singleShot(800, self._start_menu.reload_apps)

    def _show_net_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Vice Net Shield (VPN / Tor / DNS)",
                       lambda: launch_command("python3 /opt/vice-os/vice_tool_net_shield.py"))
        menu.addSeparator()
        menu.addAction("Network Connections", lambda: _launch_candidates(["nm-connection-editor"]))
        menu.addAction("WiFi Connect", lambda: launch_command("python3 /opt/vice-os/vice_wifi_connect.py"))
        menu.addAction("Net Monitor", lambda: launch_command("python3 /opt/vice-os/vice_network_monitor.py"))
        menu.addAction("Leonida Net Radar", lambda: launch_command("python3 /opt/vice-os/vice_tool_net_radar.py"))
        menu.exec_(self.net_btn.mapToGlobal(pos))

    def _refresh_net_indicator(self):
        if self._net_probe_busy:
            return
        self._net_probe_busy = True

        def _probe():
            connected, kind, detail = _get_net_state()
            try:
                self._net_updated.emit(connected, kind, detail)
            except RuntimeError:
                self._net_probe_busy = False

        threading.Thread(target=_probe, daemon=True).start()

    def _apply_net_indicator(self, connected: bool, kind: str, detail: str):
        self._net_probe_busy = False
        if not connected:
            icon = _theme_icon("network-offline", "network-wired-disconnected", "network-wired")
            tip = "Network: Disconnected (Click for connections)"
        elif kind == "wifi":
            icon = _theme_icon("network-wireless", "network-wired")
            tip = f"Network: WiFi ({detail}) — Click for connections"
        else:
            icon = _theme_icon("network-wired", "network-wireless")
            tip = f"Network: Connected ({detail}) — Click for connections"
        if not icon.isNull():
            self.net_btn.setIcon(icon)
            self.net_btn.setIconSize(QSize(16, 16))
            self.net_btn.setFixedSize(30, 30)
            if self.net_btn.text():
                self.net_btn.setText("")
        if self.net_btn.toolTip() != tip:
            self.net_btn.setToolTip(tip)

    def _on_audio_wheel(self, delta: int):
        _adjust_audio_volume(delta)
        self._apply_audio_indicator(*_AUDIO_CACHE)
        QTimer.singleShot(180, self._refresh_audio_indicator)
        if self._volume_popup.isVisible():
            self._volume_popup.sync_from_system()

    def toggle_volume_popup(self):
        if self._volume_popup.isVisible():
            self._volume_popup.hide()
            return
        if time.monotonic() - self._volume_popup.last_deactivated_at < 0.25:
            return
        self._volume_popup.open_above(self.audio_btn)

    def _show_audio_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Mute / Unmute", lambda: (_toggle_audio_mute(), self._apply_audio_indicator(*_AUDIO_CACHE), QTimer.singleShot(180, self._refresh_audio_indicator)))
        menu.addAction("Volume +10%", lambda: self._on_audio_wheel(10))
        menu.addAction("Volume -10%", lambda: self._on_audio_wheel(-10))
        menu.addSeparator()
        menu.addAction("Open Audio Mixer (pavucontrol)",
                       lambda: _launch_candidates(["pavucontrol", "python3 /opt/vice-os/vice_audio_manager.py"]))
        menu.addAction("Open Vice Audio Manager",
                       lambda: launch_command("python3 /opt/vice-os/vice_audio_manager.py"))
        menu.exec_(self.audio_btn.mapToGlobal(pos))

    def _refresh_audio_indicator(self):
        if self._audio_probe_busy:
            return
        self._audio_probe_busy = True

        def _probe():
            vol, muted, avail = _get_audio_state()
            try:
                self._audio_updated.emit(vol, muted, avail)
            except RuntimeError:
                self._audio_probe_busy = False

        threading.Thread(target=_probe, daemon=True).start()

    def _apply_audio_indicator(self, vol: int, muted: bool, avail: bool):
        self._audio_probe_busy = False
        if not avail or muted or vol == 0:
            icon = _theme_icon("audio-volume-muted", "audio-volume-low", "multimedia-volume-control")
        elif vol < 35:
            icon = _theme_icon("audio-volume-low", "audio-volume-high", "multimedia-volume-control")
        elif vol < 75:
            icon = _theme_icon("audio-volume-medium", "audio-volume-high", "multimedia-volume-control")
        else:
            icon = _theme_icon("audio-volume-high", "multimedia-volume-control")
        if not icon.isNull():
            self.audio_btn.setIcon(icon)
            self.audio_btn.setIconSize(QSize(18, 18))
            self.audio_btn.setFixedSize(30, 30)
            if self.audio_btn.text():
                self.audio_btn.setText("")
        else:
            self.audio_btn.setMinimumWidth(0)
            self.audio_btn.setMaximumWidth(52)
            self.audio_btn.setText("Mute" if muted else f"{vol}%")
        status = "Muted" if muted else f"{vol}%"
        tip = f"Volume: {status} (Click: controls, Scroll: adjust, Right-click: mixer)" if avail else "Audio Mixer (pavucontrol)"
        if self.audio_btn.toolTip() != tip:
            self.audio_btn.setToolTip(tip)

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
        self._showing_desktop = not self._showing_desktop
        self.show_desk_btn.setChecked(self._showing_desktop)
        if shutil.which("wmctrl"):
            state = "on" if self._showing_desktop else "off"
            subprocess.Popen(["wmctrl", "-k", state],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("xdotool"):
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
        self.setFixedWidth(geo.width())
        self.setFixedHeight(h)
        self.setGeometry(geo.x(), geo.y() + geo.height() - h, geo.width(), h)
        if hasattr(self, "sysinfo"):
            self.sysinfo.setMaximumWidth(175 if geo.width() < 1120 else 235)
        if hasattr(self, "taskbar"):
            self.taskbar._update_button_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "taskbar"):
            self.taskbar._update_button_layout()

    @staticmethod
    def _localtime_sig():
        """Return (realpath, mtime_ns) of /etc/localtime to detect timezone changes."""
        lt_path = "/etc/localtime"
        try:
            st = os.stat(lt_path)
            return (os.path.realpath(lt_path), getattr(st, "st_mtime_ns", int(st.st_mtime)))
        except OSError:
            return ("", 0)

    def _sync_timezone_if_changed(self):
        """Reload C library timezone data via time.tzset() when /etc/localtime changes."""
        sig = self._localtime_sig()
        if sig != self._last_tz_sig:
            self._last_tz_sig = sig
            if hasattr(time, "tzset"):
                try:
                    time.tzset()
                except Exception as e:
                    log_error(f"time.tzset() failed: {e}")

    def update_info(self):
        self._sync_timezone_if_changed()
        clock_text = time.strftime("%H:%M\n%a %d/%m")
        if clock_text != self._last_clock_text:
            self._last_clock_text = clock_text
            self.clock.setText(clock_text)
        tz_name = time.tzname[time.daylight] if (time.daylight and len(time.tzname) > 1) else time.tzname[0]
        clock_tip = time.strftime(f"%A, %d %B %Y ({tz_name}) — Click for World Clock & Sync")
        if clock_tip != self._last_clock_tip:
            self._last_clock_tip = clock_tip
            self.clock.setToolTip(clock_tip)
        try:
            cpu_text = get_cpu_usage()
            ram_text = get_ram_usage()
            if self._disk_label is None:
                self._init_disk_label()
            compact = self.width() > 0 and self.width() < 1120
            sysinfo_text, sysinfo_tip = _format_sysinfo(
                cpu_text, ram_text, self._disk_label or "", compact=compact
            )
            layout_dirty = False
            if sysinfo_text != self._last_sysinfo_text:
                self._last_sysinfo_text = sysinfo_text
                self.sysinfo.setText(sysinfo_text)
                layout_dirty = True
            if self.sysinfo.toolTip() != sysinfo_tip:
                self.sysinfo.setToolTip(sysinfo_tip)
            if self._battery_btn is not None and _POWER_MODULE is not None:
                bat_text = _POWER_MODULE._read_battery_status()
                if bat_text != self._last_bat_text:
                    self._last_bat_text = bat_text
                    self._battery_btn.setText(bat_text)
                    b_icon = _battery_icon(bat_text)
                    if not b_icon.isNull():
                        self._battery_btn.setIcon(b_icon)
                        self._battery_btn.setIconSize(QSize(16, 16))
                    self._battery_btn.setToolTip(f"Battery: {bat_text} — Click for Power Manager")
                    layout_dirty = True
            if layout_dirty and self.layout() is not None:
                self.layout().activate()
                self.taskbar._update_button_layout()
        except Exception as e:
            log_error(f"Failed to update system info: {e}")
            self.sysinfo.setText("System info")
        self._info_ticks += 1
        if self._info_ticks % 5 == 0:
            self._refresh_audio_indicator()
            self._refresh_net_indicator()

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
    _configure_cjk_fonts(app)
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

        if _TRAY_MODULE is not None and shutil.which("stalonetray"):
            def _launch_systray():
                try:
                    _TRAY_MODULE.start_systray()
                except Exception as e:
                    log_error(f"Systray initialization failed: {e}")
            threading.Thread(target=_launch_systray, daemon=True).start()

    sys.exit(app.exec_())
