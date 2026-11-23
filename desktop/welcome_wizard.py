#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) First-Boot Welcome Wizard.
Guides new users through initial system setup (timezone, locale, keyboard,
Wi-Fi, theme, optional apps) using the Leonida Coastal Dusk design system.
"""

import json
import os
import subprocess
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_error, log_info  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    build_app_qss,
    configure_cjk_fonts,
    configure_icon_theme,
    get_logo_icon,
)

FLAG_FILE = os.path.expanduser("~/.config/vice-os/welcome_completed")
STYLE_FILE = "/opt/vice-os/style.qss"
WIZARD_WIDTH = 660
WIZARD_HEIGHT = 500

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
    ("VS Code", "Visual Studio Code editor"),
    ("Flatpak Support", "Flathub repository and Flatpak runtime for sandboxed apps"),
]

THEMES = [
    ("Leonida Sunset", "#FF5E7E", "#FF9A62", "#0D0E15"),
    ("Keys Aqua", "#36D6C3", "#FF9A62", "#0D0E15"),
    ("Golden Hour", "#F7C873", "#FF5E7E", "#0D0E15"),
    ("Twilight Slate", "#A6AEBF", "#FF5E7E", "#141621"),
    ("Emerald Mint", "#3ED598", "#36D6C3", "#0D0E15"),
]

LOCALES = [
    "en_US.UTF-8", "en_GB.UTF-8", "de_DE.UTF-8", "fr_FR.UTF-8",
    "es_ES.UTF-8", "it_IT.UTF-8", "pt_BR.UTF-8", "ru_RU.UTF-8",
    "ja_JP.UTF-8", "zh_CN.UTF-8", "ko_KR.UTF-8", "pl_PL.UTF-8",
    "nl_NL.UTF-8", "sv_SE.UTF-8", "tr_TR.UTF-8", "ar_SA.UTF-8",
]

PAGE_STYLE = build_app_qss()


class WelcomePage(QWidget):
    """First page — welcome message and overview."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        logo_lbl = QLabel(self)
        logo_lbl.setAlignment(Qt.AlignCenter)
        icon = get_logo_icon()
        if not icon.isNull():
            logo_lbl.setPixmap(icon.pixmap(72, 72))

        title = QLabel("Welcome to Vice OS")
        title.setFont(QFont("Noto Sans", 24, QFont.Bold))
        title.setStyleSheet(f"color: {c['text_primary']};")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Leonida Coastal Dusk Workstation")
        subtitle.setStyleSheet(f"color: {c['accent_peach']}; font-size: 14px; font-weight: 600;")
        subtitle.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "Configure your initial workspace in a few steps:\n"
            "  • Account & Hostname\n"
            "  • Timezone, Locale & Keyboard\n"
            "  • Wi-Fi & Color Accent\n"
            "  • Optional Developer Runtimes"
        )
        desc.setStyleSheet(f"color: {c['text_secondary']}; font-size: 13px;")
        desc.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        if not icon.isNull():
            layout.addWidget(logo_lbl)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(desc)
        layout.addStretch()


class TimezonePage(QWidget):
    """Timezone selection page."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Select Your Timezone")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")

        sub = QLabel("Choose your default timezone (Vice TimeSync can also sync automatically online):")
        sub.setStyleSheet(f"color: {c['text_secondary']};")

        self.combo = QComboBox()
        self.combo.addItems(TIMEZONES)
        self.combo.setCurrentText("UTC")

        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.combo)
        layout.addStretch()

    def get_selected_timezone(self) -> str:
        return self.combo.currentText()


class KeyboardPage(QWidget):
    """Keyboard layout selection page."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Select Keyboard Layout")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")

        sub = QLabel("Choose your hardware keyboard layout:")
        sub.setStyleSheet(f"color: {c['text_secondary']};")

        self.list_widget = QListWidget()
        for code, name in KEYBOARD_LAYOUTS:
            item = QListWidgetItem(f"{name} ({code})")
            item.setData(Qt.UserRole, code)
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(0)

        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.list_widget)

    def get_selected_layout(self) -> str:
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return "us"


