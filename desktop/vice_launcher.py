#!/usr/bin/env python3
"""
Vice OS Application Launcher — unified full-width AppCard grid discovering
standard XDG .desktop applications and Vice OS utilities with categories,
live counts, search, favorites, and non-blocking incremental batch rendering.
"""

import glob
import json
import os
import re
import shlex
import shutil
import sys

from PyQt5 import QtCore as _qt_core
from PyQt5 import QtGui as _qt_gui
from PyQt5 import QtWidgets as _qt_widgets

QProcess = _qt_core.QProcess
QSize = _qt_core.QSize
Qt = _qt_core.Qt
QTimer = getattr(_qt_core, "QTimer", object)

QCursor = getattr(_qt_gui, "QCursor", object)
QFont = _qt_gui.QFont
QFontMetrics = getattr(_qt_gui, "QFontMetrics", None)
QIcon = _qt_gui.QIcon
QKeySequence = _qt_gui.QKeySequence
QPixmap = getattr(_qt_gui, "QPixmap", None)

QApplication = _qt_widgets.QApplication
QFrame = getattr(_qt_widgets, "QFrame", _qt_widgets.QWidget)
QGridLayout = _qt_widgets.QGridLayout
QHBoxLayout = _qt_widgets.QHBoxLayout
QLabel = _qt_widgets.QLabel
QLineEdit = _qt_widgets.QLineEdit
QPushButton = _qt_widgets.QPushButton
QScrollArea = _qt_widgets.QScrollArea
QShortcut = _qt_widgets.QShortcut
QSizePolicy = getattr(_qt_widgets, "QSizePolicy", object)
QVBoxLayout = _qt_widgets.QVBoxLayout
QWidget = _qt_widgets.QWidget

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

WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 640

_c = COLORS
STYLE = build_app_qss(
    f"""
QPushButton#CategoryTab {{
    background: {_c['bg_surface']};
    color: {_c['text_secondary']};
    border: 1px solid {_c['border']};
    border-radius: 9px;
    padding: 5px 12px;
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
QFrame#AppCard {{
    background: {_c['bg_surface']};
    border: 1px solid {_c['border']};
    border-radius: 12px;
}}
QFrame#AppCard:hover {{
    background: {_c['bg_elevated']};
    border-color: {_c['accent_coral']};
}}
QFrame#AppCard:focus {{
    background: {_c['bg_elevated']};
    border: 1px solid {_c['accent_aqua']};
}}
QPushButton#FavStarBtn {{
    background: transparent;
    color: {_c['text_muted']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 15px;
}}
QPushButton#FavStarBtn:hover {{
    background: {_c['bg_hover']};
    color: {_c['accent_gold']};
    border-color: {_c['border_strong']};
}}
QPushButton#FavStarBtn[favorited="true"] {{
    color: {_c['accent_gold']};
}}
QPushButton#HubPill {{
    background: {_c['bg_elevated']};
    color: {_c['accent_gold']};
    border: 1px solid {_c['border_strong']};
    border-radius: 9px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: bold;
    min-width: 0px;
}}
QPushButton#HubPill:hover {{
    background: {_c['bg_active']};
    color: {_c['accent_peach']};
    border-color: {_c['accent_coral']};
}}
"""
)

