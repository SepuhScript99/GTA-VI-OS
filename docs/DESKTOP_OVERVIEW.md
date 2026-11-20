# Desktop Environment Overview

The `desktop/` directory contains 81 components that form the Vice OS desktop experience:
a core shell/panel, multi-session management (X11 Openbox + Wayland Labwc), and a full application suite.
All components use PyQt5 and share a common QSS stylesheet (`style.qss`).

---

## Core Components

| File | Purpose |
|------|---------|
| `vice_shell.py` | Main desktop shell — TopBar (CPU/RAM/Disk metrics), Dock, RunMenu (Win+Space). Includes global exception handler and auto-restart integration. Session-aware logout. |
| `login.py` | Animated login screen and display manager greeter. Features an integrated X11 / Wayland session selection dropdown, authenticates via `su`, and persists session preference to `~/.config/vice-os/session.conf`. |
| `wayland_session.sh` | Wayland session launcher using the `labwc` compositor, `swaybg` wallpaper, `swayidle`/`swaylock` idle screen locking, and session-aware shell. |
| `dbus_session.sh` | X11 session initializer — D-Bus, Xresources, PipeWire/PulseAudio, and session watchdog. Launched by `login.py` before Openbox. |
| `style.qss` | Global Qt6-compatible stylesheet implementing the Neon Miami aesthetic (cyan/magenta). Covers all standard Qt widgets. |

---

## Panel Components

| File | Purpose |
|------|---------|
| `panel_config.py` | Shared configuration — panel dimensions, colors, dock apps, stalonetray args. Single source of truth for all panel geometry. |
| `systray_manager.py` | System tray manager — starts stalonetray, nm-applet, pavucontrol. Reads battery via sysfs with ACPI fallback. |
| `power_manager.py` | Power management — battery indicator, suspend/reboot/shutdown via logind with systemctl fallback. TopBar widgets. |
| `wallpaper_manager.py` | Multi-backend wallpaper management — nitrogen (primary) -> feh (fallback) -> swaybg (Wayland) -> asset generator (last resort). |

---

## Session Management

| File | Purpose |
|------|---------|
| `session_watchdog.py` | Monitors `vice_shell.py`, auto-restarts on crash with exponential backoff. Max 10 restarts, then alerts. |
| `ob_menu.py` | Openbox pipe menu generator. Reads `.desktop` files and outputs Openbox XML menu. |
| `vice_session_manager.py` | Session manager dialog — lock, logout, user switch, suspend, reboot, shutdown. |

---

## User-Facing Applications

| File | Purpose |
|------|---------|
| `welcome_wizard.py` | First-boot setup wizard (9 pages: user, timezone, locale, keyboard, Wi-Fi, theme, software). Runs once; flag file prevents re-run. |
| `welcome_wizard.sh` | Launcher script that checks flag file before starting wizard. |
| `vice_settings.py` | GUI Settings Center (28 pages incl. Diagnostics, Drivers, Display, Sound, Users, Power). |
| `vice_setup_apps.py` | First-boot registration: generates `.desktop` entries + autostart entries for all apps. |
| `vice_launcher.py` | Full-screen app launcher — categories, search, favorites, auto-discovery. |
| `vice_panel.py` | Top taskbar — launcher button, quick-launch, window list with wmctrl, tray, clock, quick actions. |
| `vice_widgets.py` | Draggable desktop widgets — clock, system stats, weather placeholder. |
| `vice_notification_daemon.py` | `org.freedesktop.Notifications` D-Bus server with popup stacking and JSON history. |
| `vice_notif_history.py` | Notification history viewer (dismiss, clear, export). |
| `vice_system_notifier.py` | Background monitor alerting on battery, disk, and thermal thresholds via `notify-send`. |

### System Tools
| File | Purpose |
|------|---------|
| `vice_task_manager.py` | Process list, kill/term/stop/cont, renice, CPU/mem bars. |
| `vice_system_monitor.py` | Live CPU/memory/network/disk graphs from `/proc`. |
| `vice_system_report.py` | System report generator (Overview/Details/Processes tabs). |
| `vice_sysinfo_exporter.py` | 26-section inventory export to JSON/CSV/HTML. |
| `vice_service_manager.py` | systemd unit list, start/stop/enable/disable. |
| `vice_update_manager.py` | apt upgradable list, changelog preview, upgrade runner. |
| `vice_driver_manager.py` | NVIDIA/AMD/Intel/WiFi/Bluetooth driver detect/install. |
| `vice_diagnostics.py` | 19-test diagnostics center with run-all and export. |
| `vice_log_viewer.py` | Journal + `/var/log` browser, regex filter, follow. |
| `vice_log_rotation.py` | logrotate config editor, test/force-rotate. |
| `vice_cron_manager.py` | Visual crontab editor with presets and raw tab. |
| `vice_backup_scheduler.py` | rsync/tar/7z backup jobs with cron sync, retention. |
| `vice_disk_usage.py` | Folder size scanner with drill-down visualization. |
| `vice_disk_benchmark.py` | Read/write disk performance benchmark. |
| `vice_kernel_manager.py` | Installed kernels browser, GRUB default kernel setter, safe purge. |
| `vice_cleanup.py` | System cleaner (apt cache, autoremove, thumbnails, journal, trash). |
| `vice_iso_validator.py` | GUI runner for `validation/` scripts. |
| `vice_power_manager.py` | Battery, brightness, power profiles, scheduled shutdown. |