class NetworkPage(QWidget):
    """Wi-Fi network selection and connection page."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Connect to Wi-Fi")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")

        self.status_label = QLabel("Ready to scan wireless networks.")
        self.status_label.setStyleSheet(f"color: {c['accent_aqua']};")

        self.scan_button = QPushButton("Scan Networks")
        self.scan_button.clicked.connect(self.scan_networks)

        self.network_list = QListWidget()
        self.network_list.itemClicked.connect(self.on_network_selected)

        self.skip_button = QPushButton("Skip for now")

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.network_list, 1)
        layout.addWidget(self.skip_button)

    def scan_networks(self):
        self.status_label.setText("Scanning...")
        self.network_list.clear()
        QTimer.singleShot(100, self._do_scan)

    def _do_scan(self):
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) >= 1 and parts[0]:
                        sig = parts[1] if len(parts) > 1 else "?"
                        item = QListWidgetItem(f"{parts[0]} ({sig}%)")
                        item.setData(Qt.UserRole, parts[0])
                        self.network_list.addItem(item)
                self.status_label.setText(f"Found {self.network_list.count()} network(s).")
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
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("User Account Setup")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel("Configure your local account and hostname:")
        sub.setStyleSheet(f"color: {c['text_secondary']};")
        layout.addWidget(sub)

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
        layout.addSpacing(8)
        layout.addWidget(self.autologin_cb)
        layout.addStretch()

    def get_values(self):
        return {
            "username": self.username_edit.text().strip() or "vice",
            "fullname": self.fullname_edit.text().strip(),
            "hostname": self.hostname_edit.text().strip() or "vice-os",
            "autologin": self.autologin_cb.isChecked(),
        }


class ThemePage(QWidget):
    """Theme accent picker page."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Choose Your Accent Style")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel("Select a Leonida accent profile for Vice OS:")
        sub.setStyleSheet(f"color: {c['text_secondary']};")
        layout.addWidget(sub)

        self._preview = QLabel()
        self._preview.setFixedHeight(48)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setFont(QFont("Noto Sans", 13, QFont.Bold))
        layout.addWidget(self._preview)

        self.theme_list = QListWidget()
        for name, primary, accent, bg in THEMES:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (primary, accent, bg))
            item.setForeground(QColor(primary))
            self.theme_list.addItem(item)
        self.theme_list.setCurrentRow(0)
        self.theme_list.currentItemChanged.connect(self._preview_theme)
        layout.addWidget(self.theme_list)
        layout.addStretch()
        self._preview_theme(self.theme_list.currentItem(), None)

    def _preview_theme(self, current, _prev):
        if not current:
            return
        primary, accent, bg = current.data(Qt.UserRole)
        self._preview.setText(f"Vice OS — {current.text()}")
        self._preview.setStyleSheet(
            f"background-color: {bg}; color: {primary}; "
            f"border: 1px solid {accent}; border-radius: 10px; padding: 6px;"
        )

    def get_selected_theme(self):
        item = self.theme_list.currentItem()
        if item:
            primary, accent, bg = item.data(Qt.UserRole)
            return {"name": item.text(), "primary": primary, "accent": accent, "bg": bg}
        return {"name": "Leonida Sunset", "primary": "#FF5E7E", "accent": "#FF9A62", "bg": "#0D0E15"}


