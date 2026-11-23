#!/usr/bin/env python3
"""
Vice OS — First-Boot Setup Script
Registers all vice_*.py applications in:
  - ~/.local/share/applications/  (.desktop files)
  - ~/.config/autostart/  (autostart entries)
  - Updates desktop database (update-desktop-database)
Also creates a ~/.config/vice-os/ directory structure and
optionally sets up the panel and launcher to start on login.
"""

import glob
import os
import subprocess
import sys

DESKTOP_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
DESKTOP_APP_DIR = os.path.expanduser("~/.local/share/applications")
CONFIG_DIR = os.path.expanduser("~/.config/vice-os")

APP_METADATA = {
    "vice_settings.py": {"name": "Vice Settings Center", "comment": "System settings and preferences", "cat": "Settings"},
    "vice_task_manager.py": {"name": "Vice Task Manager", "comment": "Process management and monitoring", "cat": "Utility"},
    "vice_system_monitor.py": {"name": "Vice System Monitor", "comment": "Live system resource graphs", "cat": "Utility"},
    "vice_system_report.py": {"name": "Vice System Report", "comment": "System information report generator", "cat": "Utility"},
    "vice_service_manager.py": {"name": "Vice Service Manager", "comment": "Systemd service management", "cat": "System"},
    "vice_power_manager.py": {"name": "Vice Power Manager", "comment": "Battery, brightness, and power profiles", "cat": "System"},
    "vice_driver_manager.py": {"name": "Vice Driver Manager", "comment": "NVIDIA/AMD/WiFi driver management", "cat": "System"},
    "vice_update_manager.py": {"name": "Vice Update Manager", "comment": "APT package upgrades", "cat": "System"},
    "vice_network_monitor.py": {"name": "Vice Network Monitor", "comment": "Network interfaces, traffic, connections, and diagnostics", "cat": "Network"},
    "vice_file_manager.py": {"name": "Vice File Manager", "comment": "File browser with copy/move/delete", "cat": "Utility"},
    "vice_text_editor.py": {"name": "Vice Text Editor", "comment": "Multi-tab text editor with syntax highlighting", "cat": "Development"},
    "vice_terminal.py": {"name": "Vice Terminal", "comment": "Tabbed terminal emulator", "cat": "System"},
    "vice_screenshot.py": {"name": "Vice Screenshot Tool", "comment": "Screen capture utility", "cat": "Utility"},
    "vice_clipboard.py": {"name": "Vice Clipboard Manager", "comment": "Clipboard history with pin and search", "cat": "Utility"},
    "vice_archive_manager.py": {"name": "Vice Archive Manager", "comment": "Create and extract compressed archives", "cat": "Utility"},
    "vice_audio_manager.py": {"name": "Vice Audio Manager", "comment": "Volume, sinks, and per-app audio", "cat": "Multimedia"},
    "vice_font_manager.py": {"name": "Vice Font Manager", "comment": "Install and preview system fonts", "cat": "Utility"},
    "vice_display_manager.py": {"name": "Vice Display Manager", "comment": "Screen resolution and multi-monitor", "cat": "Hardware"},
    "vice_disk_manager.py": {"name": "Vice Disk Manager", "comment": "Partition and disk usage management", "cat": "Hardware"},
    "vice_bluetooth_manager.py": {"name": "Vice Bluetooth Manager", "comment": "Bluetooth device pairing and connections", "cat": "Hardware"},
    "vice_firewall_manager.py": {"name": "Vice Firewall Manager", "comment": "UFW firewall rule management", "cat": "Security"},
    "vice_software_center.py": {"name": "Vice Software Center", "comment": "APT and Flatpak package manager", "cat": "System"},
    "vice_package_search.py": {"name": "Vice Package Search", "comment": "Browse and install packages", "cat": "System"},
    "vice_iso_validator.py": {"name": "Vice ISO Validator", "comment": "ISO build validation GUI", "cat": "Development"},
    "vice_diagnostics.py": {"name": "Vice Diagnostics", "comment": "Hardware and network diagnostics", "cat": "System"},
    "vice_user_manager.py": {"name": "Vice User Manager", "comment": "Add/remove users and groups", "cat": "System"},
    "vice_notif_history.py": {"name": "Vice Notification History", "comment": "View and manage notification log", "cat": "Utility"},
    "vice_launcher.py": {"name": "Vice Application Launcher", "comment": "Application menu with categories", "cat": "Utility"},
    "vice_panel.py": {"name": "Vice Panel", "comment": "Top taskbar with clock and tray", "cat": "System"},
    "vice_widgets.py": {"name": "Vice Desktop Widgets", "comment": "Clock, stats, and weather widgets", "cat": "Utility"},
    "vice_session_manager.py": {"name": "Vice Session Manager", "comment": "Logout, lock, reboot, shutdown", "cat": "System"},
    "vice_log_viewer.py": {"name": "Vice Log Viewer", "comment": "Browse journald and /var/log", "cat": "Utility"},
    "vice_keyboard_shortcuts.py": {"name": "Vice Keyboard Shortcuts", "comment": "View and edit keybindings", "cat": "Settings"},
    "vice_mouse_settings.py": {"name": "Vice Mouse & Touchpad", "comment": "Pointer speed and touchpad options", "cat": "Settings"},
    "vice_accessibility.py": {"name": "Vice Accessibility", "comment": "Font scale, contrast, sticky keys", "cat": "Settings"},
    "vice_usb_manager.py": {"name": "Vice USB Manager", "comment": "USB auto-mount daemon control", "cat": "Hardware"},
    "vice_vpn_manager.py": {"name": "Vice VPN Manager", "comment": "OpenVPN and WireGuard profiles", "cat": "Network"},
    "vice_network_shares.py": {"name": "Vice Network Shares", "comment": "SMB/CIFS and NFS share mounts", "cat": "Network"},
    "vice_backup_scheduler.py": {"name": "Vice Backup Scheduler", "comment": "Cron-based backup jobs", "cat": "Utility"},
    "vice_log_rotation.py": {"name": "Vice Log Rotation", "comment": "Logrotate config management", "cat": "System"},
    "vice_sysinfo_exporter.py": {"name": "Vice System Info Export", "comment": "Export inventory to JSON/CSV/HTML", "cat": "Utility"},
    "vice_printer_manager.py": {"name": "Vice Printer Manager", "comment": "CUPS printers and print queue", "cat": "Hardware"},
    "vice_theme_manager.py": {"name": "Vice Theme Manager", "comment": "Color themes, fonts, icon themes", "cat": "Settings"},
    "vice_openbox_editor.py": {"name": "Vice Openbox Editor", "comment": "Window manager keybindings and config", "cat": "Settings"},
    "vice_notification_daemon.py": {"name": "Vice Notification Daemon", "comment": "D-Bus notification server", "cat": "System"},
    "vice_calendar.py": {"name": "Vice Calendar & Clock", "comment": "Month view, events, world clock", "cat": "Utility"},
    "vice_calculator.py": {"name": "Vice Calculator", "comment": "Basic and scientific calculator", "cat": "Utility"},
    "vice_image_viewer.py": {"name": "Vice Image Viewer", "comment": "Browse, zoom, rotate, slideshow", "cat": "Multimedia"},
    "vice_startup_apps.py": {"name": "Vice Startup Apps", "comment": "Autostart entry manager", "cat": "Settings"},
    "vice_media_player.py": {"name": "Vice Media Player", "comment": "mpv frontend with playlist", "cat": "Multimedia"},
    "vice_file_search.py": {"name": "Vice File Content Search", "comment": "Recursive text search", "cat": "Utility"},
    "vice_disk_usage.py": {"name": "Vice Disk Usage Analyzer", "comment": "Folder size visualization", "cat": "System"},
    "vice_cron_manager.py": {"name": "Vice Cron Job Manager", "comment": "Visual crontab editor", "cat": "System"},
    "vice_pdf_viewer.py": {"name": "Vice PDF Viewer", "comment": "PDF reader via poppler", "cat": "Utility"},
    "vice_wifi_connect.py": {"name": "Vice WiFi Connect", "comment": "Scan and connect WiFi networks", "cat": "Network"},
    "vice_ssh_manager.py": {"name": "Vice SSH Manager", "comment": "Saved SSH sessions and key management", "cat": "Network"},
    "vice_screen_recorder.py": {"name": "Vice Screen Recorder", "comment": "ffmpeg screen capture with audio", "cat": "Multimedia"},
    "vice_checksum.py": {"name": "Vice Checksum Verifier", "comment": "MD5/SHA hash and SHA256SUMS verify", "cat": "Utility"},
    "vice_wallpaper_picker.py": {"name": "Vice Wallpaper Picker", "comment": "Browse and set wallpapers (X11/Wayland)", "cat": "Settings"},
    "vice_kernel_manager.py": {"name": "Vice Kernel Manager", "comment": "Installed kernels, boot default, purge", "cat": "System"},
    "vice_cleanup.py": {"name": "Vice System Cleanup", "comment": "Reclaim disk space safely", "cat": "System"},
    "vice_trash_manager.py": {"name": "Vice Trash Manager", "comment": "View, restore, empty trash", "cat": "Utility"},
    "vice_help_viewer.py": {"name": "Vice Help", "comment": "Documentation and app reference", "cat": "Utility"},
    "vice_speedtest.py": {"name": "Vice Network Speed Test", "comment": "Internet and LAN speed testing", "cat": "Network"},
    "vice_disk_benchmark.py": {"name": "Vice Disk Benchmark", "comment": "dd-based read/write speed tests", "cat": "System"},
}


