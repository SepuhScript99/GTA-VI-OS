#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) First-Boot Welcome Wizard
Guides new users through initial system setup:
  - Welcome / Introduction
  - Timezone and region configuration
  - Keyboard layout selection
  - Wi-Fi network connection
  - Optional software installation (Docker, VS Code, Flatpak)
  - Finish

Uses QStackedWidget for page navigation and calls system_utils scripts
for configuration changes. Writes a flag file on completion so the
wizard only runs once.
"""

import sys
import os
import subprocess
import json

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QComboBox, QListWidget, QListWidgetItem, QCheckBox,
    QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap

from python.vice_utils import log_info, log_error

FLAG_FILE = os.path.expanduser("~/.config/vice-os/welcome_completed")
STYLE_FILE = "/opt/vice-os/style.qss"
WIZARD_WIDTH = 640
WIZARD_HEIGHT = 480

TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "Europe/London", "Europe/Berlin",
    "Europe/Paris", "Europe/Moscow", "Asia/Tokyo",
    "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney",
    "Pacific/Auckland", "UTC",
]

KEYBOARD_LAYOUTS = [
    ("us", "English (US)"),
    ("gb", "English (UK)"),
    ("de", "German"),
    ("fr", "French"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("jp", "Japanese"),
    ("cn", "Chinese"),
    ("br", "Portuguese (Brazil)"),
    ("se", "Swedish"),
    ("no", "Norwegian"),
    ("dk", "Danish"),
    ("fi", "Finnish"),
    ("pl", "Polish"),
    ("cz", "Czech"),
    ("hu", "Hungarian"),
]

OPTIONAL_APPS = [
    ("Docker Engine", "Container runtime for development and deployment"),
    ("VS Code", "Microsoft Visual Studio Code editor"),
    ("Flatpak Support", "Flathub repository + Flatpak runtime for sandboxed apps"),
]

THEMES = [
    ("Cyberpunk Cyan",  "#00ffff", "#ff00ff", "#0a0a0a"),
    ("Blood Red",       "#ff2222", "#ff8800", "#0a0a0a"),
    ("Matrix Green",    "#00ff41", "#00aa00", "#0a0a0a"),
    ("Neon Purple",     "#bf00ff", "#ff00ff", "#0a0a0a"),
    ("Solar Gold",      "#ffd700", "#ff8c00", "#0a0a0a"),
    ("Ice Blue",        "#88ccff", "#0088ff", "#0d0d12"),
]

LOCALES = [
    "en_US.UTF-8", "en_GB.UTF-8", "de_DE.UTF-8", "fr_FR.UTF-8",
    "es_ES.UTF-8", "it_IT.UTF-8", "pt_BR.UTF-8", "ru_RU.UTF-8",
    "ja_JP.UTF-8", "zh_CN.UTF-8", "ko_KR.UTF-8", "pl_PL.UTF-8",
    "nl_NL.UTF-8", "sv_SE.UTF-8", "tr_TR.UTF-8", "ar_SA.UTF-8",
]

PAGE_STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QLabel { color: #00ffff; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QCheckBox { color: #cccccc; padding: 4px; }
QCheckBox::indicator { width: 14px; height: 14px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; }
QProgressBar::chunk { background: #00ffff; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px 14px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
"""


class WelcomePage(QWidget):
    """First page — welcome message and overview."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Welcome to Vice OS")
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setStyleSheet("color: #00FFFF;")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Let's get your system set up in a few steps.")
        subtitle.setFont(QFont("Arial", 14))
        subtitle.setStyleSheet("color: #FFFFFF;")
        subtitle.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "We'll help you configure:\n"
            "  - Timezone and region\n"
            "  - Keyboard layout\n"
            "  - Wi-Fi network\n"
            "  - Optional software\n\n"
            "Click Next to begin."
        )
        desc.setFont(QFont("Arial", 12))
        desc.setStyleSheet("color: #CCCCCC;")
        desc.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(desc)
        layout.addStretch()
        self.setLayout(layout)


class TimezonePage(QWidget):
    """Timezone selection page."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        title = QLabel("Select Your Timezone")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #00FFFF;")

        self.combo = QComboBox()
        self.combo.addItems(TIMEZONES)
        self.combo.setCurrentText("UTC")

        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Choose your timezone from the list below:"))
        layout.addWidget(self.combo)
        layout.addStretch()
        self.setLayout(layout)

    def get_selected_timezone(self) -> str:
        return self.combo.currentText()