### Files & Media
| File | Purpose |
|------|---------|
| `vice_file_manager.py` | File browser with bookmarks, copy/cut/paste, context menu, XDG trash support. |
| `vice_file_search.py` | Recursive content search (regex, filters, preview, export). |
| `vice_text_editor.py` | Multi-tab editor, Python/Bash highlighting, find/replace. |
| `vice_terminal.py` | Tabbed terminal with 5 neon themes and shell selector. |
| `vice_archive_manager.py` | Create/extract zip/tar/7z with progress log. |
| `vice_screenshot.py` | Full/window/region capture, delay, clipboard copy. |
| `vice_screen_recorder.py` | ffmpeg x11grab screen recorder (fullscreen/window/region with audio). |
| `vice_media_player.py` | mpv IPC frontend — playlist, seek, repeat, volume. |
| `vice_image_viewer.py` | Browse folder, zoom, rotate, slideshow. |
| `vice_pdf_viewer.py` | Poppler-based PDF viewer with page nav and DPI zoom. |
| `vice_audio_manager.py` | Volume, default sink/source, per-app streams. |
| `vice_font_manager.py` | Font preview and install. |
| `vice_calendar.py` | Month calendar with events, world clocks. |
| `vice_calculator.py` | Basic + scientific calculator with history tape. |
| `vice_clipboard.py` | Lightweight clipboard tool. |
| `vice_clipboard_manager.py` | Extended clipboard history manager with pin, search, persistence. |
| `vice_checksum.py` | Checksum generator/verifier (MD5, SHA1, SHA256, SHA512, batch verify). |
| `vice_trash_manager.py` | XDG trash bin manager with file restore and purge. |

### Hardware & Network
| File | Purpose |
|------|---------|
| `vice_display_manager.py` | xrandr resolution/refresh/rotation/multi-monitor. |
| `vice_disk_manager.py` | Partition viewer, mount/unmount, usage bars. |
| `vice_bluetooth_manager.py` | Scan, pair, connect, remove devices. |
| `vice_usb_manager.py` | USB auto-mount daemon control + mount/eject GUI. |
| `vice_printer_manager.py` | CUPS printers, print queue, test page. |
| `vice_firewall_manager.py` | UFW rule viewer, add/delete, enable/disable. |
| `vice_vpn_manager.py` | OpenVPN/WireGuard profile manager. |
| `vice_network_shares.py` | SMB/CIFS and NFS share mounts. |
| `vice_network_monitor.py` | Real-time network throughput and interface monitor. |
| `vice_wifi_connect.py` | nmcli Wi-Fi scan, connect, and hotspot configuration GUI. |
| `vice_ssh_manager.py` | Saved SSH connections, key manager, ed25519 generation, terminal launch. |
| `vice_speedtest.py` | Network download/upload speed and ping tester. |

### Admin & Settings
| File | Purpose |
|------|---------|
| `vice_user_manager.py` | Users, groups, sudo toggle, password change. |
| `vice_software_center.py` | apt/flatpak package management GUI with categories and search. |
| `vice_package_search.py` | apt + flatpak search with package details and install. |
| `vice_keyboard_shortcuts.py` | Keybinding manager with JSON persistence. |
| `vice_mouse_settings.py` | Touchpad/mouse speed, tap-to-click, gestures. |
| `vice_accessibility.py` | Font scale, high contrast, sticky/slow/bounce keys. |
| `vice_theme_manager.py` | 8 color themes, fonts, icon themes, QSS generation. |
| `vice_openbox_editor.py` | Openbox rc.xml keybinding and window rules editor with backup. |
| `vice_startup_apps.py` | XDG autostart application editor. |
| `vice_wallpaper_picker.py` | Wallpaper selection grid with multi-backend session awareness. |
| `vice_help_viewer.py` | Integrated documentation viewer and man-page browser. |

---

## Boot Theming

| File | Location | Purpose |
|------|----------|---------|
| `vice_grub_theme.sh` | recovery/ | Cyberpunk GRUB boot menu theme installer. |
| `vice_plymouth_theme.sh` | recovery/ | Plymouth boot splash (static + animated glow). |

---

## Integration Points

### Installation:
- All `.py` and `.sh` files are copied to `/opt/vice-os/` by `chroot_scripts/03_user_setup.sh`.
- Desktop entries in `config/*.desktop` are installed by `chroot_scripts/04_desktop_autostart.sh`.
- The QSS stylesheet is loaded by `vice_shell.py`, `vice_settings.py`, and all apps at startup.

### Logging:
- All components use `lib/python/vice_utils.py` for `log_info`, `log_success`, `log_warn`, `log_error`.
- Logs go to stdout/stderr (captured by systemd journal in session).

### Error Handling:
- `vice_shell.py` installs a global `sys.excepthook` for crash recovery.
- All optional modules (systray, power, wallpaper) are imported with try/except guards.
- `session_watchdog.py` auto-restarts the shell on crash.