def create_desktop_file(app_name, meta):
    filename = f"vice-{app_name.replace('.py', '.desktop')}"
    filepath = os.path.join(DESKTOP_APP_DIR, filename)
    os.makedirs(DESKTOP_APP_DIR, exist_ok=True)

    script_path = os.path.join(DESKTOP_DIR, app_name)
    executable = sys.executable

    icon = meta.get("icon", "applications-other")
    if icon == "applications-other":
        try:
            from vice_launcher import APP_LABELS
            if app_name in APP_LABELS:
                icon = APP_LABELS[app_name][1]
        except Exception:
            pass

    content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={meta['name']}
Comment={meta['comment']}
Exec={executable} {script_path}
Icon={icon}
Terminal=false
Categories={meta['cat']};
StartupNotify=true
X-GNOME-Autostart-enabled=false
"""

    try:
        with open(filepath, "w") as f:
            f.write(content)
        return True, filepath
    except Exception as e:
        return False, str(e)


def create_autostart_entry(filename, exec_cmd, enable=False):
    filepath = os.path.join(AUTOSTART_DIR, filename)
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={filename.replace('.desktop', '')}
Exec={exec_cmd}
Icon=computer
Terminal=false
X-GNOME-Autostart-enabled={'true' if enable else 'false'}
"""
    try:
        with open(filepath, "w") as f:
            f.write(content)
        return True, filepath
    except Exception as e:
        return False, str(e)


