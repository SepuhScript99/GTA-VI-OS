# Frequently Asked Questions (FAQ) - GTA VI OS (Vice OS)

---

## 🖥️ System & Architecture

### Q: What is Vice OS built on?
**A:** Vice OS is built on a minimal Debian 12 (Bookworm) base. It provides a dual-session architecture supporting both an ultra-lightweight X11 session (Openbox + custom PyQt5 desktop shell) and an opt-in Wayland session (Labwc compositor + swaybg + swayidle/swaylock).

### Q: Why use Openbox and Labwc instead of heavy environments like GNOME or KDE?
**A:** Openbox and Labwc provide exceptional performance and minimal footprint (using under 1GB RAM at idle). They boot in seconds while giving the custom PyQt5 desktop environment full control over UI theming, system tray integration, widgets, and window management without desktop bloat.

### Q: Can I run Vice OS under Wayland?
**A:** Yes. Wayland support is built-in using the `labwc` compositor. You can switch sessions using the session selector dropdown in the graphical login greeter (`login.py`) or by editing `/etc/vice-os/session.conf` (or `~/.config/vice-os/session.conf`).

### Q: Does Vice OS support ARM64 or Raspberry Pi?
**A:** Yes. Vice OS includes dedicated ARM64 build configurations (`config/packages.arm64.list`), Raspberry Pi firmware configurations (`config/rpi/`), U-Boot boot scripts, and chroot setup scripts (`chroot_scripts/47_rpi_arm64_setup.sh`).

---

## 🌐 Networking & Hardware

### Q: How do I connect to Wi-Fi?
**A:** You can connect using:
1. **Graphical Wi-Fi Tool**: Launch `vice_wifi_connect.py` from the Dock, Settings, or RunMenu.
2. **System Tray**: Click the NetworkManager applet (`nm-applet`) in the top system tray.
3. **Terminal UI**: Run `nmtui` in any terminal.
4. **Command Line**: Run `network_manager.sh wifi-connect <SSID> <password>` or `nmcli`.

### Q: Why doesn't screen resolution auto-adjust in VirtualBox or VMware?
**A:** Ensure guest integration is active. Vice OS includes both `open-vm-tools` and `virtualbox-guest-utils` in the default package list. You can also adjust resolutions dynamically using the **Vice Display Manager** (`vice_display_manager.py`) or via `xrandr`.

### Q: Do laptop media keys (volume, brightness) work?
**A:** Yes. Vice OS maps standard XF86 audio and brightness keys through Openbox and Labwc configuration. Volume adjusts PipeWire streams and brightness calls `power_manager.sh`.

---

## 🎨 Desktop & UI

### Q: How do I change the wallpaper?
**A:** Open the **Vice Wallpaper Picker** (`vice_wallpaper_picker.py`) from the Settings Center or run menu. It detects your session automatically: Nitrogen/Feh for X11, or Swaybg for Wayland.

### Q: How do I install new applications?
**A:** You have multiple options:
1. **Vice Software Center** (`vice_software_center.py`): Graphical app store for Debian packages and Flatpak apps.
2. **Flatpak**: Run `vp-flatpak.sh` to enable Flathub and install sandboxed applications.
3. **Standard APT**: Use `sudo apt install <package>` in the terminal.
4. **Settings Menu**: Quickly install tools like VS Code or Docker via the Settings Center or `vp-code.sh`/`vp-docker.sh`.

### Q: Which terminal emulator is default?
**A:** Vice OS provides **Vice Terminal** (`vice_terminal.py`), a multi-tabbed terminal with 5 neon color presets. The system also includes `xterm`, customized via `.Xresources` to match the Neon Miami aesthetic.

---

## ⚙️ Performance & Maintenance

### Q: Does Vice OS support disk-based swap?
**A:** Vice OS uses ZRAM (compressed in-memory swap) by default to eliminate SSD wear and provide near-instant page swapping. Traditional disk swap (`dphys-swapfile`) is intentionally disabled.

### Q: How are system updates handled?
**A:** Updates are automatically checked and downloaded in the background via the `vp-autoupdate.timer` systemd service. You can also review changelogs and run updates interactively using **Vice Update Manager** (`vice_update_manager.py`) or `update_manager.sh`.

### Q: Is the Live USB session persistent?
**A:** The standard Live ISO session runs from a read-only SquashFS image in RAM; changes are reset upon reboot. To preserve your data and customizations, install Vice OS to disk using `sudo vp-installer.sh` or the "Install Vice OS to Disk" launcher.
