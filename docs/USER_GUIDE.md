User Guide - GTA VI OS (Vice OS)
Welcome to Vice OS! This guide will help you navigate and use the custom Neon Miami desktop environment.

🖥️ The Desktop Environment
Vice OS uses a lightweight Openbox environment customized with a PyQt5 desktop shell.

TopBar
Located at the top of the screen, the TopBar displays:

System Info: Real-time CPU and RAM usage (Magenta).
Clock: Current date and time (Cyan).
Exit Button: Click "Exit" to log out of the session.
Dock
Located at the bottom center of the screen, the Dock contains quick-launch icons for:

Terminal (xterm)
Web Browser (firefox)
File Manager (thunar)
Editor (geany)
Note: The Dock only displays applications that are currently installed.

⌨️ Keyboard Shortcuts
Vice OS includes comprehensive keyboard shortcuts for power users.

Window Management
Super + T: Open Terminal
Super + E: Open File Manager
Super + F: Open Web Browser
Super + Space: Open Run Menu (type a command and press Enter)
Super + D: Toggle Show Desktop (Minimize/Restore all)
Alt + Tab: Cycle through windows
Alt + F4: Close active window
Super + Left: Snap window to left half
Super + Right: Snap window to right half
Super + Up: Maximize window
Super + Down: Unmaximize / Snap to bottom half
Super + V: Toggle Vertical Maximize
Desktop Navigation
Ctrl + Alt + Left/Right: Switch between virtual desktops
Media Keys
Volume Up/Down/Mute: Controls system volume (via PipeWire/PulseAudio)
Brightness Up/Down: Controls screen backlight (on laptops)
Print Screen: Launches the screenshot tool (gnome-screenshot)
🖱️ Mouse Actions
Right-Click Desktop: Opens the root menu (Applications, Settings, Exit).
Left-Click Desktop: Focuses the desktop.
Middle-Click Titlebar: Sends the window to the back.
Drag Titlebar: Moves the window.
Drag Window Border: Resizes the window.
⚙️ Vice OS Settings Menu
The Settings Menu is a text-based user interface (TUI) for system administration.

Accessing the Menu
Right-click the desktop and select Vice OS Settings.
Or, open a terminal and run sudo /usr/local/bin/vice-os-menu.sh.
Options
Install Vice OS to Disk: Launches the physical installer.
Install Visual Studio Code: Installs the VS Code editor.
Install Docker Engine: Installs Docker and Docker Compose.
Backup Home Directory: Creates a compressed archive of /home/vice.
Manual System Update: Runs apt update and apt upgrade.
Reset Network Configuration: Resets all network settings to defaults.
Reset User Password: Resets the password for a specified user (requires root).
Reinstall GRUB Bootloader: Repairs a broken GRUB installation.
Clean System Logs: Removes old journal entries and log files.
Repair Broken Packages: Fixes dpkg and apt database issues.
View System Status: Displays OS version, uptime, CPU load, memory, and disk usage.
Exit: Closes the menu.
🌐 Network Configuration
Vice OS uses NetworkManager to handle network connections.

Wi-Fi: Use nmtui in the terminal or install a network applet (like nm-applet) to connect to Wi-Fi networks.
Ethernet: Wired connections should be configured automatically via DHCP.
🔊 Audio
Vice OS uses PipeWire with PulseAudio compatibility for audio.

Volume Control: Use the media keys on your keyboard or run pavucontrol in the terminal to open the PulseAudio Volume Control panel.