class KeyboardPage(QWidget):
    """Keyboard layout selection page."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        title = QLabel("Select Keyboard Layout")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #00FFFF;")

        self.list_widget = QListWidget()
        for code, name in KEYBOARD_LAYOUTS:
            item = QListWidgetItem(f"{name} ({code})")
            item.setData(Qt.UserRole, code)
            self.list_widget.addItem(item)

        self.list_widget.setCurrentRow(0)

        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Choose your keyboard layout:"))
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

    def get_selected_layout(self) -> str:
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return "us"


class NetworkPage(QWidget):
    """Wi-Fi network selection and connection page."""
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout())

        title = QLabel("Connect to Wi-Fi")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #00FFFF;")

        self.status_label = QLabel("Scanning for networks...")
        self.status_label.setStyleSheet("color: #FF00FF;")

        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_networks)

        self.network_list = QListWidget()
        self.network_list.itemClicked.connect(self.on_network_selected)

        self.skip_button = QPushButton("Skip — I'll connect later")
        self.skip_button.setObjectName("DockButton")

        self.layout().addWidget(title)
        self.layout().addSpacing(10)
        self.layout().addWidget(self.status_label)
        self.layout().addWidget(self.scan_button)
        self.layout().addWidget(self.network_list)
        self.layout().addStretch()
        self.layout().addWidget(self.skip_button)

    def scan_networks(self):
        self.status_label.setText("Scanning...")
        self.network_list.clear()
        QTimer.singleShot(100, self._do_scan)

    def _do_scan(self):
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) >= 1 and parts[0]:
                        item = QListWidgetItem(f"{parts[0]}  ({parts[1]}%)")
                        item.setData(Qt.UserRole, parts[0])
                        self.network_list.addItem(item)
                self.status_label.setText(f"Found {self.network_list.count()} networks.")
            else:
                self.status_label.setText("No Wi-Fi networks found or Wi-Fi is disabled.")
        except Exception as e:
            self.status_label.setText(f"Scan failed: {e}")

    def on_network_selected(self, item):
        ssid = item.data(Qt.UserRole)
        log_info(f"Network selected: {ssid}")
        self.status_label.setText(f"Selected: {ssid}")

    def get_selected_ssid(self) -> str:
        item = self.network_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return ""


class UserSetupPage(QWidget):
    """User account setup page."""
    def __init__(self):
        super().__init__()
        from PyQt5.QtWidgets import QLineEdit, QFormLayout
        layout = QVBoxLayout()

        title = QLabel("User Account Setup")
        title.setFont(QFont("monospace", 18, QFont.Bold))
        title.setStyleSheet("color: #ff00ff;")
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Configure your user account:"))
        layout.addSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("e.g. vice")
        form.addRow("Username:", self.username_edit)

        self.fullname_edit = QLineEdit()
        self.fullname_edit.setPlaceholderText("e.g. Vice User")
        form.addRow("Full Name:", self.fullname_edit)

        self.hostname_edit = QLineEdit()
        self.hostname_edit.setPlaceholderText("e.g. vice-os")
        form.addRow("Hostname:", self.hostname_edit)

        self.autologin_cb = QCheckBox("Enable auto-login at boot")
        self.autologin_cb.setChecked(True)

        layout.addLayout(form)
        layout.addSpacing(10)
        layout.addWidget(self.autologin_cb)
        layout.addStretch()
        self.setLayout(layout)

    def get_values(self):
        return {
            "username": self.username_edit.text().strip() or "vice",
            "fullname": self.fullname_edit.text().strip(),
            "hostname": self.hostname_edit.text().strip() or "vice-os",
            "autologin": self.autologin_cb.isChecked(),
        }


class ThemePage(QWidget):
    """Theme picker page."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        title = QLabel("Choose Your Theme")
        title.setFont(QFont("monospace", 18, QFont.Bold))
        title.setStyleSheet("color: #ff00ff;")
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Select a color theme for Vice OS:"))
        layout.addSpacing(8)

        self._preview = QLabel()
        self._preview.setFixedHeight(48)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setFont(QFont("monospace", 13, QFont.Bold))
        layout.addWidget(self._preview)
        layout.addSpacing(6)

        self.theme_list = QListWidget()
        for name, primary, accent, bg in THEMES:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (primary, accent, bg))
            from PyQt5.QtGui import QColor
            item.setForeground(QColor(primary))
            self.theme_list.addItem(item)
        self.theme_list.setCurrentRow(0)
        self.theme_list.currentItemChanged.connect(self._preview_theme)
        layout.addWidget(self.theme_list)
        layout.addStretch()
        self.setLayout(layout)
        self._preview_theme(self.theme_list.currentItem(), None)

    def _preview_theme(self, current, _prev):
        if not current:
            return
        primary, accent, bg = current.data(Qt.UserRole)
        self._preview.setText(f"Vice OS  —  {current.text()}")
        self._preview.setStyleSheet(
            f"background-color: {bg}; color: {primary}; "
            f"border: 2px solid {accent}; padding: 4px;"
        )

    def get_selected_theme(self):
        item = self.theme_list.currentItem()
        if item:
            primary, accent, bg = item.data(Qt.UserRole)
            return {"name": item.text(), "primary": primary, "accent": accent, "bg": bg}
        return {"name": "Cyberpunk Cyan", "primary": "#00ffff", "accent": "#ff00ff", "bg": "#0a0a0a"}


