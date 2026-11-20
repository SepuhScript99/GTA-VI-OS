#!/usr/bin/env python3
"""
Vice OS Application Launcher — unified menu discovering standard XDG .desktop
applications and Vice OS utilities with categories, search, and favorites.
"""

import sys
import os
import glob
import json
import re
import shlex
import shutil

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QScrollArea, QGridLayout, QShortcut
)
from PyQt5.QtCore import Qt, QProcess, QSize
from PyQt5.QtGui import QFont, QIcon, QKeySequence

from python.vice_utils import log_info

WINDOW_WIDTH = 880
WINDOW_HEIGHT = 580

STYLE = """
QWidget { background-color: #0f121d; color: #e8eef8; font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; }
QLineEdit {
    background: #161b2a; color: #e8eef8; border: 1px solid #2b3552;
    border-radius: 10px; padding: 10px 14px; font-size: 14px;
}
QLineEdit:focus { border-color: #00e5ff; background: #1a2135; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #2e3957; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #00e5ff; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QPushButton#CategoryTab {
    background: #161b2a; color: #b7c3da; border: 1px solid #252e47;
    border-radius: 8px; padding: 4px 12px; font-size: 12px; font-weight: bold;
    min-width: 0px;
}
QPushButton#CategoryTab:hover { background: #1e273d; color: #ffffff; border-color: #00e5ff; }
QPushButton#CategoryTab:checked { background: #1b324a; color: #00e5ff; border-color: #00e5ff; }
QPushButton#AppCard {
    background: #151a2b; color: #e8eef8; border: 1px solid #252e47;
    border-radius: 10px; padding: 10px 8px; font-size: 12px; text-align: center;
}
QPushButton#AppCard:hover {
    background: #1d2942; color: #00e5ff; border-color: #00e5ff;
}
QLabel { color: #e8eef8; background: transparent; }
"""

CATEGORIES = {
    "Internet":    ["vice_network_monitor.py", "vice_vpn_manager.py", "vice_network_shares.py",
                    "vice_wifi_connect.py", "vice_ssh_manager.py", "vice_speedtest.py"],
    "Utilities":   ["vice_file_manager.py", "vice_text_editor.py", "vice_terminal.py",
                    "vice_screenshot.py", "vice_clipboard.py", "vice_archive_manager.py",
                    "vice_backup_scheduler.py", "vice_sysinfo_exporter.py",
                    "vice_calculator.py", "vice_calendar.py",
                    "vice_trash_manager.py", "vice_help_viewer.py",
                    "vice_file_search.py", "vice_checksum.py"],
    "Multimedia":  ["vice_audio_manager.py", "vice_font_manager.py", "vice_image_viewer.py",
                    "vice_media_player.py", "vice_pdf_viewer.py", "vice_screen_recorder.py"],
    "Office":      [],
    "Development": ["vice_software_center.py", "vice_package_search.py", "vice_iso_validator.py",
                    "vice_diagnostics.py", "vice_log_viewer.py", "vice_log_rotation.py",
                    "vice_cron_manager.py"],
    "System":      ["vice_task_manager.py", "vice_system_monitor.py", "vice_system_report.py",
                    "vice_service_manager.py", "vice_power_manager.py", "vice_driver_manager.py",
                    "vice_update_manager.py", "vice_kernel_manager.py", "vice_cleanup.py",
                    "vice_session_manager.py", "vice_disk_benchmark.py", "vice_disk_manager.py",
                    "vice_disk_usage.py", "vice_user_manager.py", "vice_usb_manager.py",
                    "vice_printer_manager.py", "vice_bluetooth_manager.py", "vice_firewall_manager.py"],
    "Settings":    ["vice_settings.py", "vice_display_manager.py", "vice_keyboard_shortcuts.py",
                    "vice_mouse_settings.py", "vice_accessibility.py", "vice_theme_manager.py",
                    "vice_openbox_editor.py", "vice_startup_apps.py", "vice_wallpaper_picker.py",
                    "vice_notif_history.py"],
}

_XDG_CATEGORY_MAP = {
    "Network": "Internet",
    "WebBrowser": "Internet",
    "Email": "Internet",
    "InstantMessaging": "Internet",
    "AudioVideo": "Multimedia",
    "Audio": "Multimedia",
    "Video": "Multimedia",
    "Graphics": "Multimedia",
    "Office": "Office",
    "Development": "Development",
    "IDE": "Development",
    "System": "System",
    "Monitor": "System",
    "Settings": "Settings",
    "DesktopSettings": "Settings",
    "HardwareSettings": "Settings",
    "Utility": "Utilities",
    "Accessories": "Utilities",
    "FileManager": "Utilities",
    "TerminalEmulator": "Utilities",
    "TextEditor": "Utilities",
}

