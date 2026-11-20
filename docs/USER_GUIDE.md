# User Guide - GTA VI OS (Vice OS)

Welcome to Vice OS! This guide will help you navigate and master the Neon Miami desktop environment.

---

## 🖥️ The Desktop Environment

Vice OS offers two session profiles:
1. **X11 Session**: Openbox stacking window manager combined with a custom PyQt5 desktop shell and panel.
2. **Wayland Session**: Modern `labwc` compositor providing Wayland performance, `swaybg` wallpaper, and `swayidle`/`swaylock` security.

### TopBar & Panel
- **System Metrics**: Real-time CPU, RAM, and disk utilization monitors.
- **System Tray**: NetworkManager (`nm-applet`), PipeWire volume (`pavucontrol`), and battery indicator.
- **Clock**: Date and time with quick calendar flyout.
- **Exit**: Click the logout button to open the Vice Session Manager dialog.

### Dock
Located at the bottom of the screen, the dock provides quick access to frequently used applications:
- Vice Terminal / xterm
- Firefox Web Browser
- Thunar File Manager
- Vice Settings Center
- Vice Software Center

---

## ⌨️ Keyboard Shortcuts

### Window Management
- `Super + Space`: Open Run Menu / Application Launcher
- `Super + T`: Open Terminal
- `Super + E`: Open File Manager
- `Super + F`: Open Web Browser
- `Super + D`: Show Desktop (Minimize all windows)
- `Alt + Tab`: Cycle through open windows
- `Alt + F4`: Close active window
- `Super + Left`: Snap window to left half
- `Super + Right`: Snap window to right half
- `Super + Up`: Maximize window
- `Super + Down`: Unmaximize / Restore window

### Session & Locking
- `Super + L` or `Ctrl + Alt + L`: Lock screen (`swaylock` under Wayland, or session locker under X11)
- `Ctrl + Alt + Del`: Launch Vice Task Manager

### Media & Hardware Keys
- `Volume Up / Down / Mute`: Adjust system volume via PipeWire
- `Brightness Up / Down`: Adjust display backlight
- `Print Screen`: Launch Vice Screenshot tool

---

## ⚙️ Vice OS Settings & Control Center

### Graphical Settings Center (`vice_settings.py`)
Launch from the dock or run menu. Features 28 dedicated configuration pages:
- **Display**: Resolution, refresh rate, rotation, multi-monitor layout.
- **Sound**: Default output/input devices, per-app volume sliders.
- **Appearance & Themes**: 8 neon color presets, fonts, icon themes.
- **Network**: Wi-Fi connections, VPN profiles, network shares.
- **Power**: Battery health, power profiles, sleep/suspend timeouts.
- **Diagnostics**: 19-test hardware and system integrity suite.

### TUI Administration Menu (`vice-os-menu.sh`)
For terminal environments:
```bash
sudo /usr/local/bin/vice-os-menu.sh
```

---

## 📦 Installing & Managing Applications

- **Vice Software Center** (`vice_software_center.py`): Discover and install Debian packages and Flatpak applications.
- **Flatpak Integration**: Enable thousands of sandboxed applications via `vp-flatpak.sh`.
- **APT Package Manager**: Standard Debian commands:
  ```bash
  sudo apt update && sudo apt install <package-name>
  ```
