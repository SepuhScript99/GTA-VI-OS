#!/usr/bin/env python3
"""
Vice OS Application Launcher — unified menu discovering standard XDG .desktop
applications and Vice OS utilities with categories, search, and favorites.
"""

import glob
import json
import os
import re
import shlex
import shutil
import sys

from PyQt5.QtCore import QProcess, QSize, Qt
from PyQt5.QtGui import QFont, QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    FlowLayout,
    build_app_qss,
    configure_cjk_fonts,
    configure_icon_theme,
    resolve_icon,
)

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600

_c = COLORS
STYLE = build_app_qss(
    f"""
QPushButton#CategoryTab {{
    background: {_c['bg_surface']};
    color: {_c['text_secondary']};
    border: 1px solid {_c['border']};
    border-radius: 8px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
    min-width: 0px;
}}
QPushButton#CategoryTab:hover {{
    background: {_c['bg_elevated']};
    color: {_c['text_primary']};
    border-color: {_c['border_strong']};
}}
QPushButton#CategoryTab:checked {{
    background: {_c['bg_active']};
    color: {_c['accent_peach']};
    border-color: {_c['accent_coral']};
}}
QPushButton#AppCard {{
    background: {_c['bg_surface']};
    color: {_c['text_primary']};
    border: 1px solid {_c['border']};
    border-radius: 10px;
    padding: 0px;
    font-size: 12px;
    text-align: center;
}}
QPushButton#AppCard:hover {{
    background: {_c['bg_elevated']};
    color: {_c['accent_peach']};
    border-color: {_c['border_strong']};
}}
"""
)