class LocalePage(QWidget):
    """Locale / language selection page."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        title = QLabel("Language & Locale")
        title.setFont(QFont("monospace", 18, QFont.Bold))
        title.setStyleSheet("color: #ff00ff;")
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Select system locale:"))

        self.combo = QComboBox()
        self.combo.addItems(LOCALES)
        self.combo.setCurrentText("en_US.UTF-8")
        layout.addWidget(self.combo)
        layout.addStretch()
        self.setLayout(layout)

    def get_locale(self):
        return self.combo.currentText()


class SoftwarePage(QWidget):
    """Optional software installation page."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        title = QLabel("Install Optional Software")
        title.setFont(QFont("monospace", 18, QFont.Bold))
        title.setStyleSheet("color: #ff00ff;")

        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Select additional software to install:"))

        self.checkboxes = []
        for name, desc in OPTIONAL_APPS:
            cb = QCheckBox(f"{name} — {desc}")
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        layout.addStretch()
        self.setLayout(layout)

    def get_selected_apps(self) -> list:
        selected = []
        for cb, (name, _) in zip(self.checkboxes, OPTIONAL_APPS):
            if cb.isChecked():
                selected.append(name.lower().replace(" ", "-"))
        return selected


class FinishPage(QWidget):
    """Final page — summary and completion."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Setup Complete!")
        title.setFont(QFont("monospace", 26, QFont.Bold))
        title.setStyleSheet("color: #00ffff;")
        title.setAlignment(Qt.AlignCenter)

        self.summary = QLabel("")
        self.summary.setStyleSheet("color: #888; font-size: 12px;")
        self.summary.setAlignment(Qt.AlignCenter)
        self.summary.setWordWrap(True)

        desc = QLabel("Your Vice OS system is ready.\nClick Finish to start.")
        desc.setFont(QFont("monospace", 13))
        desc.setStyleSheet("color: #cccccc;")
        desc.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(self.summary)
        layout.addSpacing(10)
        layout.addWidget(desc)
        layout.addStretch()
        self.setLayout(layout)

    def set_summary(self, tz, locale, theme_name, username, hostname):
        self.summary.setText(
            f"User: {username}  |  Host: {hostname}\n"
            f"Timezone: {tz}  |  Locale: {locale}\n"
            f"Theme: {theme_name}"
        )


class WelcomeWizard(QWidget):
    """Main wizard window with stacked pages and navigation."""
    def __init__(self):
        super().__init__()
        self.pages = []
        self.current_page = 0
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Vice OS — Setup Wizard")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(WIZARD_WIDTH, WIZARD_HEIGHT)
        self.setStyleSheet(PAGE_STYLE)

        main_layout = QVBoxLayout()

        # Step indicator
        self._step_label = QLabel()
        self._step_label.setAlignment(Qt.AlignRight)
        self._step_label.setStyleSheet("color: #555; font-size: 11px; margin-right: 4px;")
        main_layout.addWidget(self._step_label)

        self.stack = QStackedWidget()
        self._user_page = UserSetupPage()
        self._theme_page = ThemePage()
        self._locale_page = LocalePage()
        self._finish_page = FinishPage()

        self.pages = [
            WelcomePage(),
            self._user_page,
            TimezonePage(),
            self._locale_page,
            KeyboardPage(),
            NetworkPage(),
            self._theme_page,
            SoftwarePage(),
            self._finish_page,
        ]
        for page in self.pages:
            self.stack.addWidget(page)

        main_layout.addWidget(self.stack)

        btn_layout = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        btn_layout.addWidget(self.back_btn)
        btn_layout.addStretch()

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.go_next)
        btn_layout.addWidget(self.next_btn)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
        self._update_step()

    def _update_step(self):
        self._step_label.setText(f"Step {self.current_page + 1} of {len(self.pages)}")

    def go_next(self):
        if self.current_page == 0:
            self.back_btn.setEnabled(True)

        last = len(self.pages) - 1
        if self.current_page == last - 1:
            self.apply_settings()
            self.next_btn.setText("Finish")
        elif self.current_page == last:
            self.finish()
            return

        self.current_page += 1
        self.stack.setCurrentIndex(self.current_page)
        self._update_step()

    def go_back(self):
        if self.current_page == 1:
            self.back_btn.setEnabled(False)
        if self.current_page == len(self.pages) - 1:
            self.next_btn.setText("Next")
        self.current_page -= 1
        self.stack.setCurrentIndex(self.current_page)
        self._update_step()

    def apply_settings(self):
        log_info("Applying welcome wizard settings...")

        tz = self.pages[2].get_selected_timezone()
        try:
            subprocess.run(["timedatectl", "set-timezone", tz], capture_output=True, timeout=10)
            log_info(f"Timezone: {tz}")
        except Exception as e:
            log_error(f"Timezone failed: {e}")

        locale = self._locale_page.get_locale()
        try:
            subprocess.run(["localectl", "set-locale", f"LANG={locale}"], capture_output=True, timeout=10)
            log_info(f"Locale: {locale}")
        except Exception as e:
            log_error(f"Locale failed: {e}")

        kb = self.pages[4].get_selected_layout()
        try:
            subprocess.run(["setxkbmap", kb], capture_output=True, timeout=5)
            log_info(f"Keyboard: {kb}")
        except Exception as e:
            log_error(f"Keyboard failed: {e}")

        user_info = self._user_page.get_values()
        try:
            subprocess.run(["hostnamectl", "set-hostname", user_info["hostname"]], capture_output=True, timeout=5)
            log_info(f"Hostname: {user_info['hostname']}")
        except Exception as e:
            log_error(f"Hostname failed: {e}")

        theme = self._theme_page.get_selected_theme()
        theme_conf = os.path.expanduser("~/.config/vice-os/theme.json")
        os.makedirs(os.path.dirname(theme_conf), exist_ok=True)
        try:
            with open(theme_conf, "w") as f:
                json.dump(theme, f, indent=2)
            log_info(f"Theme saved: {theme['name']}")
        except Exception as e:
            log_error(f"Theme save failed: {e}")

        apps = self.pages[7].get_selected_apps()
        for app in apps:
            installer_map = {
                "docker-engine": "/usr/local/bin/vp-docker.sh",
                "vs-code": "/usr/local/bin/vp-code.sh",
                "flatpak-support": "/usr/local/bin/vp-flatpak.sh",
            }
            installer = installer_map.get(app)
            if installer and os.path.isfile(installer):
                try:
                    subprocess.run(["sudo", installer], capture_output=True, timeout=120)
                    log_info(f"Installed: {app}")
                except Exception as e:
                    log_error(f"Install failed {app}: {e}")

        self._finish_page.set_summary(
            tz, locale, theme["name"],
            user_info["username"], user_info["hostname"]
        )

    def finish(self):
        flag_dir = os.path.dirname(FLAG_FILE)
        os.makedirs(flag_dir, exist_ok=True)
        with open(FLAG_FILE, "w") as f:
            f.write("completed")
        log_info("Welcome wizard completed.")

        # Register all Vice OS applications (menu entries + autostart)
        # so every tool is discoverable right after first boot.
        self._register_apps()

        QApplication.quit()

    @staticmethod
    def _register_apps():
        setup_script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "vice_setup_apps.py")
        if os.path.exists(setup_script):
            try:
                subprocess.run([sys.executable, setup_script],
                               capture_output=True, timeout=60)
                log_info("Registered all Vice OS applications")
            except Exception as e:
                log_error(f"App registration failed: {e}")


def create_flag_file():
    """Ensure the flag directory exists (no-op, called if needed)."""
    os.makedirs(os.path.dirname(FLAG_FILE), exist_ok=True)


def has_wizard_run() -> bool:
    """Return True if the welcome wizard has already completed."""
    return os.path.isfile(FLAG_FILE)


def load_stylesheet(app: QApplication):
    if os.path.exists(STYLE_FILE):
        try:
            with open(STYLE_FILE) as f:
                app.setStyleSheet(f.read())
        except IOError:
            pass


def main():
    app = QApplication(sys.argv)
    load_stylesheet(app)

    wizard = WelcomeWizard()
    wizard.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