CATEGORIES = {
    "Development": [
        "vice_software_center.py", "vice_package_search.py", "vice_iso_validator.py",
        "vice_diagnostics.py", "vice_log_viewer.py", "vice_log_rotation.py",
        "vice_cron_manager.py", "vice_tool_qr_hash.py", "vice_tool_cheatsheets.py",
    ],
    "Office": ["vice_tool_office_hub.py", "vice_tool_missions.py"],
    "Internet": [
        "vice_network_monitor.py", "vice_vpn_manager.py", "vice_network_shares.py",
        "vice_wifi_connect.py", "vice_ssh_manager.py", "vice_speedtest.py",
        "vice_tool_net_shield.py", "vice_tool_net_radar.py",
    ],
    "Security": [
        "vice_tool_cyber_deck.py", "vice_tool_mac_cloak.py", "vice_tool_vault.py",
        "vice_tool_payload_lab.py", "vice_firewall_manager.py",
    ],
    "System": [
        "vice_task_manager.py", "vice_system_monitor.py", "vice_system_report.py",
        "vice_service_manager.py", "vice_power_manager.py", "vice_driver_manager.py",
        "vice_update_manager.py", "vice_kernel_manager.py", "vice_cleanup.py",
        "vice_session_manager.py", "vice_disk_benchmark.py", "vice_disk_manager.py",
        "vice_disk_usage.py", "vice_user_manager.py", "vice_usb_manager.py",
        "vice_printer_manager.py", "vice_bluetooth_manager.py",
        "vice_tool_hub.py", "vice_tool_turbo.py", "vice_tool_sys_deck.py",
    ],
    "Multimedia": [
        "vice_audio_manager.py", "vice_font_manager.py", "vice_image_viewer.py",
        "vice_media_player.py", "vice_pdf_viewer.py", "vice_screen_recorder.py",
        "vice_tool_radio.py", "vice_tool_media_studio.py",
    ],
    "Graphics": [],
    "Utilities": [
        "vice_file_manager.py", "vice_text_editor.py", "vice_terminal.py",
        "vice_screenshot.py", "vice_clipboard.py", "vice_archive_manager.py",
        "vice_backup_scheduler.py", "vice_sysinfo_exporter.py",
        "vice_calculator.py", "vice_calendar.py", "vice_tool_clock_sync.py",
        "vice_trash_manager.py", "vice_help_viewer.py",
        "vice_file_search.py", "vice_checksum.py",
    ],
    "Settings": [
        "vice_settings.py", "vice_display_manager.py", "vice_keyboard_shortcuts.py",
        "vice_mouse_settings.py", "vice_accessibility.py", "vice_theme_manager.py",
        "vice_openbox_editor.py", "vice_startup_apps.py", "vice_wallpaper_picker.py",
        "vice_notif_history.py",
    ],
}

CATEGORY_TABS = [
    "All",
    "Favorites",
    "GTA VI Originals",
    "Development",
    "Office",
    "Internet",
    "Security",
    "System",
    "Multimedia",
    "Graphics",
    "Utilities",
    "Settings",
]

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
    "vice_settings_pages.py",
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
    "vice_tool_payload_lab.py": ("Vice Payload Lab", "vice-tool-payload-lab"),
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


