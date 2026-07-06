Frequently Asked Questions (FAQ) - GTA VI OS (Vice OS)
🖥️ System & Architecture
Q: What is Vice OS built on?A: Vice OS is built on a minimal Debian 12 (Bookworm) base. It uses the Openbox window manager and a custom PyQt5 desktop shell (vice_shell.py) to achieve a lightweight, neon Miami aesthetic without the bloat of GNOME or KDE.

Q: Why use Openbox instead of a modern desktop environment?A: Openbox is incredibly lightweight (using <1GB RAM at idle) and highly scriptable. It allows Vice OS to boot in under 15 seconds on an SSD while maintaining full control over the UI via Python and Qt.

🌐 Networking & Hardware
Q: How do I connect to Wi-Fi?A: By default, Vice OS uses NetworkManager. You can connect via the terminal by running nmtui (Text User Interface) or nmcli. If you installed a network applet, it will appear in the system tray.

Q: Why doesn't my screen resolution auto-adjust in VirtualBox/VMware?A: Ensure you have the Guest Additions (VirtualBox) or Open VM Tools (VMware) installed. Vice OS includes open-vm-tools and virtualbox-guest-utils in the ISO by default. If resolution still doesn't adjust, try restarting the VM.

Q: My laptop function keys (volume, brightness) don't work.A: Vice OS maps standard XF86 media keys. If your laptop requires specific drivers or proprietary firmware, you may need to install them via sudo apt install <firmware-package>.

🎨 Desktop & UI
Q: How do I change my wallpaper?A: Right-click the desktop and select "Terminal". Run nitrogen /usr/share/backgrounds to open the graphical wallpaper picker.

Q: How do I install new applications?A: You can use standard Debian package managers (apt, synaptic). Additionally, you can use the "Vice OS Settings" menu (right-click desktop -> Vice OS Settings) to quickly install developer tools like VS Code or Docker.

Q: The terminal looks weird/different. Why?A: The default terminal is xterm, themed via .Xresources to match the neon aesthetic. If you prefer a different terminal like xfce4-terminal or alacritty, you can install it via apt and launch it from the right-click Applications menu.

⚙️ Performance & Maintenance
Q: Does Vice OS support disk-based swap?A: No. Vice OS uses ZRAM (compressed RAM) for swap by default to reduce SSD wear and improve performance. Disk-based swap (dphys-swapfile) is intentionally disabled.

Q: How are system updates handled?A: Updates are handled automatically in the background by a systemd timer (vp-autoupdate.timer) which runs daily. It uses apt to upgrade packages and clean up unused dependencies. You can manually trigger updates via the "Vice OS Settings" menu.

Q: Is my Live USB session persistent?A: No. The Live ISO is read-only (SquashFS). Any changes made during the Live session are lost on reboot. To save your data, you must install Vice OS to a physical disk using the "Vice OS Settings" -> "Install Vice OS to Disk" option.