def update_desktop_database():
    try:
        r = subprocess.run(
            ["update-desktop-database", DESKTOP_APP_DIR],
            capture_output=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False


def setup_vice_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # Create theme config
    theme_conf = os.path.join(CONFIG_DIR, "theme.json")
    if not os.path.exists(theme_conf):
        with open(theme_conf, "w", encoding="utf-8", newline="\n") as f:
            f.write('{"name": "Leonida Dusk", "primary": "#FF5E7E", "accent": "#36D6C3", "bg": "#0D0E15", "fg": "#F5F6FA"}\n')

    # Create panel config
    panel_conf = os.path.join(CONFIG_DIR, "panel.conf")
    if not os.path.exists(panel_conf):
        with open(panel_conf, "w") as f:
            f.write("[Panel]\nauto_start=true\nposition=top\nheight=36\n")

    # Create launcher config
    launcher_conf = os.path.join(CONFIG_DIR, "launcher.conf")
    if not os.path.exists(launcher_conf):
        with open(launcher_conf, "w") as f:
            f.write("[Launcher]\nauto_start=true\nshow_favorites=true\ndefault_category=All\n")


def main():
    print("=" * 55)
    print("  Vice OS — First-Boot Application Setup")
    print("=" * 55)
    print()

    setup_vice_config()
    print("[*] Vice OS config directory initialized")

    created = 0
    failed = 0

    app_files = glob.glob(os.path.join(DESKTOP_DIR, "vice_*.py"))
    print(f"\n[*] Found {len(app_files)} Vice OS applications")

    for app_path in sorted(app_files):
        app_name = os.path.basename(app_path)
        meta = APP_METADATA.get(app_name, {
            "name": app_name.replace("vice_", "").replace(".py", "").replace("_", " ").title(),
            "comment": "Vice OS application",
            "cat": "Utility",
        })

        ok, result = create_desktop_file(app_name, meta)
        if ok:
            print(f"  [+] {meta['name']:40s} -> {os.path.basename(result)}")
            created += 1
        else:
            print(f"  [!] {meta['name']:40s} FAILED: {result}")
            failed += 1

    # Register essential autostart entries
    print("\n[*] Setting up autostart entries...")
    essential = [
        ("vice-panel.desktop", f"{sys.executable} {os.path.join(DESKTOP_DIR, 'vice_panel.py')}", False),
        ("vice-launcher.desktop", f"{sys.executable} {os.path.join(DESKTOP_DIR, 'vice_launcher.py')}", False),
        ("vice-widgets.desktop", f"{sys.executable} {os.path.join(DESKTOP_DIR, 'vice_widgets.py')}", False),
    ]
    for fname, exec_cmd, enable in essential:
        ok, result = create_autostart_entry(fname, exec_cmd, enable)
        if ok:
            status = "enabled" if enable else "disabled"
            print(f"  [+] {fname} ({status}, not auto-started)")
        else:
            print(f"  [!] {fname} FAILED: {result}")

    # Update desktop database
    print("\n[*] Updating desktop database...")
    if update_desktop_database():
        print("  [+] Desktop database updated")
    else:
        print("  [!] update-desktop-database not available (non-GNOME system)")

    print()
    print("=" * 55)
    print(f"  Done: {created} desktop entries created, {failed} failed")
    print("  Desktop entries: ~/.local/share/applications/")
    print("  Autostart:        ~/.config/autostart/")
    print("  Vice config:      ~/.config/vice-os/")
    print("=" * 55)
    print()
    print("Run 'vice-launcher.py' to open the app menu.")
    print("Add 'vice_panel.py' to your display manager or autostart to")
    print("automatically start the panel on login.")


if __name__ == "__main__":
    main()
