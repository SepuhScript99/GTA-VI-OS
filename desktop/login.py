#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Animated Login Screen
Authenticates the user against system PAM via 'su' and launches the X session.
Uses QProcess to prevent UI freezing during authentication and session monitoring.
"""

import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QComboBox,
    QVBoxLayout, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QTimer, QProcess
from PyQt5.QtGui import QFont

# Add the project lib directory to the system path to import shared modules
sys.path.insert(0, '/opt/vice-os/lib')

# Require the shared library. Fail hard if missing.
from python.vice_utils import log_info, log_error

class AnimatedLogin(QWidget):
    def __init__(self):
        super().__init__()
        self.session_process = None
        self.auth_process = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Login - Vice OS')
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Dynamically set geometry to primary screen safely
        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display login screen.")
            sys.exit(1)

        geo = screen.geometry()
        self.setGeometry(geo)

        self.setStyleSheet("background-color: #050505;")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel("VICE OS")
        label.setFont(QFont("Arial", 56, QFont.Bold))
        label.setStyleSheet("color: #00FFFF; background: transparent;")
        label.setAlignment(Qt.AlignCenter)
        label.setFixedHeight(90)

        self.user_input = QLineEdit(self)
        self.user_input.setPlaceholderText("Username")
        self.user_input.setText("vice") # Default to vice for live iso
        self.user_input.setStyleSheet(
            "background-color: #120024; color: #FFFFFF; "
            "border: 2px solid #00FFFF; border-radius: 10px; padding: 10px;"
        )
        self.user_input.setFixedSize(300, 40)
        self.pwd = QLineEdit(self)
        self.pwd.setPlaceholderText("Password")
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setStyleSheet(
            "background-color: #120024; color: #FFFFFF; "
            "border: 2px solid #FF00FF; border-radius: 10px; padding: 10px;"
        )
        self.pwd.setFixedSize(300, 40)
        self.pwd.returnPressed.connect(self.check_pass)
        self.user_input.returnPressed.connect(self.pwd.setFocus)

        # Session selection dropdown (X11 / Wayland)
        self.session_combo = QComboBox(self)
        self.session_combo.addItem("X11 (Openbox)", "x11")
        self.session_combo.addItem("Wayland (Labwc)", "wayland")
        self.session_combo.setStyleSheet(
            "QComboBox { background-color: #120024; color: #00FFFF; border: 2px solid #00FFFF; "
            "border-radius: 8px; padding: 6px 12px; font-weight: bold; } "
            "QComboBox::drop-down { border: none; } "
            "QComboBox QAbstractItemView { background-color: #120024; color: #FFFFFF; "
            "selection-background-color: #FF00FF; selection-color: #FFFFFF; }"
        )
        self.session_combo.setFixedSize(300, 36)

        # Load default session preference from system configuration
        self.load_default_session()

        hint_label = QLabel("Live Session Default: vice / vice")
        hint_label.setFont(QFont("Arial", 10))
        hint_label.setStyleSheet("color: #66CCCC; background: transparent;")
        hint_label.setAlignment(Qt.AlignCenter)

        layout.addStretch(2)
        layout.addWidget(label)
        layout.addSpacing(24)
        layout.addWidget(self.user_input, alignment=Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self.pwd, alignment=Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self.session_combo, alignment=Qt.AlignCenter)
        layout.addSpacing(14)
        layout.addWidget(hint_label, alignment=Qt.AlignCenter)
        layout.addStretch(3)
        self.setLayout(layout)

        # Fade-in title animation (avoids geometry conflicts with QVBoxLayout)
        self._title_opacity = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(self._title_opacity)
        self.anim = QPropertyAnimation(self._title_opacity, b"opacity")
        self.anim.setDuration(900)
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
        """Loads default session preference from system/user config."""
        for conf_path in ["/etc/vice-os/session.conf", os.path.expanduser("~/.config/vice-os/session.conf")]:
            if os.path.isfile(conf_path):
                try:
                    with open(conf_path, "r") as f:
                        for line in f:
                            if line.strip().startswith("SESSION_TYPE="):
                                session_type = line.strip().split("=", 1)[1].strip('"\'')
                                if session_type == "wayland":
                                    self.session_combo.setCurrentIndex(1)
                                else:
                                    self.session_combo.setCurrentIndex(0)
                                break
                except Exception:
                    pass

    def check_pass(self):
        username = self.user_input.text().strip()
        password = self.pwd.text()

        if not username or not password:
            self.shake_error()
            if not username:
                self.user_input.setFocus()
            else:
                self.pwd.setFocus()
            return

        # Disable inputs to prevent multiple submissions
        self.user_input.setEnabled(False)
        self.pwd.setEnabled(False)

        # Use QProcess to prevent UI freeze during PAM authentication
        self.auth_process = QProcess(self)
        self.auth_process.setProcessChannelMode(QProcess.ForwardedChannels)

        # Handle the result asynchronously
        self.auth_process.finished.connect(self.handle_auth_result)

        # Start 'su' to verify the password
        self.auth_process.start('su', [username, '-c', 'true'])

        # Wait for the process to start writing to stdin safely
        if not self.auth_process.waitForStarted(3000):
            self.shake_error("Failed to start authentication process.")
            return

        # Write the password to stdin and close it
        bytes_written = self.auth_process.write(f"{password}\n".encode())

        # Clear the password from memory immediately after writing
        self.pwd.clear()

        if bytes_written == -1:
            log_error("Failed to write password to auth process stdin.")
            self.shake_error("Authentication pipe error.")
            return

        # Wait for bytes to be written to ensure 'su' receives the password
        self.auth_process.waitForBytesWritten(1000)
        self.auth_process.closeWriteChannel()

        # Set a timeout to prevent infinite hangs
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
        self.pwd.clear()
        self.user_input.setEnabled(True)
        self.pwd.setEnabled(True)
        self.pwd.setStyleSheet(
            "background-color: #240012; color: #FFFFFF; "
            "border: 2px solid #FF0000; border-radius: 10px; padding: 10px;"
        )
        self.pwd.setPlaceholderText(message)
        self.pwd.setFocus()
        QTimer.singleShot(2000, self.reset_pwd_style)

    def reset_pwd_style(self):
        self.pwd.setStyleSheet(
            "background-color: #120024; color: #FFFFFF; "
            "border: 2px solid #FF00FF; border-radius: 10px; padding: 10px;"
        )
        self.pwd.setPlaceholderText("Password")

    def start_session(self, username: str):
        """Starts the configured session (X11 or Wayland) and monitors it for exit."""
        try:
            uid = os.getuid()
            runtime_dir = f"/run/user/{uid}"

            # Since we bypass pam_systemd via 'su', we must create the runtime dir manually
            os.makedirs(runtime_dir, exist_ok=True)
            os.chmod(runtime_dir, 0o700)

            # Set necessary environment variables for the session
            os.environ["USER"] = username
            os.environ["LOGNAME"] = username
            os.environ["HOME"] = f"/home/{username}"
            os.environ["XDG_RUNTIME_DIR"] = runtime_dir
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"

            # Determine selected session type
            selected_session = self.session_combo.currentData() or "x11"

            # Persist user choice to user configuration
            user_config_dir = f"/home/{username}/.config/vice-os"
            os.makedirs(user_config_dir, exist_ok=True)
            try:
                with open(f"{user_config_dir}/session.conf", "w") as f:
                    f.write(f'# Vice OS User Session Preference\nSESSION_TYPE="{selected_session}"\n')
            except Exception:
                pass

            session_script = "/opt/vice-os/wayland_session.sh" if selected_session == "wayland" else "/opt/vice-os/dbus_session.sh"

            # Start the session process to ensure audio/dbus work
            self.session_process = QProcess(self)
            self.session_process.setProcessChannelMode(QProcess.ForwardedChannels)
            self.session_process.finished.connect(QApplication.quit)

            self.session_process.start(session_script)

        except Exception as e:
            log_error(f"Failed to start session: {e}")
            # Fallback to xterm so the user isn't stranded on a black screen
            subprocess.Popen(["xterm", "-e", "bash"], env=os.environ)
            sys.exit(1)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AnimatedLogin()
    ex.showFullScreen()
    ex.raise_()
    ex.activateWindow()
    ex.pwd.setFocus()
    sys.exit(app.exec_())
