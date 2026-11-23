#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Animated Login Screen.
Authenticates the user against system PAM via 'su' and launches the X11 or Wayland
session using QProcess, styled with the Leonida Coastal Dusk design system.
"""

import os
import shutil
import subprocess
import sys

from PyQt5.QtCore import QProcess, QPropertyAnimation, Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QLineEdit,
    QPushButton,
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
    configure_cjk_fonts,
    configure_icon_theme,
)


class AnimatedLogin(QWidget):
    """Full-screen PAM login greeter styled with calm slate surfaces and coral CTAs."""

    def __init__(self):
        super().__init__()
        self.session_process = None
        self.auth_process = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Login - Vice OS")
        self.setWindowFlags(Qt.FramelessWindowHint)

        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display login screen.")
            sys.exit(1)

        self.setGeometry(screen.geometry())
        c = COLORS
        self.setStyleSheet(f"QWidget#LoginRoot {{ background-color: {c['bg_canvas']}; }}")
        self.setObjectName("LoginRoot")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("Card")
        card.setFixedWidth(376)
        card.setStyleSheet(
            f"QFrame#Card {{ background-color: {c['bg_surface']}; "
            f"border: 1px solid {c['border']}; border-radius: 14px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        logo_label = QLabel(card)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("background: transparent; border: none;")
        logo_loaded = False
        for logo_path in (
            "/usr/share/pixmaps/vice-debian-gta6.png",
            "/usr/share/pixmaps/vice-app.png",
        ):
            if os.path.isfile(logo_path):
                pix = QPixmap(logo_path)
                if not pix.isNull():
                    logo_label.setPixmap(
                        pix.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                    logo_loaded = True
                    break

        title = QLabel("VICE OS", card)
        title.setFont(QFont("Noto Sans", 28, QFont.Bold))
        title.setStyleSheet(
            f"color: {c['text_primary']}; letter-spacing: 5px; background: transparent; border: none;"
        )
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Leonida Workstation", card)
        subtitle.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: 12px; background: transparent; border: none;"
        )
        subtitle.setAlignment(Qt.AlignCenter)

        self.user_input = QLineEdit(card)
        self.user_input.setPlaceholderText("Username")
        self.user_input.setText("vice")
        self.user_input.setFixedHeight(40)

        self.pwd = QLineEdit(card)
        self.pwd.setPlaceholderText("Password")
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setFixedHeight(40)
        self.pwd.returnPressed.connect(self.check_pass)
        self.user_input.returnPressed.connect(self.pwd.setFocus)

        self.session_combo = QComboBox(card)
        self.session_combo.addItem("X11 (Openbox)", "x11")
        self.session_combo.addItem("Wayland (Labwc)", "wayland")
        self.session_combo.setFixedHeight(38)
        self.load_default_session()

        self.login_btn = QPushButton("Sign In", card)
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.setFixedHeight(40)
        self.login_btn.clicked.connect(self.check_pass)

        hint_label = QLabel("Live Session Default: vice / vice", card)
        hint_label.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 11px; background: transparent; border: none;"
        )
        hint_label.setAlignment(Qt.AlignCenter)

        if logo_loaded:
            layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(self.user_input)
        layout.addWidget(self.pwd)
        layout.addWidget(self.session_combo)
        layout.addWidget(self.login_btn)
        layout.addSpacing(4)
        layout.addWidget(hint_label)

        outer.addStretch(2)
        outer.addWidget(card, alignment=Qt.AlignCenter)
        outer.addStretch(3)

        self._title_opacity = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(self._title_opacity)
        self.anim = QPropertyAnimation(self._title_opacity, b"opacity")
        self.anim.setDuration(600)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(150, self._focus_password_field)
        QTimer.singleShot(500, self._focus_password_field)

    def _focus_password_field(self):
        self.raise_()
        self.activateWindow()
        self.pwd.setFocus(Qt.ActiveWindowFocusReason)

    def load_default_session(self):
        """Load default session preference from system or user config."""
        for conf_path in (
            "/etc/vice-os/session.conf",
            os.path.expanduser("~/.config/vice-os/session.conf"),
        ):
            if os.path.isfile(conf_path):
                try:
                    with open(conf_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("SESSION_TYPE="):
                                session_type = line.strip().split("=", 1)[1].strip('"\'')
                                self.session_combo.setCurrentIndex(1 if session_type == "wayland" else 0)
                                break
                except Exception:
                    pass

    def check_pass(self):
        username = self.user_input.text().strip()
        password = self.pwd.text()

        if not username or not password:
            self.shake_error("Enter username and password")
            if not username:
                self.user_input.setFocus()
            else:
                self.pwd.setFocus()
            return

        self.user_input.setEnabled(False)
        self.pwd.setEnabled(False)
        self.login_btn.setEnabled(False)

        self.auth_process = QProcess(self)
        self.auth_process.setProcessChannelMode(QProcess.ForwardedChannels)
        self.auth_process.finished.connect(self.handle_auth_result)
        self.auth_process.start("su", [username, "-c", "true"])

        if not self.auth_process.waitForStarted(3000):
            self.shake_error("Failed to start authentication process.")
            return

        bytes_written = self.auth_process.write(f"{password}\n".encode())
        self.pwd.clear()

        if bytes_written == -1:
            log_error("Failed to write password to auth process stdin.")
            self.shake_error("Authentication pipe error.")
            return

        self.auth_process.waitForBytesWritten(1000)
        self.auth_process.closeWriteChannel()
        QTimer.singleShot(5000, self.handle_auth_timeout)

    def handle_auth_timeout(self):
        if self.auth_process and self.auth_process.state() == QProcess.Running:
            self.auth_process.kill()
            self.shake_error("Authentication timed out.")

    def handle_auth_result(self):
        exit_code = self.auth_process.exitCode()
        if exit_code == 0:
            self.hide()
            self.start_session(self.user_input.text().strip())
        else:
            self.shake_error("Login incorrect.")

    def shake_error(self, message: str = "Login incorrect"):
        c = COLORS
        self.pwd.clear()
        self.user_input.setEnabled(True)
        self.pwd.setEnabled(True)
        self.login_btn.setEnabled(True)
        self.pwd.setStyleSheet(
            f"background-color: #2A161D; color: {c['text_primary']}; "
            f"border: 1px solid {c['danger']}; border-radius: 8px; padding: 6px 10px;"
        )
        self.pwd.setPlaceholderText(message)
        self.pwd.setFocus()
        QTimer.singleShot(2000, self.reset_pwd_style)

    def reset_pwd_style(self):
        self.pwd.setStyleSheet("")
        self.pwd.setPlaceholderText("Password")

    def start_session(self, username: str):
        """Start the configured session (X11 or Wayland) and monitor it for exit."""
        try:
            uid = os.getuid()
            runtime_dir = f"/run/user/{uid}"
            os.makedirs(runtime_dir, exist_ok=True)
            os.chmod(runtime_dir, 0o700)

            os.environ["USER"] = username
            os.environ["LOGNAME"] = username
            os.environ["HOME"] = f"/home/{username}"
            os.environ["XDG_RUNTIME_DIR"] = runtime_dir
            bus_sock = f"{runtime_dir}/bus"
            if os.path.exists(bus_sock):
                os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_sock}"
            else:
                os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)

            selected_session = self.session_combo.currentData() or "x11"
            user_config_dir = f"/home/{username}/.config/vice-os"
            os.makedirs(user_config_dir, exist_ok=True)
            try:
                with open(f"{user_config_dir}/session.conf", "w", encoding="utf-8") as f:
                    f.write(f'# Vice OS User Session Preference\nSESSION_TYPE="{selected_session}"\n')
            except Exception:
                pass

            session_script = (
                "/opt/vice-os/wayland_session.sh"
                if selected_session == "wayland"
                else "/opt/vice-os/dbus_session.sh"
            )

            self.session_process = QProcess(self)
            self.session_process.setProcessChannelMode(QProcess.ForwardedChannels)
            self.session_process.finished.connect(QApplication.quit)
            self.session_process.start(session_script)

        except Exception as e:
            log_error(f"Failed to start session: {e}")
            term = next(
                (t for t in ("xfce4-terminal", "x-terminal-emulator", "xterm") if shutil.which(t)),
                None,
            )
            if term:
                subprocess.Popen([term, "-e", "bash"], env=os.environ)
            else:
                subprocess.Popen(["bash"], env=os.environ)
            sys.exit(1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    configure_cjk_fonts(app)
    configure_icon_theme()
    apply_app_theme(app)
    ex = AnimatedLogin()
    ex.showFullScreen()
    ex.raise_()
    ex.activateWindow()
    ex.pwd.setFocus()
    sys.exit(app.exec_())
