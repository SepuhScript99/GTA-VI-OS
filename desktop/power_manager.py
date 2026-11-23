#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Power Manager
Provides battery status display, system suspend/hibernate/reboot/shutdown,
and session logout for the desktop shell.

Architecture:
  - systemd-logind (loginctl) is the primary interface for session control.
  - systemctl is the fallback if logind is unavailable.
  - Battery status is read from /sys/class/power_supply/ with acpi fallback.
  - All operations are guarded by existence checks and error handling.
"""

import os
import shutil
import subprocess
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QPushButton

sys.path.insert(0, '/opt/vice-os/lib')
sys.path.insert(0, '/opt/vice-os')

from python.vice_utils import launch_command, log_error, log_info, log_warn  # noqa: E402

_LOGIND_BIN = "loginctl"
_SYSTEMCTL_BIN = "systemctl"
_OPENBOX_BIN = "openbox"
_BATTERY_PATH = "/sys/class/power_supply"
_ACPI_BIN = "acpi"

_BATTERY_POLL_MS = 30000


def _session_command(command: str) -> bool:
    """
    Execute a session/power command via logind or systemctl.

    Priority:
      1. loginctl <command>  (systemd-logind — modern, desktop-friendly)
      2. systemctl <command>  (fallback)
    """
    if shutil.which(_LOGIND_BIN):
        try:
            result = subprocess.run(
                [_LOGIND_BIN, command],
                capture_output=True, timeout=15
            )
            if result.returncode == 0:
                log_info(f"Power: {command} via loginctl succeeded.")
                return True
            log_warn(f"Power: loginctl {command} returned {result.returncode}. Trying systemctl fallback.")
        except Exception as e:
            log_error(f"Power: loginctl {command} failed: {e}")

    if shutil.which(_SYSTEMCTL_BIN):
        try:
            result = subprocess.run(
                [_SYSTEMCTL_BIN, command],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                log_info(f"Power: {command} via systemctl succeeded.")
                return True
            log_error(f"Power: systemctl {command} returned {result.returncode}.")
            return False
        except Exception as e:
            log_error(f"Power: systemctl {command} failed: {e}")
            return False

    log_error(f"Power: neither {_LOGIND_BIN} nor {_SYSTEMCTL_BIN} found. Cannot {command}.")
    return False


def suspend_system() -> bool:
    """Suspend to RAM (sleep)."""
    return _session_command("suspend")


def hibernate_system() -> bool:
    """Hibernate to disk."""
    return _session_command("hibernate")


def reboot_system() -> bool:
    """Reboot the system."""
    return _session_command("reboot")


def shutdown_system() -> bool:
    """Power off the system."""
    return _session_command("poweroff")


def logout_session() -> bool:
    """End the session (Wayland/labwc or X11/openbox), returning to the login screen."""
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        if shutil.which("labwc"):
            return launch_command("labwc --exit")
    if shutil.which(_OPENBOX_BIN):
        return launch_command("openbox --exit")
    if shutil.which(_LOGIND_BIN):
        return _session_command("terminate-session")
    log_error("Power: no supported window manager or session manager found to logout.")
    return False


def _read_battery_status() -> str:
    """
    Read battery status from sysfs.

    Returns a compact string like "75%", "Charging 80%", or "AC" when on
    mains power with no battery.
    """
    if not os.path.isdir(_BATTERY_PATH):
        return "AC"

    try:
        for entry in sorted(os.listdir(_BATTERY_PATH)):
            type_path = os.path.join(_BATTERY_PATH, entry, "type")
            if not os.path.isfile(type_path):
                continue
            with open(type_path) as f:
                if f.read().strip() != "Battery":
                    continue

            status = "Unknown"
            status_path = os.path.join(_BATTERY_PATH, entry, "status")
            if os.path.isfile(status_path):
                with open(status_path) as f:
                    status = f.read().strip()

            capacity = 0
            capacity_path = os.path.join(_BATTERY_PATH, entry, "capacity")
            if os.path.isfile(capacity_path):
                with open(capacity_path) as f:
                    val = f.read().strip()
                    if val:
                        capacity = int(val)

            if status == "Charging":
                return f"Chrg {capacity}%"
            elif status == "Discharging":
                return f"Bat {capacity}%"
            else:
                return f"{capacity}%"
    except Exception as e:
        log_error(f"Power: battery sysfs read failed: {e}")

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


def create_topbar_widgets(parent) -> list:
    """
    Create power management widgets for the TopBar.

    Returns a list of QWidgets:
      - Battery status label (if battery detected)
      - Suspend button
      - Reboot button
      - Shutdown button

    Each button is guarded against accidental clicks (no immediate action).
    """
    widgets = []

    battery_text = _read_battery_status()
    if battery_text != "AC":
        battery_label = QLabel(battery_text, parent)
        battery_label.setObjectName("SysInfo")
        battery_label.setToolTip("Battery status — updates every 30s")

        poll_timer = QTimer(parent)
        poll_timer.timeout.connect(lambda: _update_battery_label(battery_label))
        poll_timer.start(_BATTERY_POLL_MS)

        widgets.append(battery_label)

    suspend_btn = QPushButton("Sleep", parent)
    suspend_btn.setObjectName("ExitButton")
    suspend_btn.setFocusPolicy(Qt.NoFocus)
    suspend_btn.setToolTip("Suspend to RAM")
    suspend_btn.clicked.connect(suspend_system)
    widgets.append(suspend_btn)

    reboot_btn = QPushButton("Restart", parent)
    reboot_btn.setObjectName("ExitButton")
    reboot_btn.setFocusPolicy(Qt.NoFocus)
    reboot_btn.setToolTip("Reboot the system")
    reboot_btn.clicked.connect(reboot_system)
    widgets.append(reboot_btn)

    shutdown_btn = QPushButton("Power Off", parent)
    shutdown_btn.setObjectName("ExitButton")
    shutdown_btn.setFocusPolicy(Qt.NoFocus)
    shutdown_btn.setToolTip("Shut down the system")
    shutdown_btn.clicked.connect(shutdown_system)
    widgets.append(shutdown_btn)

    return widgets


def _update_battery_label(label: QLabel):
    """Update a battery status label with fresh data."""
    try:
        label.setText(_read_battery_status())
    except Exception as e:
        log_error(f"Power: battery label update failed: {e}")


if __name__ == "__main__":
    print(f"Battery status: {_read_battery_status()}")
