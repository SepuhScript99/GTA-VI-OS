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
    QApplication, QWidget, QLabel, QLineEdit, 
    QVBoxLayout
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QTimer, QProcess
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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Dynamically set geometry to primary screen safely
        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display login screen.")
            sys.exit(1)
            
        geo = screen.geometry()
        self.setGeometry(geo)
        
        self.setStyleSheet("background-color: #050505;")
        
        layout = QVBoxLayout()
        label = QLabel("VICE OS")
        label.setFont(QFont("Arial", 64, QFont.Bold))
        label.setStyleSheet("color: #00FFFF;")
        label.setAlignment(Qt.AlignCenter)
        
        self.user_input = QLineEdit(self)
        self.user_input.setPlaceholderText("Username")
        self.user_input.setText("vice") # Default to vice for live iso
        self.user_input.setStyleSheet(
            "background-color: #120024; color: #FFFFFF; "
            "border: 2px solid #00FFFF; border-radius: 10px; padding: 10px;"
        )
        self.user_input.setFixedSize(300, 40)
        self.user_input.returnPressed.connect(self.pwd.setFocus)

        self.pwd = QLineEdit(self)
        self.pwd.setPlaceholderText("Password")
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setStyleSheet(
            "background-color: #120024; color: #FFFFFF; "
            "border: 2px solid #FF00FF; border-radius: 10px; padding: 10px;"
        )
        self.pwd.setFixedSize(300, 40)
        self.pwd.returnPressed.connect(self.check_pass)

        layout.addWidget(label)
        layout.addWidget(self.user_input, alignment=Qt.AlignCenter)
        layout.addWidget(self.pwd, alignment=Qt.AlignCenter)
        self.setLayout(layout)
        
        # Dynamic Animation based on screen size
        self.anim = QPropertyAnimation(label, b"geometry")
        self.anim.setDuration(1000)
        self.anim.setStartValue(QRect(0, -100, geo.width(), 100))
        self.anim.setEndValue(QRect(0, geo.height() // 4, geo.width(), 100))
        self.anim.start()

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
        """Starts the DBus/X session and monitors it for exit."""
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
            
            # Start the window manager via dbus_session.sh to ensure audio/dbus work
            self.session_process = QProcess(self)
            self.session_process.setProcessChannelMode(QProcess.ForwardedChannels)
            self.session_process.finished.connect(QApplication.quit)
            
            self.session_process.start("/opt/vice-os/dbus_session.sh")
            
        except Exception as e:
            log_error(f"Failed to start session: {e}")
            # Fallback to xterm so the user isn't stranded on a black screen
            subprocess.Popen(["xterm", "-e", "bash"], env=os.environ)
            sys.exit(1)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AnimatedLogin()
    ex.show()
    sys.exit(app.exec_())