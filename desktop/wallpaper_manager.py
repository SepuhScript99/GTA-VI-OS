#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Wallpaper Manager
Applies the Vice OS branded wallpaper on desktop startup using nitrogen (primary)
with feh fallback for X11 sessions, and swaybg for Wayland sessions.
Generates procedural wallpapers via the asset generator if no wallpaper image exists.

Architecture:
  - Wayland sessions: swaybg -i <image> -m fill (native Wayland wallpaper)
  - X11 sessions:
    - nitrogen --restore is the primary method (reads ~/.config/nitrogen/bg-saved.cfg).
    - feh --bg-scale is the fallback if nitrogen is unavailable.
  - If no wallpaper file exists, runs generate_assets.py to create one.
  - All operations are guarded by existence checks.
"""

import os
import sys
import shutil
import subprocess
from typing import Optional

sys.path.insert(0, '/opt/vice-os/lib')
sys.path.insert(0, '/opt/vice-os')

from python.vice_utils import log_info, log_warn, log_error

_WALLPAPER_DIRS = [
    "/usr/share/backgrounds",
    os.path.expanduser("~/.local/share/backgrounds"),
]
_NITROGEN_CONFIG = os.path.expanduser("~/.config/nitrogen/bg-saved.cfg")
_ASSET_GENERATOR = "/opt/vice-os/generate_assets.py"
_LEGACY_GENERATOR = "/opt/vice-os/assets/generate_assets.py"
_NITROGEN_BIN = "nitrogen"
_FEH_BIN = "feh"
_SWAYBG_BIN = "swaybg"


def _find_wallpaper() -> Optional[str]:
    """
    Find the first available wallpaper image.

    Searches WALLPAPER_DIRS for common image formats, sorted by name
    (so the most recently generated wallpaper is preferred).
    """
    for directory in _WALLPAPER_DIRS:
        if not os.path.isdir(directory):
            continue
        images = []
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            for entry in os.listdir(directory):
                if entry.lower().endswith(ext):
                    images.append(os.path.join(directory, entry))
        if images:
            images.sort()
            return images[-1]
    return None


def _generate_wallpaper() -> bool:
    """
    Run the project's asset generator to create a wallpaper.

    Supports both the deployed path (/opt/vice-os/generate_assets.py) and
    the legacy source path (/opt/vice-os/assets/generate_assets.py).
    """
    generator = None
    if os.path.isfile(_ASSET_GENERATOR):
        generator = _ASSET_GENERATOR
    elif os.path.isfile(_LEGACY_GENERATOR):
        generator = _LEGACY_GENERATOR

    if not generator:
        log_warn("Wallpaper: asset generator not found. Cannot generate wallpaper.")
        return False

    log_info("Wallpaper: generating procedural wallpaper...")
    try:
        result = subprocess.run(
            ["python3", generator],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log_info("Wallpaper: generation succeeded.")
            return True
        log_error(f"Wallpaper: asset generator failed (exit {result.returncode}): {result.stderr.strip()}")
        return False
    except Exception as e:
        log_error(f"Wallpaper: asset generator exception: {e}")
        return False


def _apply_swaybg(wallpaper_path: str) -> bool:
    """Apply wallpaper via swaybg (Wayland sessions)."""
    if not shutil.which(_SWAYBG_BIN):
        log_warn("Wallpaper: swaybg not found. Cannot set Wayland wallpaper.")
        return False

    log_info(f"Wallpaper: applying via swaybg {wallpaper_path}...")
    try:
        # Kill any existing swaybg instance to avoid duplicates
        subprocess.run(
            ["pkill", "-x", _SWAYBG_BIN],
            capture_output=True, timeout=5
        )
        result = subprocess.Popen(
            [_SWAYBG_BIN, "-i", wallpaper_path, "-m", "fill"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if result.pid > 0:
            log_info("Wallpaper: swaybg applied successfully.")
            return True
        log_warn("Wallpaper: swaybg failed to start.")
        return False
    except Exception as e:
        log_error(f"Wallpaper: swaybg exception: {e}")
        return False


def _apply_nitrogen() -> bool:
    """Restore wallpaper via nitrogen --restore."""
    if not shutil.which(_NITROGEN_BIN):
        return False
    if not os.path.isfile(_NITROGEN_CONFIG):
        log_info("Wallpaper: no nitrogen config found. Not restoring.")
        return False

    log_info("Wallpaper: applying via nitrogen --restore...")
    try:
        result = subprocess.run(
            [_NITROGEN_BIN, "--restore"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            log_info("Wallpaper: nitrogen applied successfully.")
            return True
        log_warn(f"Wallpaper: nitrogen --restore returned {result.returncode}. Trying feh fallback.")
        return False
    except Exception as e:
        log_error(f"Wallpaper: nitrogen exception: {e}")
        return False


def _apply_feh(wallpaper_path: str) -> bool:
    """Apply wallpaper via feh --bg-scale."""
    if not shutil.which(_FEH_BIN):
        log_warn("Wallpaper: feh not found. Cannot set wallpaper.")
        return False

    log_info(f"Wallpaper: applying via feh --bg-scale {wallpaper_path}...")
    try:
        result = subprocess.run(
            [_FEH_BIN, "--bg-scale", wallpaper_path],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            log_info("Wallpaper: feh applied successfully.")
            return True
        log_warn(f"Wallpaper: feh returned {result.returncode}.")
        return False
    except Exception as e:
        log_error(f"Wallpaper: feh exception: {e}")
        return False


def apply_wallpaper():
    """
    Main entry point called by vice_shell.py on startup.

    Pipeline:
      1. Wayland sessions: find wallpaper and apply via swaybg.
      2. X11 sessions: try nitrogen --restore (preserves user's last-set wallpaper).
      3. If no wallpaper file exists, generate one via the asset generator.
      4. Find the generated wallpaper and apply via feh (X11) or swaybg (Wayland).
      5. If everything fails, log a warning (not fatal — user can set manually).
    """
    log_info("Wallpaper: initializing desktop wallpaper...")

    is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))

    if is_wayland:
        wallpaper = _find_wallpaper()
        if wallpaper is None:
            log_info("Wallpaper: no wallpaper found. Attempting generation...")
            if _generate_wallpaper():
                wallpaper = _find_wallpaper()
        if wallpaper and os.path.isfile(wallpaper):
            _apply_swaybg(wallpaper)
        else:
            log_warn("Wallpaper: unable to set Wayland wallpaper. User can set one manually via Settings.")
        return

    if _apply_nitrogen():
        return

    wallpaper = _find_wallpaper()
    if wallpaper is None:
        log_info("Wallpaper: no wallpaper found. Attempting generation...")
        if _generate_wallpaper():
            wallpaper = _find_wallpaper()

    if wallpaper and os.path.isfile(wallpaper):
        _apply_feh(wallpaper)
    else:
        log_warn("Wallpaper: unable to set wallpaper. User can set one manually via Settings.")


if __name__ == "__main__":
    apply_wallpaper()

