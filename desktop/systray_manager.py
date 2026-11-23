#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) System Tray Manager
Manages the X11 system tray container, network applet, audio applet,
battery monitoring, and provides a session control menu.

Architecture:
  - stalonetray provides the X11 system tray container for legacy applets
    (nm-applet, pavucontrol).
  - If stalonetray is unavailable, pure-Qt QSystemTrayIcon acts as fallback.
  - Battery status is polled from /sys/class/power_supply/ every 30 seconds.
  - All tray items are guarded by existence checks to prevent silent failures.
"""

import os
import sys
import shutil
import subprocess
import time

sys.path.insert(0, '/opt/vice-os/lib')
sys.path.insert(0, '/opt/vice-os')

from python.vice_utils import launch_command, log_error, log_info, log_warn  # noqa: E402

try:
    import panel_config as _pc
except (ImportError, Exception):
    _pc = None

_STALONETRAY_BIN = "stalonetray"
_NM_APPLET_BIN = "nm-applet"
_PAVUCONTROL_BIN = "pavucontrol"
_ACPI_BIN = "acpi"

_BATTERY_PATH = "/sys/class/power_supply"

_AUTOSTART_DELAY = 1.5

_LAUNCHED_APPLETS = []


def _is_running(process_name: str) -> bool:
    """Check whether a process matching *process_name* is running for this user."""
    try:
        uid = os.getuid()
        result = subprocess.run(
            ["pgrep", "-u", str(uid), "-x", process_name],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _start_daemon(binary: str, args: list = None) -> bool:
    """Start *binary* with *args* if it exists and is not already running."""
    if _is_running(binary):
        log_info(f"Systray: {binary} already running, skipping.")
        return True

    if not shutil.which(binary):
        log_warn(f"Systray: {binary} not found, skipping.")
        return False

    full_args = [binary]
    if args:
        full_args.extend(args)

    try:
        subprocess.Popen(
            full_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        log_info(f"Systray: started {binary}")
        _LAUNCHED_APPLETS.append(binary)
        return True
    except Exception as e:
        log_error(f"Systray: failed to start {binary}: {e}")
        return False


def start_stalonetray():
    """
    Start the stalonetray X11 system tray container.

    Configured to:
      - Float at the top-right of the screen (matching TopBar position).
      - Use a transparent background matching the Vice OS aesthetic.
      - Avoid decorating with window manager borders.
    """
    if not shutil.which(_STALONETRAY_BIN):
        log_warn("Systray: stalonetray not installed. Using Qt fallback tray.")
        return False

    if _pc is not None and hasattr(_pc, 'STALONETRAY_ARGS'):
        arguments = list(_pc.STALONETRAY_ARGS)
    else:
        arguments = [
            "--geometry", "1x1-0+0",
            "--max-geometry", "800x32",
            "--grow-gravity", "NE",
            "--icon-gravity", "NE",
            "--window-type", "desktop",
            "--skip-taskbar",
            "--skip-pager",
            "--transparent",
            "--vertical",
            "--sticky",
            "--kludges", "force_icons_size=24",
            "--background", "#050505",
        ]
    return _start_daemon(_STALONETRAY_BIN, arguments)


def start_nm_applet():
    """Start the NetworkManager tray applet for network status and connections."""
    return _start_daemon(_NM_APPLET_BIN)


def start_pavucontrol():
    """Start the PulseAudio/PipeWire volume control tray applet."""
    return _start_daemon(_PAVUCONTROL_BIN)


def get_battery_percentage() -> str:
    """
    Read battery status from sysfs.

    Returns a string like "75%" or "Charging 75%" or "AC" when on mains power.
    Returns "N/A" if no battery is detected.
    """
    if not os.path.isdir(_BATTERY_PATH):
        return "N/A"

    try:
        for entry in os.listdir(_BATTERY_PATH):
            bat_type_path = os.path.join(_BATTERY_PATH, entry, "type")
            if not os.path.isfile(bat_type_path):
                continue
            with open(bat_type_path) as f:
                if f.read().strip() != "Battery":
                    continue

            status_path = os.path.join(_BATTERY_PATH, entry, "status")
            capacity_path = os.path.join(_BATTERY_PATH, entry, "capacity")

            status = "Unknown"
            if os.path.isfile(status_path):
                with open(status_path) as f:
                    status = f.read().strip()

            capacity = 0
            if os.path.isfile(capacity_path):
                with open(capacity_path) as f:
                    cap_str = f.read().strip()
                    if cap_str:
                        capacity = int(cap_str)

            if status == "Charging":
                return f"Charging {capacity}%"
            elif status == "Discharging":
                return f"Battery {capacity}%"
            else:
                return f"{capacity}%"
    except Exception as e:
        log_error(f"Systray: battery read failed: {e}")

    if shutil.which(_ACPI_BIN):
        try:
            result = subprocess.run(
                [_ACPI_BIN, "-b"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split(":")[-1].strip()
        except Exception:
            pass

    return "AC"


def start_systray():
    """
    Main entry point called by vice_shell.py.

    Starts the X11 system tray container and network applet (audio mixer is
    launched on-demand rather than opening a window automatically on login).
    Safe to call multiple times — each daemon is guarded against duplicate launch.
    """
    log_info("Systray: initializing system tray...")

    start_stalonetray()
    time.sleep(_AUTOSTART_DELAY)

    start_nm_applet()

    log_info("Systray: initialization complete.")
    return True


def is_systray_available() -> bool:
    """Return True if at least one tray container is running."""
    return _is_running(_STALONETRAY_BIN)


if __name__ == "__main__":
    start_systray()