_EXCLUDED_VICE_SCRIPTS = {
    "vice_notification_daemon.py",
    "vice_system_notifier.py",
    "vice_panel.py",
    "vice_launcher.py",
    "vice_clipboard_manager.py",
    "vice_setup_apps.py",
    "vice_shell.py",
}

APP_LABELS = {
    "vice_settings.py":          ("Settings Center",     "preferences-system"),
    "vice_task_manager.py":      ("Task Manager",        "utilities-system-monitor"),
    "vice_system_monitor.py":    ("System Monitor",      "utilities-system-monitor"),
    "vice_system_report.py":     ("System Report",       "dialog-information"),
    "vice_service_manager.py":   ("Service Manager",     "system-run"),
    "vice_power_manager.py":     ("Power Manager",       "battery"),
    "vice_driver_manager.py":    ("Driver Manager",      "preferences-desktop"),
    "vice_update_manager.py":    ("Update Manager",      "system-software-update"),
    "vice_file_manager.py":      ("Vice Files",          "system-file-manager"),
    "vice_text_editor.py":       ("Vice Editor",         "accessories-text-editor"),
    "vice_terminal.py":          ("Vice Terminal",       "utilities-terminal"),
    "vice_screenshot.py":        ("Screenshot",          "applets-screenshooter"),
    "vice_clipboard.py":         ("Clipboard",           "edit-paste"),
    "vice_archive_manager.py":   ("Archive Manager",     "package-x-generic"),
    "vice_audio_manager.py":     ("Audio Manager",       "audio-volume-high"),
    "vice_font_manager.py":      ("Font Manager",        "preferences-desktop-font"),
    "vice_display_manager.py":   ("Display Manager",     "preferences-desktop-display"),
    "vice_disk_manager.py":      ("Disk Manager",        "drive-harddisk"),
    "vice_bluetooth_manager.py": ("Bluetooth",           "bluetooth"),
    "vice_firewall_manager.py":  ("Firewall",            "security-high"),
    "vice_software_center.py":   ("Software Center",     "system-software-install"),
    "vice_package_search.py":    ("Package Search",      "system-search"),
    "vice_iso_validator.py":     ("ISO Validator",       "media-optical"),
    "vice_diagnostics.py":       ("Diagnostics",         "utilities-system-monitor"),
    "vice_user_manager.py":      ("User Manager",        "system-users"),
    "vice_notif_history.py":     ("Notifications",       "preferences-desktop-notification"),
    "vice_keyboard_shortcuts.py": ("Keyboard",           "input-keyboard"),
    "vice_mouse_settings.py":    ("Mouse & Touchpad",    "input-mouse"),
    "vice_accessibility.py":     ("Accessibility",       "preferences-desktop-accessibility"),
    "vice_usb_manager.py":       ("USB Manager",         "drive-removable-media"),
    "vice_vpn_manager.py":       ("VPN Manager",         "network-vpn"),
    "vice_network_shares.py":    ("Network Shares",      "folder-remote"),
    "vice_backup_scheduler.py":  ("Backup Jobs",         "document-save"),
    "vice_log_rotation.py":      ("Log Rotation",        "utilities-log-viewer"),
    "vice_log_viewer.py":        ("Log Viewer",          "utilities-log-viewer"),
    "vice_sysinfo_exporter.py":  ("Info Export",         "document-export"),
    "vice_printer_manager.py":   ("Printer",             "printer"),
    "vice_theme_manager.py":     ("Theme Manager",       "preferences-desktop-theme"),
    "vice_openbox_editor.py":    ("Openbox Editor",      "preferences-system-windows"),
    "vice_calendar.py":          ("Calendar",            "x-office-calendar"),
    "vice_calculator.py":        ("Vice Calculator",     "accessories-calculator"),
    "vice_image_viewer.py":      ("Vice Image Viewer",   "image-x-generic"),
    "vice_startup_apps.py":      ("Startup Apps",        "preferences-system"),
    "vice_media_player.py":      ("Vice Media Player",   "multimedia-player"),
    "vice_file_search.py":       ("File Search",         "edit-find"),
    "vice_disk_usage.py":        ("Disk Usage",          "drive-harddisk"),
    "vice_cron_manager.py":      ("Cron Jobs",           "appointment-new"),
    "vice_pdf_viewer.py":        ("Vice PDF Viewer",     "application-pdf"),
    "vice_wifi_connect.py":      ("WiFi Connect",        "network-wireless"),
    "vice_ssh_manager.py":       ("SSH Manager",         "network-server"),
    "vice_screen_recorder.py":   ("Screen Recorder",     "camera-video"),
    "vice_checksum.py":          ("Checksum",            "dialog-ok"),
    "vice_wallpaper_picker.py":  ("Wallpapers",          "preferences-desktop-wallpaper"),
    "vice_kernel_manager.py":    ("Kernel Manager",      "applications-system"),
    "vice_cleanup.py":           ("System Cleanup",      "edit-clear"),
    "vice_network_monitor.py":   ("Net Monitor",         "network-wired"),
    "vice_trash_manager.py":     ("Trash",               "user-trash"),
    "vice_help_viewer.py":       ("Vice Help",           "help-browser"),
    "vice_speedtest.py":         ("Speed Test",          "network-transmit-receive"),
    "vice_disk_benchmark.py":    ("Disk Benchmark",      "drive-harddisk"),
}