CATEGORIES = {
    "Internet": ["vice_network_monitor.py", "vice_vpn_manager.py", "vice_network_shares.py",
                 "vice_wifi_connect.py", "vice_ssh_manager.py", "vice_speedtest.py",
                 "vice_tool_net_shield.py", "vice_tool_net_radar.py"],
    "Utilities": ["vice_file_manager.py", "vice_text_editor.py", "vice_terminal.py",
                  "vice_screenshot.py", "vice_clipboard.py", "vice_archive_manager.py",
                  "vice_backup_scheduler.py", "vice_sysinfo_exporter.py",
                  "vice_calculator.py", "vice_calendar.py", "vice_tool_clock_sync.py",
                  "vice_trash_manager.py", "vice_help_viewer.py",
                  "vice_file_search.py", "vice_checksum.py"],
    "Multimedia": ["vice_audio_manager.py", "vice_font_manager.py", "vice_image_viewer.py",
                   "vice_media_player.py", "vice_pdf_viewer.py", "vice_screen_recorder.py",
                   "vice_tool_radio.py", "vice_tool_media_studio.py"],
    "Graphics": [],
    "Office": ["vice_tool_office_hub.py", "vice_tool_missions.py"],
    "Development": ["vice_software_center.py", "vice_package_search.py", "vice_iso_validator.py",
                    "vice_diagnostics.py", "vice_log_viewer.py", "vice_log_rotation.py",
                    "vice_cron_manager.py", "vice_tool_qr_hash.py", "vice_tool_cheatsheets.py"],
    "Security": ["vice_tool_cyber_deck.py", "vice_tool_mac_cloak.py", "vice_tool_vault.py",
                 "vice_firewall_manager.py"],
    "System": ["vice_task_manager.py", "vice_system_monitor.py", "vice_system_report.py",
               "vice_service_manager.py", "vice_power_manager.py", "vice_driver_manager.py",
               "vice_update_manager.py", "vice_kernel_manager.py", "vice_cleanup.py",
               "vice_session_manager.py", "vice_disk_benchmark.py", "vice_disk_manager.py",
               "vice_disk_usage.py", "vice_user_manager.py", "vice_usb_manager.py",
               "vice_printer_manager.py", "vice_bluetooth_manager.py",
               "vice_tool_hub.py", "vice_tool_turbo.py", "vice_tool_sys_deck.py"],
    "Settings": ["vice_settings.py", "vice_display_manager.py", "vice_keyboard_shortcuts.py",
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
    "Graphics": "Graphics",
    "Photography": "Graphics",
    "RasterGraphics": "Graphics",
    "2DGraphics": "Graphics",
    "Office": "Office",
    "Development": "Development",
    "IDE": "Development",
    "Security": "Security",
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
    "vice_theme.py",
}

APP_LABELS = {
    "vice_settings.py": ("Settings Center", "preferences-system"),
    "vice_task_manager.py": ("Task Manager", "utilities-system-monitor"),
    "vice_system_monitor.py": ("System Monitor", "utilities-system-monitor"),
    "vice_system_report.py": ("System Report", "dialog-information"),
    "vice_service_manager.py": ("Service Manager", "system-run"),
    "vice_power_manager.py": ("Power Manager", "battery"),
    "vice_driver_manager.py": ("Driver Manager", "preferences-desktop"),
    "vice_update_manager.py": ("Update Manager", "system-software-update"),
    "vice_file_manager.py": ("Vice Files", "system-file-manager"),
    "vice_text_editor.py": ("Vice Editor", "accessories-text-editor"),
    "vice_terminal.py": ("Vice Terminal", "utilities-terminal"),
    "vice_screenshot.py": ("Screenshot", "applets-screenshooter"),
    "vice_clipboard.py": ("Clipboard", "edit-paste"),
    "vice_archive_manager.py": ("Archive Manager", "package-x-generic"),
    "vice_audio_manager.py": ("Audio Manager", "audio-volume-high"),
    "vice_font_manager.py": ("Font Manager", "preferences-desktop-font"),
    "vice_display_manager.py": ("Display Manager", "preferences-desktop-display"),
    "vice_disk_manager.py": ("Disk Manager", "drive-harddisk"),
    "vice_bluetooth_manager.py": ("Bluetooth", "bluetooth"),
    "vice_firewall_manager.py": ("Firewall", "security-high"),
    "vice_software_center.py": ("Software Center", "system-software-install"),
    "vice_package_search.py": ("Package Search", "system-search"),
    "vice_iso_validator.py": ("ISO Validator", "media-optical"),
    "vice_diagnostics.py": ("Diagnostics", "utilities-system-monitor"),
    "vice_user_manager.py": ("User Manager", "system-users"),
    "vice_notif_history.py": ("Notifications", "preferences-desktop-notification"),
    "vice_keyboard_shortcuts.py": ("Keyboard", "input-keyboard"),
    "vice_mouse_settings.py": ("Mouse & Touchpad", "input-mouse"),
    "vice_accessibility.py": ("Accessibility", "preferences-desktop-accessibility"),
    "vice_usb_manager.py": ("USB Manager", "drive-removable-media"),
    "vice_vpn_manager.py": ("VPN Manager", "network-vpn"),
    "vice_network_shares.py": ("Network Shares", "folder-remote"),
    "vice_backup_scheduler.py": ("Backup Jobs", "document-save"),
    "vice_log_rotation.py": ("Log Rotation", "utilities-log-viewer"),
    "vice_log_viewer.py": ("Log Viewer", "utilities-log-viewer"),
    "vice_sysinfo_exporter.py": ("Info Export", "document-export"),
    "vice_printer_manager.py": ("Printer", "printer"),
    "vice_theme_manager.py": ("Theme Manager", "preferences-desktop-theme"),
    "vice_openbox_editor.py": ("Openbox Editor", "preferences-system-windows"),
    "vice_calendar.py": ("Calendar", "x-office-calendar"),
    "vice_calculator.py": ("Vice Calculator", "accessories-calculator"),
    "vice_image_viewer.py": ("Vice Image Viewer", "image-x-generic"),
    "vice_startup_apps.py": ("Startup Apps", "preferences-system"),
    "vice_media_player.py": ("Vice Media Player", "multimedia-player"),
    "vice_file_search.py": ("File Search", "edit-find"),
    "vice_disk_usage.py": ("Disk Usage", "drive-harddisk"),
    "vice_cron_manager.py": ("Cron Jobs", "appointment-new"),
    "vice_pdf_viewer.py": ("Vice PDF Viewer", "application-pdf"),
    "vice_wifi_connect.py": ("WiFi Connect", "network-wireless"),
    "vice_ssh_manager.py": ("SSH Manager", "network-server"),
    "vice_screen_recorder.py": ("Screen Recorder", "camera-video"),
    "vice_checksum.py": ("Checksum", "dialog-ok"),
    "vice_wallpaper_picker.py": ("Wallpapers", "preferences-desktop-wallpaper"),
    "vice_kernel_manager.py": ("Kernel Manager", "applications-system"),
    "vice_cleanup.py": ("System Cleanup", "edit-clear"),
    "vice_network_monitor.py": ("Net Monitor", "network-wired"),
    "vice_trash_manager.py": ("Trash", "user-trash"),
    "vice_help_viewer.py": ("Vice Help", "help-browser"),
    "vice_speedtest.py": ("Speed Test", "network-transmit-receive"),
    "vice_disk_benchmark.py": ("Disk Benchmark", "drive-harddisk"),
    "vice_tool_hub.py": ("Vice Tool Hub", "vice-tool-hub"),
    "vice_tool_radio.py": ("Leonida FM Radio", "vice-tool-radio"),
    "vice_tool_net_radar.py": ("Leonida Net Radar", "vice-tool-net-radar"),
    "vice_tool_missions.py": ("Vice Mission Board", "vice-tool-missions"),
    "vice_tool_vault.py": ("Vice Vault", "vice-tool-vault"),
    "vice_tool_turbo.py": ("Vice Turbo Mode", "vice-tool-turbo"),
    "vice_tool_media_studio.py": ("Vice Media Studio", "vice-tool-media-studio"),
    "vice_tool_qr_hash.py": ("Vice QR & Dev Lab", "vice-tool-qr-hash"),
    "vice_tool_sys_deck.py": ("Vice Hardware Deck", "vice-tool-sys-deck"),
    "vice_tool_cheatsheets.py": ("Vice Command Deck", "vice-tool-cheatsheets"),
    "vice_tool_net_shield.py": ("Vice Net Shield", "vice-tool-net-shield"),
    "vice_tool_cyber_deck.py": ("Vice Cyber Deck", "vice-tool-cyber-deck"),
    "vice_tool_mac_cloak.py": ("Vice Identity Cloak", "vice-tool-mac-cloak"),
    "vice_tool_office_hub.py": ("Vice Office Studio", "vice-tool-office-hub"),
    "vice_tool_clock_sync.py": ("Vice World Clock", "vice-tool-clock-sync"),
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
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return [
        "Firefox ESR",
        "Thunar File Manager",
        "Xfce Terminal",
        "Vice Office Studio",
        "Vice Tool Hub",
        "Settings Center",
    ]


def save_favorites(favs):
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
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
    workdir = ""
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
                elif key == "Path":
                    workdir = val.strip()
                elif key == "Categories":
                    cats = [c.strip() for c in val.split(";") if c.strip()]
                elif key == "NoDisplay" and val.strip().lower() == "true":
                    return None
                elif key == "Hidden" and val.strip().lower() == "true":
                    return None
                elif key == "OnlyShowIn":
                    envs = {e.strip().upper() for e in val.split(";") if e.strip()}
                    if envs and not (envs & {"OPENBOX", "XFCE", "LXDE", "GTK"}):
                        return None
                elif key == "NotShowIn":
                    envs = {e.strip().upper() for e in val.split(";") if e.strip()}
                    if "OPENBOX" in envs:
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
        args = [a for a in shlex.split(exec_cmd) if a != ""]
    except ValueError:
        args = [a for a in exec_cmd.split() if a != ""]
    if not args:
        return None
    if args[0] == "su-to-root" and shutil.which("su-to-root") is None:
        return None
    if os.path.isabs(args[0]) and not os.path.exists(args[0]):
        return None

    if terminal:
        term_bin = shutil.which("xfce4-terminal") or shutil.which("x-terminal-emulator") or "xterm"
        if "xfce4-terminal" in os.path.basename(term_bin):
            args = [term_bin, "-x"] + args
        else:
            args = [term_bin, "-e", " ".join(shlex.quote(a) for a in args)]

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
        "workdir": workdir,
    }


def _exec_dedup_key(entry: dict):
    """Return canonical command tuple for deduplicating stock .desktop vs vice-tool-*.desktop."""
    args = entry.get("args") or []
    if not args:
        return None
    if args[0] == "su-to-root" and shutil.which("su-to-root") is None:
        return None
    if os.path.isabs(args[0]) and not os.path.exists(args[0]):
        return None
    head = os.path.basename(args[0]).lower()
    if head == "vice-run-tool" and len(args) >= 3:
        cmd_tokens = [os.path.basename(args[2]).lower()] + [a.lower() for a in args[3:]]
        return tuple(cmd_tokens)
    if head in ("python3", "python") and len(args) >= 2:
        return ("py", os.path.basename(args[1]).lower())
    if head in ("xfce4-terminal", "xterm") and len(args) >= 3 and args[1] in ("-x", "-e"):
        return tuple([os.path.basename(args[2]).lower()] + [a.lower() for a in args[3:]])
    return tuple([head] + [a.lower() for a in args[1:]])


def discover_apps(desktop_app_dirs=None, include_vice_scripts: bool = True) -> list:
    """Discover both standard XDG .desktop apps and curated Vice OS utilities."""
    apps = []
    seen_labels = set()
    seen_execs = {}
    seen_vice_scripts = set()

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
            exec_key = _exec_dedup_key(entry)
            is_vice_tool = entry["id"].startswith("vice-tool-")
            if exec_key and exec_key in seen_execs:
                existing_idx = seen_execs[exec_key]
                existing_is_vice = apps[existing_idx]["id"].startswith("vice-tool-")
                if is_vice_tool and not existing_is_vice:
                    seen_labels.discard(apps[existing_idx]["label"].lower())
                    seen_labels.add(key)
                    apps[existing_idx] = entry
                continue
            seen_labels.add(key)
            if exec_key:
                seen_execs[exec_key] = len(apps)
            for arg in entry.get("args", []):
                base = os.path.basename(arg)
                if base.startswith("vice_") and base.endswith(".py"):
                    seen_vice_scripts.add(base)
            apps.append(entry)

    if include_vice_scripts:
        for path in sorted(glob.glob(os.path.join(DESKTOP_DIR, "vice_*.py"))):
            name = os.path.basename(path)
            if name in _EXCLUDED_VICE_SCRIPTS or name in seen_vice_scripts:
                continue
            default_label = name.replace("vice_", "").replace(".py", "").replace("_", " ").title()
            label, icon = APP_LABELS.get(name, (default_label, "applications-other"))
            if label.lower() in seen_labels:
                continue
            seen_labels.add(label.lower())
            seen_vice_scripts.add(name)
            apps.append({
                "id": name,
                "name": name,
                "label": label,
                "icon": icon,
                "comment": label,
                "category": _VICE_CAT_LOOKUP.get(name, "Utilities"),
                "args": [sys.executable, path],
                "workdir": os.path.expanduser("~"),
            })

    apps.sort(key=lambda item: item["label"].lower())
    return apps


def _load_card_icon(icon_name: str) -> QIcon:
    """Resolve an icon from filesystem path, theme, hicolor apps, or pixmaps."""
    return resolve_icon(icon_name, "application-x-executable", "applications-other")


class AppButton(QPushButton):
    def __init__(self, app_info, on_launch, on_fav_toggle, is_fav=False):
        super().__init__()
        self._info = app_info
        self._is_fav = is_fav
        self.setObjectName("AppCard")
        self.setFocusPolicy(Qt.NoFocus)

        label = app_info["label"]
        self.setToolTip(f"{label}\n{app_info.get('comment', '')}".strip())
        self.setMinimumSize(166, 102)
        self.setMaximumSize(188, 108)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)
        card_layout.setAlignment(Qt.AlignVCenter)

        icon_lbl = QLabel(self)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon = _load_card_icon(app_info.get("icon", ""))
        if not icon.isNull():
            icon_lbl.setPixmap(icon.pixmap(34, 34))
        card_layout.addWidget(icon_lbl)

        display_label = label[:32] + "…" if len(label) > 33 else label
        text_lbl = QLabel(display_label, self)
        text_lbl.setAlignment(Qt.AlignCenter)
        text_lbl.setWordWrap(True)
        text_lbl.setMinimumWidth(144)
        lbl_font = text_lbl.font()
        lbl_font.setBold(True)
        text_lbl.setFont(lbl_font)
        text_lbl.setStyleSheet("background: transparent; border: none; font-size: 12px;")
        card_layout.addWidget(text_lbl)

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
        self.setMinimumSize(700, 480)
        self.setStyleSheet(STYLE)
        self._apps = discover_apps()
        self._favorites = load_favorites()
        self._category = "All"
        self._cat_buttons = {}
        self._cols = self._calc_cols()
        self._init_ui()
        self._populate()
        self._search.setFocus()

    def _calc_cols(self) -> int:
        return max(3, (self.width() - 44) // 182)

    def _init_ui(self):
        c = COLORS
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 14, 16, 14)

        header = QHBoxLayout()
        title = QLabel("Applications")
        title.setFont(QFont("Noto Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {c['text_primary']};")
        header.addWidget(title)
        header.addStretch(1)
        hint = QLabel("Right-click card to pin/unpin Favorites · Esc to close")
        hint.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px;")
        header.addWidget(hint)
        root.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search Debian, Office, Security & Vice OS apps...")
        self._search.textChanged.connect(self._populate)
        root.addWidget(self._search)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

        cats_host = QWidget(self)
        cats_host.setStyleSheet("background: transparent;")
        cats_flow = FlowLayout(cats_host, h_spacing=6, v_spacing=6)
        cats_flow.setContentsMargins(0, 0, 0, 0)
        for cat in ["All", "Favorites"] + list(CATEGORIES.keys()):
            btn = QPushButton(cat, cats_host)
            btn.setObjectName("CategoryTab")
            btn.setFixedHeight(32)
            btn.setCheckable(True)
            btn.setChecked(cat == "All")
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _checked=False, name=cat: self._set_category(name))
            cats_flow.addWidget(btn)
            self._cat_buttons[cat] = btn
        root.addWidget(cats_host)

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
        self._count_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
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

        cols = self._calc_cols()
        self._cols = cols
        for i, app in enumerate(filtered):
            is_fav = app["label"] in self._favorites or app["name"] in self._favorites
            btn = AppButton(app, self._launch, self._toggle_fav, is_fav)
            row, col = divmod(i, cols)
            self._grid_layout.addWidget(btn, row, col)

        self._count_label.setText(f"{len(filtered)} application(s)")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_cols()
        if new_cols != self._cols:
            self._populate()

    def _launch(self, app_info):
        args = app_info.get("args", [])
        if not args:
            return
        workdir = app_info.get("workdir") or os.path.expanduser("~")
        if not os.path.isdir(workdir):
            workdir = os.path.expanduser("~")
        log_info(f"Launching: {' '.join(args)}")
        QProcess.startDetached(args[0], args[1:], workdir)
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


def _configure_icon_theme():
    """Ensure PyQt5 resolves Papirus-Dark / Adwaita icons properly."""
    configure_icon_theme()


def _configure_cjk_fonts(app: QApplication):
    """Ensure CJK characters render properly without tofu boxes."""
    configure_cjk_fonts(app)


def main():
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    _configure_icon_theme()
    win = AppLauncher()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
