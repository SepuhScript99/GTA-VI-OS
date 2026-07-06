#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Desktop Shell
Provides a dynamic TopBar (with CPU/RAM), Dock, and Application Search Menu.
Uses lib.python.vice_utils for system metrics and command execution.
"""

import sys
import os
import time
import argparse
import shlex
import shutil

# Add the project lib directory to the system path to import shared modules
sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, 
    QHBoxLayout, QVBoxLayout, QLineEdit, QShortcut
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence

# Import shared utilities
from python.vice_utils import launch_command, get_cpu_usage, get_ram_usage, log_info, log_error

STYLE_FILE = "/opt/vice-os/style.qss"

class RunMenu(QWidget):
    """Quick search/run menu triggered by W-space."""
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Run Command")
        self.setObjectName("RunMenu")
        
        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display RunMenu.")
            sys.exit(1)
        
        geo = screen.geometry()
        self.setGeometry(geo.width() // 2 - 200, geo.height() // 3, 400, 50)

        layout = QVBoxLayout()
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Type command and press Enter...")
        self.input_field.returnPressed.connect(self.run_command)
        self.input_field.textChanged.connect(self.clear_error)
        
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.close)
        
        layout.addWidget(self.input_field)
        self.setLayout(layout)

    def clear_error(self):
        self.input_field.setStyleSheet("") # Reset to QSS default

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
        self.input_field.setStyleSheet("border: 2px solid #FF0000; color: #FF0000;")
        self.input_field.setText(message)

    def focusOutEvent(self, event):
        """Close the menu if it loses focus."""
        # Small delay to allow keybind presses to settle
        QTimer.singleShot(100, self.check_focus)

    def check_focus(self):
        if not self.isActiveWindow():
            self.close()

class Dock(QWidget):
    """Application dock at the bottom of the screen."""
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # Prevent the dock from stealing focus on startup
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("Dock")
        
        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display Dock.")
            sys.exit(1)
            
        geo = screen.availableGeometry()
        dock_width = 400
        dock_height = 70
        x = (geo.width() - dock_width) // 2
        y = geo.height() - dock_height
        self.setGeometry(x, y, dock_width, dock_height)
        
        layout = QHBoxLayout()
        
        apps = [
            ("Terminal", "xterm"),
            ("Browser", "firefox"),
            ("Files", "thunar"),
            ("Editor", "geany")
        ]
        
        for name, cmd in apps:
            # Only show button if the application is actually installed
            if shutil.which(shlex.split(cmd)[0]):
                btn = QPushButton(name, self)
                btn.setObjectName("DockButton")
                btn.setFocusPolicy(Qt.NoFocus) # Prevent dock buttons from stealing focus
                btn.clicked.connect(lambda state, c=cmd: launch_command(c))
                layout.addWidget(btn)
            
        self.setLayout(layout)

class TopBar(QWidget):
    """System bar at the top of the screen with taskbar and clock."""
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # Prevent the topbar from stealing focus on startup
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("TopBar")
        
        screen = QApplication.primaryScreen()
        if not screen:
            log_error("No screen found. Cannot display TopBar.")
            sys.exit(1)
            
        geo = screen.availableGeometry()
        self.setGeometry(0, 0, geo.width(), 30)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        
        self.sysinfo = QLabel("CPU: 0% | RAM: 0MB", self)
        self.sysinfo.setObjectName("SysInfo")
        
        self.clock = QLabel("00:00:00", self)
        self.clock.setObjectName("Clock")
        
        # Add Logout button
        self.logout_btn = QPushButton("Exit", self)
        self.logout_btn.setObjectName("ExitButton")
        self.logout_btn.setFocusPolicy(Qt.NoFocus)
        self.logout_btn.clicked.connect(self.logout)
        
        layout.addWidget(self.sysinfo)
        layout.addStretch()
        layout.addWidget(self.clock)
        layout.addWidget(self.logout_btn)
        self.setLayout(layout)
        
        timer = QTimer(self)
        timer.timeout.connect(self.update_info)
        timer.start(1000)
        self.update_info()

    def update_info(self):
        # Display Date and Time
        self.clock.setText(time.strftime("%b %d, %H:%M:%S"))
        
        try:
            cpu_text = get_cpu_usage()
            ram_text = get_ram_usage()
            self.sysinfo.setText(f"{cpu_text} | {ram_text}")
        except Exception as e:
            log_error(f"Failed to update system info: {e}")
            self.sysinfo.setText("System info error")

    def logout(self):
        """Exits the Openbox session, which terminates the X server."""
        launch_command("openbox --exit")

def load_stylesheet(app: QApplication):
    if os.path.exists(STYLE_FILE):
        try:
            with open(STYLE_FILE, "r") as f:
                app.setStyleSheet(f.read())
        except IOError as e:
            log_error(f"Failed to read stylesheet: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Vice OS Desktop Shell")
    parser.add_argument('--menu', action='store_true', help="Open the run menu")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    load_stylesheet(app)

    if args.menu:
        menu = RunMenu()
        menu.show()
        menu.activateWindow()
        menu.input_field.setFocus()
        # If the menu is the only window, ensure the app exits when it closes
        app.setQuitOnLastWindowClosed(True)
    else:
        dock = Dock()
        bar = TopBar()
        dock.show()
        bar.show()
        # Keep running even if windows are hidden/closed (e.g., if menu is launched separately)
        app.setQuitOnLastWindowClosed(False)

    sys.exit(app.exec_())