FAVORITES_FILE = os.path.expanduser("~/.config/vice-os/favorites.json")
DESKTOP_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_APP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
]

_VICE_CAT_LOOKUP = {
    fname: cat
    for cat, files in CATEGORIES.items()
    for fname in files
}


def load_favorites():
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return [
        "Firefox ESR",
        "Thunar File Manager",
        "Xfce Terminal",
        "Mousepad",
        "Settings Center",
    ]


def save_favorites(favs):
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    try:
        with open(FAVORITES_FILE, "w") as f:
            json.dump(favs, f)
    except Exception:
        pass


def _parse_xdg_desktop_file(filepath: str):
    """Parse an XDG .desktop entry and return a unified launcher app dict or None."""
    name = None
    exec_cmd = None
    icon = "application-x-executable"
    comment = ""
    cats = []
    terminal = False
    is_app = True

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            in_main = False
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("["):
                    if line == "[Desktop Entry]":
                        in_main = True
                        continue
                    if in_main:
                        break
                    continue
                if not in_main or "=" not in line:
                    continue

                key, val = line.split("=", 1)
                if key == "Name":
                    name = val.strip()
                elif key == "Exec":
                    cleaned = re.sub(r"%[a-zA-Z]", "", val)
                    exec_cmd = re.sub(r"\s+", " ", cleaned).strip()
                elif key == "Icon":
                    icon = val.strip() or icon
                elif key == "Comment":
                    comment = val.strip()
                elif key == "Categories":
                    cats = [c.strip() for c in val.split(";") if c.strip()]
                elif key == "NoDisplay" and val.strip().lower() == "true":
                    return None
                elif key == "Hidden" and val.strip().lower() == "true":
                    return None
                elif key == "Type" and val.strip() != "Application":
                    is_app = False
                elif key == "Terminal":
                    terminal = val.strip().lower() == "true"
                elif key == "TryExec":
                    try_bin = val.strip()
                    if try_bin and shutil.which(try_bin) is None:
                        return None
    except Exception:
        return None

    if not is_app or not name or not exec_cmd:
        return None

    try:
        args = shlex.split(exec_cmd)
    except ValueError:
        args = exec_cmd.split()
    if not args:
        return None

    if terminal:
        term_bin = shutil.which("xfce4-terminal") or "xterm"
        args = [term_bin, "-e"] + args

    category = "Utilities"
    for xdg_cat in cats:
        if xdg_cat in _XDG_CATEGORY_MAP:
            category = _XDG_CATEGORY_MAP[xdg_cat]
            break

    return {
        "id": os.path.basename(filepath),
        "name": os.path.basename(filepath),
        "label": name,
        "icon": icon,
        "comment": comment or name,
        "category": category,
        "args": args,
    }


def discover_apps(desktop_app_dirs=None, include_vice_scripts: bool = True) -> list:
    """Discover both standard XDG .desktop apps and curated Vice OS utilities."""
    apps = []
    seen_labels = set()

    dirs = DESKTOP_APP_DIRS if desktop_app_dirs is None else desktop_app_dirs
    for app_dir in dirs:
        if not app_dir or not os.path.isdir(app_dir):
            continue
        for filepath in sorted(glob.glob(os.path.join(app_dir, "*.desktop"))):
            entry = _parse_xdg_desktop_file(filepath)
            if not entry:
                continue
            key = entry["label"].lower()
            if key in seen_labels:
                continue
            seen_labels.add(key)
            apps.append(entry)

    if include_vice_scripts:
        for path in sorted(glob.glob(os.path.join(DESKTOP_DIR, "vice_*.py"))):
            name = os.path.basename(path)
            if name in _EXCLUDED_VICE_SCRIPTS:
                continue
            default_label = name.replace("vice_", "").replace(".py", "").replace("_", " ").title()
            label, icon = APP_LABELS.get(name, (default_label, "applications-other"))
            if label.lower() in seen_labels:
                continue
            seen_labels.add(label.lower())
            apps.append({
                "id": name,
                "name": name,
                "label": label,
                "icon": icon,
                "comment": label,
                "category": _VICE_CAT_LOOKUP.get(name, "Utilities"),
                "args": [sys.executable, path],
            })

    apps.sort(key=lambda item: item["label"].lower())
    return apps


