#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Panel Configuration
Single source of truth for all desktop panel dimensions, positions, colors,
dock applications, and hotkey bindings.

All panel components (TopBar, Dock, RunMenu, Systray) should read their
geometry from this module rather than hardcoding values.
"""

# ──────────────────────────────────────────────
# Panel Dimensions (pixels)
# ──────────────────────────────────────────────

TOPBAR_HEIGHT = 30
"""Height of the TopBar in pixels."""

DOCK_HEIGHT = 70
"""Height of the Dock in pixels."""

DOCK_WIDTH = 400
"""Width of the Dock in pixels."""

DOCK_BUTTON_WIDTH = 90
"""Width of each dock application button in pixels."""

RUNMENU_WIDTH = 400
"""Width of the RunMenu in pixels."""

RUNMENU_HEIGHT = 50
"""Height of the RunMenu in pixels."""

SYSTRAY_WIDTH = 800
"""Maximum width of the system tray area in pixels."""

SYSTRAY_ICON_SIZE = 24
"""System tray icon size in pixels."""

# ──────────────────────────────────────────────
# Panel Positions (relative to screen)
# ──────────────────────────────────────────────

TOPBAR_X = 0
"""TopBar always starts at screen-left."""

TOPBAR_Y = 0
"""TopBar always starts at screen-top."""

DOCK_Y_OFFSET = 0
"""Dock sits at the bottom of the screen. This offset is added."""

RUNMENU_X_FRACTION = 2
"""RunMenu X position is screen_width // RUNMENU_X_FRACTION - RUNMENU_WIDTH // 2."""

RUNMENU_Y_FRACTION = 3
"""RunMenu Y position is screen_height // RUNMENU_Y_FRACTION."""

# ──────────────────────────────────────────────
# Application Dock Items
# ──────────────────────────────────────────────

DOCK_APPS = [
    ("Terminal", "xterm", "Open a terminal emulator"),
    ("Browser", "firefox", "Launch web browser"),
    ("Files", "thunar", "Open file manager"),
    ("Editor", "geany", "Launch code editor"),
]
"""
List of (label, command, tooltip) tuples for the dock.
Each entry is checked against $PATH at runtime; missing binaries are skipped.
"""

# ──────────────────────────────────────────────
# Neon Miami Color Palette
# ──────────────────────────────────────────────

COLOR_BG_DARK = "#0a0a0a"
"""Default widget background."""

COLOR_BG_PANEL = "rgba(5, 5, 5, 200)"
"""Semi-transparent panel background."""

COLOR_BG_INPUT = "#120024"
"""Input field background."""

COLOR_BG_INPUT_FOCUS = "#1a002e"
"""Input field background when focused."""

COLOR_CYAN = "#00FFFF"
"""Primary accent — cyan."""

COLOR_MAGENTA = "#FF00FF"
"""Secondary accent — magenta."""

COLOR_WHITE = "#FFFFFF"
"""Text color."""

COLOR_RED = "#FF0000"
"""Error / danger."""

COLOR_BORDER = "#FF00FF"
"""Default border — magenta."""

COLOR_BORDER_FOCUS = "#00FFFF"
"""Focused border — cyan."""

# ──────────────────────────────────────────────
# Stalonetray Configuration
# ──────────────────────────────────────────────

STALONETRAY_ARGS = [
    "--geometry", "1x1-0+0",
    "--max-geometry", f"{SYSTRAY_WIDTH}x{TOPBAR_HEIGHT}",
    "--grow-gravity", "NE",
    "--icon-gravity", "NE",
    "--window-type", "desktop",
    "--skip-taskbar",
    "--skip-pager",
    "--transparent",
    "--vertical",
    "--sticky",
    "--kludges", f"force_icons_size={SYSTRAY_ICON_SIZE}",
    "--background", "#050505",
]
"""
Command-line arguments passed to stalonetray on startup.
Geometry is dynamically sized to fit within the TopBar area.
"""

# ──────────────────────────────────────────────
# Autostart Delays (seconds)
# ──────────────────────────────────────────────

STALONETRAY_DELAY = 1.5
"""Delay between starting stalonetray and launching tray applets."""

SYSTRAY_APPLET_DELAY = 0.5
"""Delay between launching individual tray applets."""

BATTERY_POLL_INTERVAL = 30000
"""Battery status poll interval in milliseconds."""

TOPBAR_UPDATE_INTERVAL = 2000
"""TopBar system info update interval in milliseconds."""

# ──────────────────────────────────────────────
# Power Management Binaries
# ──────────────────────────────────────────────

POWER_BINARIES = {
    "loginctl": "loginctl",
    "systemctl": "systemctl",
    "openbox": "openbox",
}
"""
Canonical names for power management binaries.
Used by power_manager.py to locate system tools.
"""

# ──────────────────────────────────────────────
# Desktop Entry Paths
# ──────────────────────────────────────────────

STYLE_FILE = "/opt/vice-os/style.qss"
"""Path to the Qt stylesheet loaded by all desktop components."""

LIB_PATH = "/opt/vice-os/lib"
"""Path appended to sys.path for vice_utils imports."""

VICE_OS_DIR = "/opt/vice-os"
"""Base directory for all Vice OS desktop components."""

AUTOSTART_DIR = "/etc/xdg/autostart"
"""System-wide XDG autostart directory."""