class LocalePage(QWidget):
    """Locale / language selection page."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Language & Locale")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel("Select system locale:")
        sub.setStyleSheet(f"color: {c['text_secondary']};")
        layout.addWidget(sub)

        self.combo = QComboBox()
        self.combo.addItems(LOCALES)
        self.combo.setCurrentText("en_US.UTF-8")
        layout.addWidget(self.combo)
        layout.addStretch()

    def get_locale(self):
        return self.combo.currentText()


class SoftwarePage(QWidget):
    """Optional software installation page."""

    def __init__(self):
        super().__init__()
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Install Optional Software")
        title.setStyleSheet(f"color: {c['text_primary']}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel("Select additional developer runtimes to install:")
        sub.setStyleSheet(f"color: {c['text_secondary']};")
        layout.addWidget(sub)

        self.checkboxes = []
        for name, desc in OPTIONAL_APPS:
            cb = QCheckBox(f"{name} — {desc}")
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        layout.addStretch()

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
        c = COLORS
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        title = QLabel("Setup Complete")
        title.setStyleSheet(f"color: {c['accent_aqua']}; font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)

        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")
        self.summary.setAlignment(Qt.AlignCenter)
        self.summary.setWordWrap(True)

        desc = QLabel("Your Vice OS workstation is ready.\nClick Finish to begin.")
        desc.setStyleSheet(f"color: {c['text_primary']}; font-size: 13px;")
        desc.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(self.summary)
        layout.addWidget(desc)
        layout.addStretch()

    def set_summary(self, tz, locale, theme_name, username, hostname):
        self.summary.setText(
            f"User: {username}  |  Host: {hostname}\n"
            f"Timezone: {tz}  |  Locale: {locale}\n"
            f"Accent: {theme_name}"
        )


class WelcomeWizard(QWidget):
    """Main managed wizard window with stacked pages and navigation."""

    def __init__(self):
        super().__init__()
        self.pages = []
        self.current_page = 0
        self.initUI()

    def initUI(self):
        c = COLORS
        self.setWindowTitle("Vice OS — Setup Wizard")
        self.resize(WIZARD_WIDTH, WIZARD_HEIGHT)
        self.setMinimumSize(WIZARD_WIDTH, WIZARD_HEIGHT)
        self.setStyleSheet(PAGE_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        self._step_label = QLabel()
        self._step_label.setAlignment(Qt.AlignRight)
        self._step_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        main_layout.addWidget(self._step_label)

        stack_card = QFrame(self)
        stack_card.setObjectName("Card")
        stack_lay = QVBoxLayout(stack_card)
        stack_lay.setContentsMargins(16, 14, 16, 14)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: transparent; border: none;")
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
            page.setStyleSheet("background-color: transparent;")
            self.stack.addWidget(page)

        stack_lay.addWidget(self.stack, 1)
        main_layout.addWidget(stack_card, 1)

        btn_layout = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        btn_layout.addWidget(self.back_btn)
        btn_layout.addStretch()

        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("PrimaryButton")
        self.next_btn.clicked.connect(self.go_next)
        btn_layout.addWidget(self.next_btn)

        main_layout.addLayout(btn_layout)
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
            with open(theme_conf, "w", encoding="utf-8") as f:
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
            tz, locale, theme["name"], user_info["username"], user_info["hostname"]
        )

    def finish(self):
        os.makedirs(os.path.dirname(FLAG_FILE), exist_ok=True)
        with open(FLAG_FILE, "w", encoding="utf-8") as f:
            f.write("completed")
        log_info("Welcome wizard completed.")
        self._register_apps()
        QApplication.quit()

    @staticmethod
    def _register_apps():
        setup_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "vice_setup_apps.py"
        )
        if os.path.exists(setup_script):
            try:
                subprocess.run([sys.executable, setup_script], capture_output=True, timeout=60)
                log_info("Registered all Vice OS applications")
            except Exception as e:
                log_error(f"App registration failed: {e}")


def create_flag_file():
    """Ensure the flag directory exists."""
    os.makedirs(os.path.dirname(FLAG_FILE), exist_ok=True)


def has_wizard_run() -> bool:
    """Return True if the welcome wizard has already completed."""
    return os.path.isfile(FLAG_FILE)


def load_stylesheet(app: QApplication):
    apply_app_theme(app)


def main():
    app = QApplication(sys.argv)
    configure_cjk_fonts(app)
    configure_icon_theme()
    load_stylesheet(app)

    wizard = WelcomeWizard()
    wizard.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
