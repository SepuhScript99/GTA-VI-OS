#!/usr/bin/env python3
"""
Vice OS — USB Auto-Mount Daemon
Monitors udev events for USB block devices and auto-mounts them.
Creates mount points under /media/$USER/ and optionally shows notifications.
"""

import sys
import os
import subprocess
import signal
import json
import time
import threading
from pathlib import Path

REPO_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib'))
for p in ['/opt/vice-os/lib', REPO_LIB]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from python.vice_utils import log_info, log_error
except ImportError:
    try:
        from vice_utils import log_info, log_error
    except ImportError:
        def log_info(msg): print(f"[INFO] {msg}")
        def log_error(msg): print(f"[ERROR] {msg}", file=sys.stderr)

MOUNT_BASE = Path(os.path.expanduser("~/media"))
CONFIG_FILE = Path(os.path.expanduser("~/.config/vice-os/usb_automount.json"))
PID_FILE = Path("/tmp/vice_usb_automount.pid")


class USBAutomount:
    def __init__(self):
        self._running = False
        self._udev_monitor = None
        self._mounts = {}
        self._config = self._load_config()
        MOUNT_BASE.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        defaults = {
            "auto_mount": True,
            "notify": True,
            "fstype_whitelist": ["vfat", "exfat", "ntfs", "ext4", "ext3", "ext2"],
            "fstype_blacklist": ["swap", "crypto_LUKS"],
            "mount_options": "rw,nosuid,nodev,relatime,uid=1000,gid=1000,umask=022",
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    return {**defaults, **json.load(f)}
            except Exception:
                pass
        return defaults

    def _save_config(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            log_error(f"Config save failed: {e}")

    def start(self):
        if self._running:
            return
        self._running = True
        self._write_pid()

        # Start udev monitor in background thread
        self._udev_monitor = threading.Thread(target=self._monitor_udev, daemon=True)
        self._udev_monitor.start()

        # Also handle existing devices
        self._scan_existing()

        log_info("USB Auto-Mount daemon started")

    def stop(self):
        self._running = False
        try:
            PID_FILE.unlink()
        except Exception:
            pass
        log_info("USB Auto-Mount daemon stopped")

    def _write_pid(self):
        try:
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

    def _scan_existing(self):
        """Mount already-connected USB drives on startup."""
        out, _ = subprocess.run(
            ["lsblk", "-o", "NAME,TYPE,FSTYPE,TRAN,MOUNTPOINT", "-J"],
            capture_output=True, text=True
        ).stdout, None
        try:
            data = json.loads(out)
            for dev in data.get("blockdevices", []):
                if dev.get("tran") == "usb" and dev.get("type") == "part":
                    self._mount_device(dev)
        except Exception:
            pass

    def _monitor_udev(self):
        """Monitor udev events for USB block devices."""
        try:
            # Use udevadm monitor for USB block events
            proc = subprocess.Popen(
                ["udevadm", "monitor", "--udev", "--subsystem-match=block", "--property"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1
            )

            for line in proc.stdout:
                if not self._running:
                    break
                if "ACTION=add" in line:
                    # Wait a moment for device to settle
                    time.sleep(0.5)
                    # Get the device path from the line
                    self._process_udev_event(line)
        except Exception as e:
            log_error(f"Udev monitor error: {e}")

    def _process_udev_event(self, line):
        """Process a udev event line to extract device info."""
        # Extract device name from udev event
        import re
        match = re.search(r'DEVNAME=(/dev/\S+)', line)
        if not match:
            return
        dev_path = match.group(1)

        # Get device info via lsblk
        out, _ = subprocess.run(
            ["lsblk", "-o", "NAME,TYPE,FSTYPE,TRAN,MOUNTPOINT,SIZE", "-J", dev_path],
            capture_output=True, text=True, timeout=3
        ).stdout, None
        try:
            data = json.loads(out)
            for dev in data.get("blockdevices", []):
                if dev.get("type") == "part" and dev.get("tran") == "usb":
                    self._mount_device(dev)
        except Exception as e:
            log_error(f"Udev event processing error: {e}")

    def _mount_device(self, dev):
        """Mount a USB device if not already mounted."""
        name = dev.get("name", "")
        import re
        if not name or not re.match(r'^[a-zA-Z0-9_-]+$', name):
            log_error(f"Invalid device name: {name}")
            return
        fstype = dev.get("fstype", "")
        mountpoint = dev.get("mountpoint", "")
        size = dev.get("size", "")

        # Check whitelist/blacklist
        if fstype in self._config["fstype_blacklist"]:
            return
        if self._config["fstype_whitelist"] and fstype not in self._config["fstype_whitelist"]:
            return

        if mountpoint:
            return  # Already mounted

        # Create mount point
        mount_dir = MOUNT_BASE / name
        try:
            mount_dir.mkdir(parents=True, exist_ok=True)

            # Build mount command
            opts = self._config["mount_options"]
            if fstype in ("ntfs", "vfat", "exfat"):
                opts = "rw,nosuid,nodev,relatime,uid=1000,gid=1000,umask=022"

            cmd = ["mount", "-t", fstype, "-o", opts, f"/dev/{name}", str(mount_dir)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                self._mounts[name] = str(mount_dir)
                log_info(f"Auto-mounted /dev/{name} ({fstype}, {size}) -> {mount_dir}")
                if self._config["notify"]:
                    self._notify(f"USB Mounted", f"{name} ({fstype}) mounted at {mount_dir}")
            else:
                log_error(f"Mount failed /dev/{name}: {r.stderr}")
                # Clean up empty dir
                try:
                    mount_dir.rmdir()
                except Exception:
                    pass
        except Exception as e:
            log_error(f"Mount error for /dev/{name}: {e}")

    def _notify(self, title, body):
        """Send desktop notification."""
        try:
            subprocess.run(["notify-send", "-i", "drive-removable-media", title, body], timeout=3)
        except Exception:
            pass

    def get_mounts(self):
        """Return currently tracked mounts."""
        return self._mounts

    def unmount(self, name):
        """Unmount a device by name."""
        mount_dir = self._mounts.get(name)
        if not mount_dir:
            return False
        try:
            subprocess.run(["umount", mount_dir], timeout=5, check=True)
            del self._mounts[name]
            try:
                Path(mount_dir).rmdir()
            except Exception:
                pass
            log_info(f"Unmounted /dev/{name}")
            if self._config["notify"]:
                self._notify("USB Unmounted", f"{name} safely removed")
            return True
        except Exception as e:
            log_error(f"Unmount failed /dev/{name}: {e}")
            return False

    def get_config(self):
        return self._config

    def update_config(self, cfg):
        self._config.update(cfg)
        self._save_config()


def main():
    """Run as daemon."""
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            print("Daemon stopped")
        else:
            print("Daemon not running")
        return

    # Fork to background
    if os.fork() > 0:
        return

    os.setsid()
    daemon = USBAutomount()
    daemon.start()

    # Keep running
    try:
        while daemon._running:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    main()