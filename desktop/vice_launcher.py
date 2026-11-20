#!/usr/bin/env python3
"""Vice OS Application Launcher — full-screen menu with categories, search, and favorites."""

import sys
import os
import glob

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QScrollArea, QFrame, QGridLayout, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QFont, QColor, QIcon

from python.vice_utils import log_info

WINDOW_WIDTH = 1020
WINDOW_HEIGHT = 680

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QLineEdit { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; padding: 8px; font-size: 14px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0a0a0a; width: 8px; }
QScrollBar::handle:vertical { background: #00ffff; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #1a4a4a; padding: 12px; text-align: center; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QLabel { color: #00ffff; }
"""

CATEGORIES = {
    "System":      ["vice_settings.py", "vice_task_manager.py", "vice_system_monitor.py",
                    "vice_system_report.py", "vice_service_manager.py", "vice_power_manager.py",
                    "vice_driver_manager.py", "vice_update_manager.py",
                    "vice_kernel_manager.py", "vice_cleanup.py", "vice_session_manager.py",
                    "vice_disk_benchmark.py"],
    "Internet":    ["vice_network_monitor.py", "vice_vpn_manager.py", "vice_network_shares.py",
                    "vice_wifi_connect.py", "vice_ssh_manager.py", "vice_speedtest.py"],
    "Utilities":   ["vice_file_manager.py", "vice_text_editor.py", "vice_terminal.py",
                    "vice_screenshot.py", "vice_clipboard.py", "vice_archive_manager.py",
                    "vice_backup_scheduler.py", "vice_sysinfo_exporter.py",
                    "vice_calculator.py", "vice_calendar.py", "vice_clipboard_manager.py",
                    "vice_trash_manager.py", "vice_help_viewer.py"],
    "Multimedia":  ["vice_audio_manager.py", "vice_font_manager.py", "vice_image_viewer.py",
                    "vice_media_player.py", "vice_pdf_viewer.py", "vice_screen_recorder.py"],
    "Hardware":    ["vice_display_manager.py", "vice_disk_manager.py", "vice_bluetooth_manager.py",
                    "vice_firewall_manager.py", "vice_usb_manager.py", "vice_printer_manager.py"],
    "Developer":   ["vice_software_center.py", "vice_package_search.py", "vice_iso_validator.py",
                    "vice_diagnostics.py", "vice_log_viewer.py", "vice_log_rotation.py",
                    "vice_cron_manager.py"],
    "Admin":       ["vice_user_manager.py", "vice_notif_history.py", "vice_disk_usage.py",
                    "vice_file_search.py", "vice_checksum.py"],
    "Settings":    ["vice_keyboard_shortcuts.py", "vice_mouse_settings.py", "vice_accessibility.py",
                    "vice_theme_manager.py", "vice_openbox_editor.py", "vice_startup_apps.py",
                    "vice_wallpaper_picker.py"],
}

APP_LABELS = {
    "vice_settings.py":          ("Settings Center", "⚙"),
    "vice_task_manager.py":      ("Task Manager",    "📊"),
    "vice_system_monitor.py":    ("System Monitor",  "📈"),
    "vice_system_report.py":     ("System Report",   "📋"),
    "vice_service_manager.py":   ("Service Manager", "🔧"),
    "vice_power_manager.py":     ("Power Manager",   "🔋"),
    "vice_driver_manager.py":    ("Driver Manager",  "🖥"),
    "vice_update_manager.py":    ("Update Manager",  "📦"),
    "vice_file_manager.py":      ("File Manager",    "📁"),
    "vice_text_editor.py":       ("Text Editor",     "📝"),
    "vice_terminal.py":          ("Terminal",        "💻"),
    "vice_screenshot.py":        ("Screenshot",      "📸"),
    "vice_clipboard.py":         ("Clipboard",       "📋"),
    "vice_archive_manager.py":   ("Archive Manager", "🗜"),
    "vice_audio_manager.py":     ("Audio Manager",   "🔊"),
    "vice_font_manager.py":      ("Font Manager",    "🔤"),
    "vice_display_manager.py":   ("Display Manager", "🖥"),
    "vice_disk_manager.py":      ("Disk Manager",    "💾"),
    "vice_bluetooth_manager.py": ("Bluetooth",       "📡"),
    "vice_firewall_manager.py":  ("Firewall",        "🛡"),
    "vice_software_center.py":   ("Software Center", "🏪"),
    "vice_package_search.py":    ("Package Search",  "🔍"),
    "vice_iso_validator.py":     ("ISO Validator",   "✅"),
    "vice_diagnostics.py":       ("Diagnostics",     "🩺"),
    "vice_user_manager.py":      ("User Manager",    "👤"),
    "vice_notif_history.py":     ("Notifications",   "🔔"),
    "vice_keyboard_shortcuts.py": ("Keyboard",        "⌨"),
    "vice_mouse_settings.py":    ("Mouse/Touchpad",  "🖱"),
    "vice_accessibility.py":     ("Accessibility",   "♿"),
    "vice_usb_manager.py":       ("USB Manager",     "🔌"),
    "vice_vpn_manager.py":       ("VPN Manager",     "🔐"),
    "vice_network_shares.py":    ("Net Shares",      "🗂"),
    "vice_backup_scheduler.py":  ("Backup Jobs",     " Scheduled"),
    "vice_log_rotation.py":      ("Log Rotation",    "🌀"),
    "vice_sysinfo_exporter.py":  ("Info Export",     "📤"),
    "vice_printer_manager.py":   ("Printer",         "🖨"),
    "vice_theme_manager.py":     ("Theme Manager",   "🎨"),
    "vice_openbox_editor.py":    ("Openbox Editor",  "🪟"),
    "vice_notification_daemon.py": ("Notif Daemon", "👻"),
    "vice_calendar.py":          ("Calendar",        "📅"),
    "vice_calculator.py":        ("Calculator",      "🧮"),
    "vice_image_viewer.py":      ("Image Viewer",    "🖼"),
    "vice_startup_apps.py":      ("Startup Apps",    "🚀"),
    "vice_media_player.py":      ("Media Player",    "🎵"),
    "vice_file_search.py":       ("File Search",     "🔎"),
    "vice_disk_usage.py":        ("Disk Usage",      "📊"),
    "vice_cron_manager.py":      ("Cron Jobs",       "⏰"),
    "vice_pdf_viewer.py":        ("PDF Viewer",      "📄"),
    "vice_wifi_connect.py":      ("WiFi Connect",    "📶"),
    "vice_ssh_manager.py":       ("SSH Manager",     "🔗"),
    "vice_screen_recorder.py":   ("Screen Recorder", "🎥"),
    "vice_checksum.py":          ("Checksum",        "#️⃣"),
    "vice_wallpaper_picker.py":  ("Wallpapers",      "🖼"),
    "vice_kernel_manager.py":    ("Kernel Manager",  "🐧"),
    "vice_cleanup.py":           ("System Cleanup",  "🧹"),
    "vice_clipboard_manager.py": ("Clipboard (v1)",  "📋"),
    "vice_network_monitor.py":   ("Net Monitor",     "📡"),
    "vice_trash_manager.py":     ("Trash",           "🗑"),
    "vice_help_viewer.py":       ("Help",            "❓"),
    "vice_speedtest.py":         ("Speed Test",      "⚡"),
    "vice_disk_benchmark.py":    ("Disk Bench",      "💽"),
}

FAVORITES_FILE = os.path.expanduser("~/.config/vice-os/favorites.json")
DESKTOP_DIR = os.path.join(os.path.dirname(__file__))


def load_favorites():
    import json
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return ["vice_terminal.py", "vice_file_manager.py", "vice_text_editor.py",
            "vice_settings.py", "vice_software_center.py"]


def save_favorites(favs):
    import json
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    try:
        with open(FAVORITES_FILE, "w") as f:
            json.dump(favs, f)
    except Exception:
        pass


def discover_apps():
    apps = []
    py_files = glob.glob(os.path.join(DESKTOP_DIR, "vice_*.py"))
    for path in sorted(py_files):
        name = os.path.basename(path)
        label, icon = APP_LABELS.get(name, (name.replace("vice_", "").replace(".py", "").replace("_", " ").title(), "•"))
        apps.append({"file": path, "name": name, "label": label, "icon": icon})
    return apps


class AppButton(QPushButton):
    def __init__(self, app_info, on_launch, on_fav_toggle, is_fav=False):
        super().__init__()
        self._info = app_info
        self._is_fav = is_fav
        icon = app_info["icon"]
        label = app_info["label"]
        self.setText(f"{icon}\n{label}")
        self.setMinimumSize(120, 90)
        self.setFixedWidth(120)
        self.setStyleSheet("""
            QPushButton { font-size: 12px; padding: 10px; }
        """)
        self.clicked.connect(lambda: on_launch(app_info["file"]))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos, a=app_info, f=is_fav: on_fav_toggle(a, self)
        )


class AppLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Applications")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._apps = discover_apps()
        self._favorites = load_favorites()
        self._category = "All"
        self._init_ui()
        self._populate()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Vice OS")
        title.setFont(QFont("monospace", 20, QFont.Bold))
        title.setStyleSheet("color: #ff00ff;")
        root.addWidget(title)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search applications...")
        self._search.textChanged.connect(self._populate)
        root.addWidget(self._search)

        # Category bar
        cat_row = QHBoxLayout()
        cat_row.setSpacing(4)
        for cat in ["All", "Favorites"] + list(CATEGORIES.keys()) + ["Other"]:
            btn = QPushButton(cat)
            btn.setFixedHeight(28)
            btn.setCheckable(True)
            btn.setChecked(cat == "All")
            btn.clicked.connect(lambda _, c=cat: self._set_category(c))
            cat_row.addWidget(btn)
        root.addLayout(cat_row)

        # App grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(8)
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._count_label)

    def _set_category(self, cat):
        self._category = cat
        for btn in self.findChildren(QPushButton):
            if btn.text() == cat:
                btn.setChecked(True)
            elif btn.text() in (["All", "Favorites"] + list(CATEGORIES.keys()) + ["Other"]):
                btn.setChecked(False)
        self._populate()

    def _populate(self):
        while self._grid_layout.count():
            w = self._grid_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        search = self._search.text().lower()
        filtered = []

        if self._category == "Favorites":
            for app in self._apps:
                if app["name"] in self._favorites:
                    if not search or search in app["label"].lower() or search in app["name"]:
                        filtered.append(app)
        elif self._category == "All":
            filtered = [a for a in self._apps
                        if not search or search in a["label"].lower() or search in a["name"]]
        elif self._category == "Other":
            categorized = set()
            for files in CATEGORIES.values():
                categorized.update(files)
            filtered = [a for a in self._apps if a["name"] not in categorized
                        and (not search or search in a["label"].lower() or search in a["name"])]
        else:
            cat_files = CATEGORIES.get(self._category, [])
            filtered = [a for a in self._apps if a["name"] in cat_files
                        and (not search or search in a["label"].lower() or search in a["name"])]

        cols = 8
        for i, app in enumerate(filtered):
            is_fav = app["name"] in self._favorites
            btn = AppButton(app, self._launch, self._toggle_fav, is_fav)
            row, col = divmod(i, cols)
            self._grid_layout.addWidget(btn, row, col)

        self._count_label.setText(f"{len(filtered)} application(s)")

    def _launch(self, filepath):
        log_info(f"Launching: {filepath}")
        proc = QProcess(self)
        proc.setWorkingDirectory(DESKTOP_DIR)
        proc.startDetached(sys.executable, [filepath])

    def _toggle_fav(self, app_info, btn):
        name = app_info["name"]
        if name in self._favorites:
            self._favorites.remove(name)
        else:
            self._favorites.append(name)
        save_favorites(self._favorites)
        self._populate()


def main():
    app = QApplication(sys.argv)
    win = AppLauncher()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