def _load_card_icon(icon_name: str) -> QIcon:
    """Resolve an icon from filesystem path or Freedesktop icon theme."""
    if icon_name and os.path.isfile(icon_name):
        return QIcon(icon_name)
    for candidate in (icon_name, "application-x-executable", "applications-other"):
        if candidate:
            icon = QIcon.fromTheme(candidate)
            if not icon.isNull():
                return icon
    return QIcon()


class AppButton(QPushButton):
    def __init__(self, app_info, on_launch, on_fav_toggle, is_fav=False):
        super().__init__()
        self._info = app_info
        self._is_fav = is_fav
        self.setObjectName("AppCard")
        self.setFocusPolicy(Qt.NoFocus)

        label = app_info["label"]
        if len(label) > 18:
            display_label = label[:17] + "…"
        else:
            display_label = label

        self.setText(display_label)
        self.setToolTip(f"{label}\n{app_info.get('comment', '')}".strip())
        self.setMinimumSize(148, 80)
        self.setMaximumWidth(172)

        icon = _load_card_icon(app_info.get("icon", ""))
        if not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(QSize(24, 24))

        self.clicked.connect(lambda: on_launch(app_info))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda _pos, a=app_info: on_fav_toggle(a)
        )


class AppLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Applications")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(680, 460)
        self.setStyleSheet(STYLE)
        self._apps = discover_apps()
        self._favorites = load_favorites()
        self._category = "All"
        self._cat_buttons = {}
        self._init_ui()
        self._populate()
        self._search.setFocus()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 14, 16, 14)

        header = QHBoxLayout()
        title = QLabel("Applications")
        title.setFont(QFont("Noto Sans", 18, QFont.Bold))
        title.setStyleSheet("color: #00e5ff;")
        header.addWidget(title)
        header.addStretch(1)
        hint = QLabel("Right-click card to pin/unpin Favorites · Esc to close")
        hint.setStyleSheet("color: #7c87a3; font-size: 11px;")
        header.addWidget(hint)
        root.addLayout(header)

        # Live Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search Debian & Vice OS apps...")
        self._search.textChanged.connect(self._populate)
        root.addWidget(self._search)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

        # Category bar (clean fixed height 32, zero clipped text)
        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        for cat in ["All", "Favorites"] + list(CATEGORIES.keys()):
            btn = QPushButton(cat)
            btn.setObjectName("CategoryTab")
            btn.setFixedHeight(32)
            btn.setCheckable(True)
            btn.setChecked(cat == "All")
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _checked=False, c=cat: self._set_category(c))
            cat_row.addWidget(btn)
            self._cat_buttons[cat] = btn
        cat_row.addStretch(1)
        root.addLayout(cat_row)

        # App grid (vertical scroll only, never clips columns horizontally)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll, 1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #8c96b2; font-size: 11px;")
        root.addWidget(self._count_label)

    def _set_category(self, cat):
        self._category = cat
        for name, btn in self._cat_buttons.items():
            btn.setChecked(name == cat)
        self._populate()

    def _populate(self):
        while self._grid_layout.count():
            w = self._grid_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        search = self._search.text().strip().lower()
        filtered = []

        for app in self._apps:
            is_fav = app["label"] in self._favorites or app["name"] in self._favorites
            if self._category == "Favorites" and not is_fav:
                continue
            if self._category not in ("All", "Favorites") and app.get("category") != self._category:
                continue

            haystack = f"{app['label']} {app['name']} {app.get('comment', '')}".lower()
            if search and search not in haystack:
                continue
            filtered.append(app)

        cols = 5
        for i, app in enumerate(filtered):
            is_fav = app["label"] in self._favorites or app["name"] in self._favorites
            btn = AppButton(app, self._launch, self._toggle_fav, is_fav)
            row, col = divmod(i, cols)
            self._grid_layout.addWidget(btn, row, col)

        self._count_label.setText(f"{len(filtered)} application(s)")

    def _launch(self, app_info):
        args = app_info.get("args", [])
        if not args:
            return
        log_info(f"Launching: {' '.join(args)}")
        QProcess.startDetached(args[0], args[1:], DESKTOP_DIR)
        self.close()

    def _toggle_fav(self, app_info):
        key = app_info["label"]
        if key in self._favorites:
            self._favorites.remove(key)
        elif app_info["name"] in self._favorites:
            self._favorites.remove(app_info["name"])
        else:
            self._favorites.append(key)
        save_favorites(self._favorites)
        self._populate()


def main():
    app = QApplication(sys.argv)
    win = AppLauncher()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