def _read_registry_counts() -> tuple:
    """Return (current_count, target_count) from tools_registry.json."""
    repo_root = os.path.abspath(os.path.join(DESKTOP_DIR, ".."))
    candidates = (
        "/opt/vice-os/tools_registry.json",
        os.path.join(repo_root, "config", "tools_registry.json"),
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


def load_favorites():
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return [
        "Firefox ESR",
        "Visual Studio Code",
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

    base_name = os.path.basename(filepath)
    is_original = base_name.startswith(("vice-", "vice_"))
    return {
        "id": base_name,
        "name": base_name,
        "label": name,
        "icon": icon,
        "comment": comment or name,
        "category": category,
        "original": is_original,
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
    seen_labels = {}
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
            exec_key = _exec_dedup_key(entry)
            is_vice_tool = entry["id"].startswith("vice-tool-")
            if key in seen_labels:
                existing_idx = seen_labels[key]
                existing_is_vice = apps[existing_idx]["id"].startswith("vice-tool-")
                if is_vice_tool and not existing_is_vice:
                    apps[existing_idx] = entry
                    if exec_key:
                        seen_execs[exec_key] = existing_idx
                continue
            if exec_key and exec_key in seen_execs:
                existing_idx = seen_execs[exec_key]
                existing_is_vice = apps[existing_idx]["id"].startswith("vice-tool-")
                if is_vice_tool and not existing_is_vice:
                    seen_labels.pop(apps[existing_idx]["label"].lower(), None)
                    seen_labels[key] = existing_idx
                    apps[existing_idx] = entry
                continue
            idx = len(apps)
            seen_labels[key] = idx
            if exec_key:
                seen_execs[exec_key] = idx
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
            seen_labels[label.lower()] = len(apps)
            seen_vice_scripts.add(name)
            apps.append({
                "id": name,
                "name": name,
                "label": label,
                "icon": icon,
                "comment": label,
                "category": _VICE_CAT_LOOKUP.get(name, "Utilities"),
                "original": True,
                "args": [sys.executable, path],
                "workdir": os.path.expanduser("~"),
            })

    if desktop_app_dirs is None:
        code_bin = shutil.which("code")
        if code_bin and "visual studio code" not in seen_labels:
            seen_labels["visual studio code"] = len(apps)
            apps.append({
                "id": "vscode.desktop",
                "name": "vscode.desktop",
                "label": "Visual Studio Code",
                "icon": "vice-tool-vscode",
                "comment": "Code Editing. Redefined (C/C++/C#/Python/Rust/JS)",
                "category": "Development",
                "original": False,
                "args": [code_bin],
                "workdir": os.path.expanduser("~"),
            })
        hw_bin = shutil.which("vice-hw-autodetect") or (
            "/usr/local/bin/vice-hw-autodetect"
            if os.path.isfile("/usr/local/bin/vice-hw-autodetect")
            else None
        )
        if hw_bin and not any(
            k in seen_labels for k in ("vice hw & vm auto-detect", "vice hw auto-detect", "hw auto-detect")
        ):
            runner = shutil.which("vice-run-tool")
            hw_args = (
                [runner, "Vice HW & VM Auto-Detect", hw_bin, "--status"]
                if runner
                else ["xfce4-terminal", "--disable-server", "-x", hw_bin, "--status"]
            )
            seen_labels["vice hw & vm auto-detect"] = len(apps)
            apps.append({
                "id": "vice-tool-hw-autodetect.desktop",
                "name": "vice-tool-hw-autodetect.desktop",
                "label": "Vice HW & VM Auto-Detect",
                "icon": "vice-tool-hw-autodetect",
                "comment": "Universal Hardware, GPU, Wi-Fi & VM Driver Auto-Detection",
                "category": "System",
                "original": True,
                "args": hw_args,
                "workdir": os.path.expanduser("~"),
            })

    apps.sort(key=lambda item: item["label"].lower())
    return apps


def _load_card_pixmap(icon_name: str, cache: dict, size: int = 40):
    """Resolve and cache a crisp icon QPixmap for *icon_name*."""
    key = (icon_name or "", size)
    if key in cache:
        return cache[key]
    icon = resolve_icon(icon_name, "application-x-executable", "applications-other")
    pix = icon.pixmap(size, size) if not icon.isNull() else None
    cache[key] = pix
    return pix


class AppCard(QFrame):
    """Full-width horizontal application card ([40x40 Icon] [Title + Subtitle] [Star])."""

    def __init__(self, app_info, icon_cache, on_launch, on_fav_toggle, is_fav=False, parent=None):
        super().__init__(parent)
        self._info = app_info
        self._on_launch = on_launch
        self._on_fav_toggle = on_fav_toggle
        self._is_fav = is_fav

        self.setObjectName("AppCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(74)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        if hasattr(Qt, "PointingHandCursor"):
            self.setCursor(QCursor(Qt.PointingHandCursor))

        label = app_info.get("label", "")
        comment = app_info.get("comment", "") or label
        cat = app_info.get("category", "Utilities")
        self.setToolTip(f"{label}\n{cat} — {comment}")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(12)

        icon_lbl = QLabel(self)
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        pix = _load_card_pixmap(app_info.get("icon", ""), icon_cache, 40)
        if pix is not None and not pix.isNull():
            icon_lbl.setPixmap(pix)
        else:
            icon_lbl.setText(label[:2].upper())
            icon_lbl.setStyleSheet(
                f"background: {COLORS['bg_elevated']}; color: {COLORS['accent_peach']}; "
                f"border-radius: 10px; font-weight: bold;"
            )
        row.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title_lbl = QLabel(label, self)
        title_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: bold; "
            "background: transparent; border: none;"
        )
        title_lbl.setWordWrap(False)
        title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_col.addWidget(title_lbl)

        subtitle_raw = f"{cat} · {comment}" if comment and comment != label else cat
        if len(subtitle_raw) > 54:
            subtitle_raw = subtitle_raw[:51] + "…"
        sub_lbl = QLabel(subtitle_raw, self)
        sub_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            "background: transparent; border: none;"
        )
        sub_lbl.setWordWrap(False)
        sub_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_col.addWidget(sub_lbl)
        row.addLayout(text_col, 1)

        self._fav_btn = QPushButton("★" if is_fav else "☆", self)
        self._fav_btn.setObjectName("FavStarBtn")
        self._fav_btn.setProperty("favorited", "true" if is_fav else "false")
        self._fav_btn.setFocusPolicy(Qt.NoFocus)
        self._fav_btn.setToolTip("Unpin from Favorites" if is_fav else "Pin to Favorites")
        self._fav_btn.clicked.connect(lambda _checked=False: self._on_fav_toggle(self._info))
        row.addWidget(self._fav_btn, 0, Qt.AlignVCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_launch(self._info)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self._on_fav_toggle(self._info)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._on_launch(self._info)
            event.accept()
            return
        super().keyPressEvent(event)


class AppLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Applications")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 520)
        self.setStyleSheet(STYLE)

        self._apps = discover_apps()
        self._favorites = load_favorites()
        self._category = "All"
        self._cat_buttons = {}
        self._icon_cache = {}
        self._pending_apps = []
        self._rendered_count = 0
        self._render_total = 0

        self._batch_timer = QTimer(self)
        self._batch_timer.setInterval(10)
        self._batch_timer.timeout.connect(self._render_next_batch)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(80)
        self._search_timer.timeout.connect(self._populate)

        self._init_ui()
        self._cols = self._calc_cols()
        self._update_category_counts()
        self._populate()
        self._search.setFocus()

    def _calc_cols(self) -> int:
        vp_w = self._scroll.viewport().width() if hasattr(self, "_scroll") else 0
        width = vp_w if vp_w > 120 else (self.width() - 36)
        if width >= 1160:
            return 4
        if width >= 740:
            return 3
        return 2

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
        hint = QLabel("Click card to launch · ★ or right-click to pin Favorites · Esc to close")
        hint.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px;")
        header.addWidget(hint)
        cur_tools, tgt_tools = _read_registry_counts()
        pct_tools = int(round((cur_tools / max(1, tgt_tools)) * 100))
        hub_pill = QPushButton(f"Tool Hub · {cur_tools} / {tgt_tools} ({pct_tools}%)")
        hub_pill.setObjectName("HubPill")
        hub_pill.setFocusPolicy(Qt.NoFocus)
        hub_pill.clicked.connect(lambda: self._launch({
            "args": [sys.executable, os.path.join(DESKTOP_DIR, "vice_tool_hub.py")],
            "workdir": os.path.expanduser("~"),
        }))
        header.addWidget(hub_pill)
        root.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            f"Search {len(self._apps)} Debian, Office, Security & Vice OS apps..."
        )
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _txt: self._search_timer.start())
        root.addWidget(self._search)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

        cats_host = QWidget(self)
        cats_host.setStyleSheet("background: transparent;")
        cats_flow = FlowLayout(cats_host, h_spacing=6, v_spacing=6)
        cats_flow.setContentsMargins(0, 0, 0, 0)
        for cat in CATEGORY_TABS:
            btn = QPushButton(cat.replace("&", "&&"), cats_host)
            btn.setObjectName("CategoryTab")
            btn.setFixedHeight(32)
            btn.setCheckable(True)
            btn.setChecked(cat == "All")
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _checked=False, name=cat: self._set_category(name))
            cats_flow.addWidget(btn)
            self._cat_buttons[cat] = btn
        root.addWidget(cats_host)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(2, 4, 8, 4)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._grid_widget)
        root.addWidget(self._scroll, 1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        root.addWidget(self._count_label)

    def _is_favorite(self, app: dict) -> bool:
        return app["label"] in self._favorites or app["name"] in self._favorites

    def _matches_category(self, app: dict, cat: str) -> bool:
        if cat == "All":
            return True
        if cat == "Favorites":
            return self._is_favorite(app)
        if cat == "GTA VI Originals":
            return bool(app.get("original"))
        return app.get("category") == cat

    def _update_category_counts(self):
        for cat, btn in self._cat_buttons.items():
            cnt = sum(1 for app in self._apps if self._matches_category(app, cat))
            btn.setText(f"{cat} ({cnt})".replace("&", "&&"))

    def _set_category(self, cat):
        self._category = cat
        for name, btn in self._cat_buttons.items():
            btn.setChecked(name == cat)
        self._populate()

    def _clear_grid(self):
        self._batch_timer.stop()
        self._pending_apps = []
        self._rendered_count = 0
        self._render_total = 0
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _populate(self):
        self._clear_grid()

        search = self._search.text().strip().lower()
        filtered = []
        for app in self._apps:
            if not self._matches_category(app, self._category):
                continue
            if search:
                haystack = (
                    f"{app['label']} {app['name']} {app.get('category', '')} "
                    f"{app.get('comment', '')}"
                ).lower()
                if search not in haystack:
                    continue
            filtered.append(app)

        cols = self._calc_cols()
        self._cols = cols
        for c in range(6):
            self._grid_layout.setColumnStretch(c, 1 if c < cols else 0)

        if not filtered:
            empty = QLabel("No applications match your search.", self._grid_widget)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"color: {COLORS['text_secondary']}; font-size: 14px; padding: 40px;"
            )
            self._grid_layout.addWidget(empty, 0, 0, 1, cols)
            self._count_label.setText("0 application(s)")
            return

        self._pending_apps = filtered
        self._rendered_count = 0
        self._render_total = len(filtered)
        self._render_batch(limit=24)
        if self._pending_apps:
            self._batch_timer.start()

    def _render_batch(self, limit: int):
        cols = self._cols
        batch = self._pending_apps[:limit]
        self._pending_apps = self._pending_apps[limit:]
        for app in batch:
            idx = self._rendered_count
            card = AppCard(
                app,
                self._icon_cache,
                self._launch,
                self._toggle_fav,
                is_fav=self._is_favorite(app),
                parent=self._grid_widget,
            )
            row, col = divmod(idx, cols)
            self._grid_layout.addWidget(card, row, col)
            self._rendered_count += 1

        if not self._pending_apps:
            self._batch_timer.stop()
            last_row = max(0, (self._render_total - 1) // cols + 1)
            self._grid_layout.setRowStretch(last_row, 1)
            self._count_label.setText(f"{self._render_total} application(s)")
        else:
            self._count_label.setText(
                f"Loading {self._rendered_count} / {self._render_total} applications..."
            )

    def _render_next_batch(self):
        self._render_batch(limit=36)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_cols()
        if new_cols != self._cols:
            self._populate()

    def closeEvent(self, event):
        self._search_timer.stop()
        self._batch_timer.stop()
        super().closeEvent(event)

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
        self._update_category_counts()
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
