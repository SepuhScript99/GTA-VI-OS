#!/usr/bin/env python3
"""
Vice OS — System Notifier
Background daemon that polls system health and sends desktop notifications:
  - Battery: warnings at 20% (low), 10% (critical), 5% (danger)
  - Disk: warning when a filesystem exceeds 90% usage
  - Temperature: warning when a thermal zone exceeds THRESH_TEMP
Runs from the session; uses notify-send so it works with the Vice
notification daemon (or any org.freedesktop.Notifications server).
"""

import sys
import os
import shutil
import subprocess
import time
import json
import datetime

sys.path.insert(0, '/opt/vice-os/lib')
from python.vice_utils import log_info, log_error

POLL_INTERVAL = 60  # seconds
STATE_FILE = os.path.expanduser("~/.local/share/vice-os/notifier_state.json")
NOTIF_HISTORY = os.path.expanduser("~/.local/share/vice-os/notification_history.json")

BATTERY_THRESHOLDS = [
    (20, "low", "Battery Low", "Battery at {pct}%. Consider plugging in."),
    (10, "critical", "Battery Critical", "Battery at {pct}%. Plug in now!"),
    (5,  "danger", "Battery Danger", "Battery at {pct}%. System will suspend soon."),
]

DISK_WARN_PCT = 90
TEMP_WARN_C = 75


def notify(title, body, urgency="normal", icon="dialog-warning"):
    """Send a desktop notification via notify-send or gdbus fallback."""
    timeout_ms = "5000" if urgency != "critical" else "0"
    try:
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "-i", icon, "-u", urgency, "-t", timeout_ms, title, body],
                capture_output=True, timeout=5
            )
        elif shutil.which("gdbus"):
            subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.freedesktop.Notifications",
                    "--object-path", "/org/freedesktop/Notifications",
                    "--method", "org.freedesktop.Notifications.Notify",
                    "vice-os", "0", icon, title, body, "[]", "{}", timeout_ms
                ],
                capture_output=True, timeout=5
            )
    except Exception as e:
        log_error(f"Notification dispatch failed: {e}")
    # Also record in the Vice notification history for the history viewer
    try:
        os.makedirs(os.path.dirname(NOTIF_HISTORY), exist_ok=True)
        entries = []
        if os.path.exists(NOTIF_HISTORY):
            with open(NOTIF_HISTORY) as f:
                entries = json.load(f)
        entries.append({
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "summary": title,
            "body": body,
            "urgency": urgency,
            "app": "system-notifier",
            "dismissed": False,
        })
        with open(NOTIF_HISTORY, "w") as f:
            json.dump(entries[-200:], f, indent=2)
    except Exception:
        pass


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"battery_alerted": {}, "disk_alerted": {}, "temp_alerted": {}}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log_error(f"Notifier state save failed: {e}")


def get_battery():
    """Return (percent, status) or None."""
    for name in ("BAT0", "BAT1"):
        base = f"/sys/class/power_supply/{name}"
        if not os.path.isdir(base):
            continue
        try:
            with open(os.path.join(base, "capacity")) as f:
                pct = int(f.read().strip())
            with open(os.path.join(base, "status")) as f:
                status = f.read().strip()
            return pct, status
        except (OSError, ValueError):
            continue
    return None


def check_battery(state):
    bat = get_battery()
    if not bat:
        return
    pct, status = bat
    if status == "Charging" or status == "Full":
        # Reset alerts when plugged in
        state["battery_alerted"] = {}
        return

    for threshold, level, title, body in BATTERY_THRESHOLDS:
        if pct <= threshold:
            # Alert once per threshold per discharge cycle
            if not state["battery_alerted"].get(level):
                notify(title, body.format(pct=pct),
                       urgency="critical" if level != "low" else "normal",
                       icon="battery-caution")
                log_info(f"Battery alert: {level} at {pct}%")
                state["battery_alerted"][level] = True
            break  # only the highest applicable threshold


def check_disk(state):
    """Warn when any real filesystem exceeds DISK_WARN_PCT."""
    try:
        out = subprocess.check_output(
            ["df", "--output=source,pcent,target"],
            text=True, timeout=5
        ).splitlines()[1:]
    except Exception:
        return
    for line in out:
        parts = line.split()
        if len(parts) < 3:
            continue
        source, pcent, target = parts[0], parts[1], parts[2]
        if any(x in source for x in ("tmpfs", "udev", "loop", "devtmpfs", "efivarfs")):
            continue
        try:
            pct = int(pcent.replace("%", ""))
        except ValueError:
            continue
        if pct >= DISK_WARN_PCT:
            if not state["disk_alerted"].get(target):
                notify("Disk Almost Full",
                       f"{target} is {pct}% full ({source}).",
                       urgency="critical", icon="drive-harddisk")
                log_info(f"Disk alert: {target} at {pct}%")
                state["disk_alerted"][target] = True
        else:
            # Clear alert flag once space is freed
            state["disk_alerted"].pop(target, None)


def check_temperature(state):
    """Warn when a thermal zone exceeds TEMP_WARN_C."""
    for i in range(8):
        path = f"/sys/class/thermal/thermal_zone{i}/temp"
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                celsius = int(f.read().strip()) / 1000
        except (OSError, ValueError):
            continue
        zone = f"zone{i}"
        if celsius >= TEMP_WARN_C:
            if not state["temp_alerted"].get(zone):
                notify("High Temperature",
                       f"Thermal zone {i} at {celsius:.0f}°C.",
                       urgency="critical", icon="temperature-high")
                log_info(f"Temp alert: {zone} at {celsius}C")
                state["temp_alerted"][zone] = True
        else:
            state["temp_alerted"].pop(zone, None)


def main():
    log_info("Vice system notifier started")
    print("Vice system notifier running (battery/disk/temperature alerts)")

    state = load_state()
    # Battery alerts reset each session (fresh discharge cycle tracking)
    state["battery_alerted"] = {}

    while True:
        try:
            check_battery(state)
            check_disk(state)
            check_temperature(state)
            save_state(state)
        except KeyboardInterrupt:
            log_info("System notifier stopped")
            break
        except Exception as e:
            log_error(f"Notifier loop error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()